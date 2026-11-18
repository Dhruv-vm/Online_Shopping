from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_session_factory
from app.core.events.envelope import EventEnvelope
from app.core.search.client import (
    MockOpenSearchClient,
    OpenSearchConflictError,
    OpenSearchConnectionError,
)
from app.core.search.consumer import OpenSearchConsumer
from app.core.search.document import build_product_document
from app.core.search.index import (
    PRODUCT_INDEX_MAPPINGS,
    IndexManager,
)
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductImage,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)


@pytest.fixture
def mock_search_client() -> MockOpenSearchClient:
    return MockOpenSearchClient()


@pytest.fixture
def index_manager(mock_search_client: MockOpenSearchClient) -> IndexManager:
    return IndexManager(client=mock_search_client, prefix="test_basket")


@pytest.fixture
async def db_session():
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


# -------------------------------------------------------------------------
# MockOpenSearchClient & External Versioning Tests
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_opensearch_index_lifecycle(
    mock_search_client: MockOpenSearchClient,
):
    idx = "test_index_v1"
    assert await mock_search_client.index_exists(idx) is False

    await mock_search_client.create_index(idx, body=PRODUCT_INDEX_MAPPINGS)
    assert await mock_search_client.index_exists(idx) is True

    await mock_search_client.delete_index(idx)
    assert await mock_search_client.index_exists(idx) is False


@pytest.mark.asyncio
async def test_mock_opensearch_external_gte_versioning(
    mock_search_client: MockOpenSearchClient,
):
    idx = "test_products"
    doc_id = "prod-123"
    await mock_search_client.create_index(idx)

    # 1. Initial write with version 1
    res1 = await mock_search_client.index_document(
        index=idx,
        doc_id=doc_id,
        document={"name": "Almond Butter", "version": 1},
        version=1,
        version_type="external_gte",
    )
    assert res1["result"] == "created"
    assert res1["_version"] == 1

    # 2. Advance to version 3
    res2 = await mock_search_client.index_document(
        index=idx,
        doc_id=doc_id,
        document={"name": "Almond Butter Organic", "version": 3},
        version=3,
        version_type="external_gte",
    )
    assert res2["result"] == "updated"
    assert res2["_version"] == 3

    # 3. Same version replay (v3 again) is permitted under external_gte
    res3 = await mock_search_client.index_document(
        index=idx,
        doc_id=doc_id,
        document={"name": "Almond Butter Organic", "version": 3},
        version=3,
        version_type="external_gte",
    )
    assert res3["result"] == "updated"
    assert res3["_version"] == 3

    # 4. Stale version (v2 < current v3) must raise 409 Conflict
    with pytest.raises(OpenSearchConflictError) as exc_info:
        await mock_search_client.index_document(
            index=idx,
            doc_id=doc_id,
            document={"name": "Stale Update", "version": 2},
            version=2,
            version_type="external_gte",
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.current_version == 3


@pytest.mark.asyncio
async def test_mock_opensearch_deletion_versioning(
    mock_search_client: MockOpenSearchClient,
):
    idx = "test_products"
    doc_id = "prod-del"
    await mock_search_client.create_index(idx)

    # Index doc at version 5
    await mock_search_client.index_document(
        index=idx,
        doc_id=doc_id,
        document={"name": "To be deleted"},
        version=5,
        version_type="external_gte",
    )

    # Stale deletion attempt with version 4 must conflict
    with pytest.raises(OpenSearchConflictError):
        await mock_search_client.delete_document(
            index=idx,
            doc_id=doc_id,
            version=4,
            version_type="external_gte",
        )

    # Valid deletion with version 6 succeeds
    del_res = await mock_search_client.delete_document(
        index=idx,
        doc_id=doc_id,
        version=6,
        version_type="external_gte",
    )
    assert del_res["result"] == "deleted"

    # Subsequent delete on missing doc returns not_found without error
    del_res2 = await mock_search_client.delete_document(
        index=idx,
        doc_id=doc_id,
        version=7,
        version_type="external_gte",
    )
    assert del_res2["result"] == "not_found"


@pytest.mark.asyncio
async def test_mock_opensearch_downtime_simulation(
    mock_search_client: MockOpenSearchClient,
):
    mock_search_client.simulate_downtime = True
    with pytest.raises(OpenSearchConnectionError):
        await mock_search_client.ping()

    with pytest.raises(OpenSearchConnectionError):
        await mock_search_client.search("any_index", {})


# -------------------------------------------------------------------------
# IndexManager Tests (Aliases, Blue/Green, Reconciliation)
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_manager_lifecycle(
    index_manager: IndexManager, mock_search_client: MockOpenSearchClient
):
    # Ensure index and aliases
    idx = await index_manager.ensure_index_and_aliases(version="v1")
    assert idx == "test_basket_products_v1"
    assert await mock_search_client.index_exists(idx) is True

    # Check search and write aliases are attached to v1
    search_aliases = await mock_search_client.get_alias(index_manager.search_alias)
    assert idx in search_aliases

    # Blue/green alias swap to v2
    await mock_search_client.create_index("test_basket_products_v2")
    await index_manager.swap_aliases_to_new_version(new_version="v2", old_version="v1")

    search_aliases_v2 = await mock_search_client.get_alias(index_manager.search_alias)
    assert "test_basket_products_v2" in search_aliases_v2
    assert "test_basket_products_v1" not in search_aliases_v2

    # Rollback alias to v1
    await index_manager.rollback_alias(rollback_version="v1")
    search_aliases_rolled_back = await mock_search_client.get_alias(
        index_manager.search_alias
    )
    assert "test_basket_products_v1" in search_aliases_rolled_back
    assert "test_basket_products_v2" not in search_aliases_rolled_back


# -------------------------------------------------------------------------
# Deterministic build_product_document Projection Tests
# -------------------------------------------------------------------------


def test_build_product_document_projection():
    prod_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    var_id = uuid.uuid4()
    ret_id = uuid.uuid4()
    listing_id = uuid.uuid4()

    cat = Category(
        id=cat_id,
        name="Artisanal Foods",
        slug="artisanal-foods",
    )
    product = Product(
        id=prod_id,
        name="Wild Forest Honey",
        slug="wild-forest-honey",
        brand="PureHimalaya",
        description="Raw wild unprocessed mountain honey",
        category_id=cat_id,
        is_active=True,
    )
    product.category = cat

    img = ProductImage(
        id=uuid.uuid4(),
        product_id=prod_id,
        url="https://images.basket.local/honey.jpg",
        is_primary=True,
        sort_order=0,
    )
    product.images = [img]

    variant = ProductVariant(
        id=var_id,
        product_id=prod_id,
        sku="HONEY-500G",
        name="500g Jar",
        attributes={"weight": "500g", "origin": "Himalayas"},
    )

    retailer = Retailer(
        id=ret_id,
        name="GreenOrganics",
        slug="green-organics",
        rating=4.8,
    )

    listing = ProductListing(
        id=listing_id,
        variant_id=var_id,
        retailer_id=ret_id,
        selling_price_paise=45000,
        original_price_paise=50000,
        is_active=True,
    )
    listing.retailer = retailer

    inventory = StoreInventory(
        id=uuid.uuid4(),
        listing_id=listing_id,
        on_hand_quantity=15,
        reserved_quantity=2,
    )
    listing.inventory = inventory

    variant.listings = [listing]
    product.variants = [variant]

    # Build projection
    doc = build_product_document(product, aggregate_version=4)

    assert doc["product_id"] == str(prod_id)
    assert doc["name"] == "Wild Forest Honey"
    assert doc["brand"] == "PureHimalaya"
    assert doc["category_name"] == "Artisanal Foods"
    assert doc["category_slug"] == "artisanal-foods"
    assert doc["primary_image_url"] == "https://images.basket.local/honey.jpg"
    assert doc["min_price_paise"] == 45000
    assert doc["max_price_paise"] == 45000
    assert doc["is_in_stock"] is True
    assert doc["total_available_quantity"] == 13
    assert doc["rating"] == 4.8
    assert doc["aggregate_version"] == 4
    assert "Wild Forest Honey" in doc["searchable_text"]
    assert "PureHimalaya" in doc["searchable_text"]
    assert "500g" in doc["searchable_text"]


# -------------------------------------------------------------------------
# Strategy B OpenSearchConsumer Tests
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_opensearch_consumer_handles_product_upsert(
    db_session: AsyncSession,
    mock_search_client: MockOpenSearchClient,
):
    from sqlalchemy import select

    session_factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, class_=AsyncSession
    )

    # 1. Fetch existing seeded product
    stmt = select(Product).limit(1)
    prod = (await db_session.execute(stmt)).scalar_one()

    # 2. Setup OpenSearch index and consumer
    write_alias = "basket_products_write"
    await mock_search_client.create_index("basket_products_v1")
    await mock_search_client.update_aliases(
        actions=[{"add": {"index": "basket_products_v1", "alias": write_alias}}]
    )

    consumer = OpenSearchConsumer(
        session_factory=session_factory,
        search_client=mock_search_client,
        index_alias=write_alias,
    )

    # 3. Simulate product.created event
    envelope = EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="product.created",
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="Product",
        aggregate_id=str(prod.id),
        aggregate_version=1,
        payload={"product_id": str(prod.id), "name": prod.name},
    )

    # Handle event inside session
    await consumer.handle_event(envelope, db_session)

    # 4. Verify document in OpenSearch
    doc = await mock_search_client.get_document(write_alias, str(prod.id))
    assert doc is not None
    assert doc["_source"]["name"] == prod.name
    assert doc["_source"]["aggregate_version"] == 1


@pytest.mark.asyncio
async def test_opensearch_consumer_handles_version_conflict_as_safe_noop(
    db_session: AsyncSession,
    mock_search_client: MockOpenSearchClient,
):
    from sqlalchemy import select

    session_factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, class_=AsyncSession
    )

    stmt = select(Product).offset(1).limit(1)
    prod = (await db_session.execute(stmt)).scalar_one()
    prod_id = prod.id

    write_alias = "basket_products_write"
    await mock_search_client.create_index("basket_products_v1")
    await mock_search_client.update_aliases(
        actions=[{"add": {"index": "basket_products_v1", "alias": write_alias}}]
    )

    # Pre-index doc at version 5
    await mock_search_client.index_document(
        index=write_alias,
        doc_id=str(prod_id),
        document={"name": prod.name, "aggregate_version": 5},
        version=5,
        version_type="external_gte",
    )

    consumer = OpenSearchConsumer(
        session_factory=session_factory,
        search_client=mock_search_client,
        index_alias=write_alias,
    )

    # Incoming stale event at version 4 (should be discarded as safe no-op)
    stale_envelope = EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="product.updated",
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="Product",
        aggregate_id=str(prod_id),
        aggregate_version=4,
        payload={"product_id": str(prod_id)},
    )

    # Should not raise an error
    await consumer.handle_event(stale_envelope, db_session)

    # Verify OpenSearch still holds version 5
    doc = await mock_search_client.get_document(write_alias, str(prod_id))
    assert doc["_version"] == 5


@pytest.mark.asyncio
async def test_opensearch_consumer_handles_product_deletion(
    db_session: AsyncSession,
    mock_search_client: MockOpenSearchClient,
):
    session_factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, class_=AsyncSession
    )
    prod_id = uuid.uuid4()
    write_alias = "basket_products_write"
    await mock_search_client.create_index("basket_products_v1")
    await mock_search_client.update_aliases(
        actions=[{"add": {"index": "basket_products_v1", "alias": write_alias}}]
    )

    # Index doc at version 2
    await mock_search_client.index_document(
        index=write_alias,
        doc_id=str(prod_id),
        document={"name": "Discontinued Product", "aggregate_version": 2},
        version=2,
        version_type="external_gte",
    )

    consumer = OpenSearchConsumer(
        session_factory=session_factory,
        search_client=mock_search_client,
        index_alias=write_alias,
    )

    # Delete event at version 3
    del_envelope = EventEnvelope(
        event_id=uuid.uuid4(),
        event_type="product.deleted",
        event_version=1,
        occurred_at=datetime.now(UTC),
        aggregate_type="Product",
        aggregate_id=str(prod_id),
        aggregate_version=3,
        payload={"product_id": str(prod_id)},
    )

    await consumer.handle_event(del_envelope, db_session)

    # Verify doc deleted
    doc = await mock_search_client.get_document(write_alias, str(prod_id))
    assert doc is None
