"""create payments, payment_captures, payment_refunds, webhook_events, triggers, constraints

Revision ID: 0008_payments_razorpay_schema
Revises: 0007_orders_outbox_schema
Create Date: 2026-11-18 14:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_payments_razorpay_schema"
down_revision: str | None = "0007_orders_outbox_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create payments table (Payment Attempts)
    op.create_table(
        "payments",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
            index=True,
        ),
        sa.Column("guest_token_hash", sa.String(64), nullable=True, index=True),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'RAZORPAY_SANDBOX'"),
        ),
        sa.Column("provider_order_id", sa.String(128), nullable=True, index=True),
        sa.Column("provider_payment_id", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'CREATING'"),
            index=True,
        ),
        sa.Column("method", sa.String(32), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_description", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_payment_ownership",
        ),
        sa.CheckConstraint("amount_paise >= 0", name="chk_payment_amount_paise"),
        sa.CheckConstraint(
            "status IN ('CREATING', 'CREATION_AMBIGUOUS', 'PENDING', 'AUTHORIZED', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')",
            name="chk_payment_status",
        ),
        sa.UniqueConstraint(
            "order_id", "idempotency_key", name="uq_payments_order_idempotency"
        ),
        sa.UniqueConstraint(
            "order_id", "attempt_number", name="uq_payments_order_attempt"
        ),
        sa.UniqueConstraint("id", "order_id", name="uq_payments_id_order"),
    )

    # 2. Create payment_captures table (Durable Capture Ledger)
    op.create_table(
        "payment_captures",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'RAZORPAY_SANDBOX'"),
        ),
        sa.Column("provider_payment_id", sa.String(128), nullable=False),
        sa.Column("provider_order_id", sa.String(128), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'CAPTURED'"),
        ),
        sa.Column("method", sa.String(32), nullable=True),
        sa.Column("acquirer_reference", sa.String(128), nullable=True),
        sa.Column(
            "is_fulfillment_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "reconciliation_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'NORMAL'"),
            index=True,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_payment_captures_provider_payment",
        ),
        sa.UniqueConstraint("id", "order_id", name="uq_payment_captures_id_order"),
        sa.ForeignKeyConstraint(
            ["payment_id", "order_id"],
            ["payments.id", "payments.order_id"],
            name="fk_payment_captures_payment_same_order",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount_paise > 0", name="chk_capture_amount_paise"),
        sa.CheckConstraint(
            "reconciliation_status IN ('NORMAL', 'OVERPAYMENT_ANOMALY', 'PARTIAL_CAPTURE_REJECTED', 'LATE_CAPTURE_ANOMALY', 'RESOLVED')",
            name="chk_capture_reconciliation_status",
        ),
    )

    # Trigger to protect capture ledger immutable facts and fulfillment eligibility
    op.execute(
        """
        CREATE OR REPLACE FUNCTION protect_payment_capture_immutable_facts()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Illegal operation: payment_captures records are permanent financial ledger facts and cannot be deleted (capture_id=%)', OLD.id;
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF OLD.provider <> NEW.provider OR
                   OLD.provider_payment_id <> NEW.provider_payment_id OR
                   OLD.order_id <> NEW.order_id OR
                   OLD.payment_id <> NEW.payment_id OR
                   OLD.amount_paise <> NEW.amount_paise OR
                   OLD.currency <> NEW.currency OR
                   OLD.captured_at <> NEW.captured_at OR
                   OLD.is_fulfillment_eligible <> NEW.is_fulfillment_eligible THEN
                    RAISE EXCEPTION 'Illegal operation: core financial facts and fulfillment eligibility in payment_captures are immutable (capture_id=%)', OLD.id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_payment_captures_protect_immutable
        BEFORE UPDATE OR DELETE ON payment_captures
        FOR EACH ROW
        EXECUTE FUNCTION protect_payment_capture_immutable_facts();
        """
    )

    # 3. Alter orders table to establish single source of truth for fulfillment
    op.add_column(
        "orders",
        sa.Column("fulfilling_capture_id", sa.Uuid(), nullable=True, unique=True),
    )

    op.create_foreign_key(
        "fk_orders_fulfilling_capture_same_order",
        "orders",
        "payment_captures",
        ["fulfilling_capture_id", "id"],
        ["id", "order_id"],
        ondelete="RESTRICT",
    )

    # Update check constraint on orders for payment_status to include PARTIALLY_REFUNDED
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS chk_order_payment_status;")
    op.execute(
        """
        ALTER TABLE orders ADD CONSTRAINT chk_order_payment_status CHECK (
            payment_status IN ('NOT_INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')
        );
        """
    )

    # Trigger on orders to guarantee fulfilling_capture_id immutability, eligibility and existence (Dual INSERT/UPDATE)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_order_fulfilling_capture()
        RETURNS TRIGGER AS $$
        DECLARE
            v_eligible BOOLEAN;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.fulfilling_capture_id IS NOT NULL THEN
                    SELECT is_fulfillment_eligible INTO v_eligible
                    FROM payment_captures
                    WHERE id = NEW.fulfilling_capture_id AND order_id = NEW.id;
                    
                    IF v_eligible IS NOT TRUE THEN
                        RAISE EXCEPTION 'Illegal fulfillment: capture % does not exist or is not eligible for order % fulfillment', 
                            NEW.fulfilling_capture_id, NEW.id;
                    END IF;
                END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.fulfilling_capture_id IS NOT NULL THEN
                    -- Invariant: Once set, fulfilling_capture_id cannot be overwritten/replaced
                    IF OLD.fulfilling_capture_id IS NOT NULL AND OLD.fulfilling_capture_id <> NEW.fulfilling_capture_id THEN
                        RAISE EXCEPTION 'Illegal state violation: fulfilling_capture_id is immutable once set (order_id=%, existing=%, attempted=%)', 
                            OLD.id, OLD.fulfilling_capture_id, NEW.fulfilling_capture_id;
                    END IF;
                    
                    -- Invariant: Fulfilling capture MUST be marked fulfillment eligible when first assigned
                    IF OLD.fulfilling_capture_id IS NULL THEN
                        SELECT is_fulfillment_eligible INTO v_eligible
                        FROM payment_captures
                        WHERE id = NEW.fulfilling_capture_id AND order_id = NEW.id;
                        
                        IF v_eligible IS NOT TRUE THEN
                            RAISE EXCEPTION 'Illegal fulfillment: capture % does not exist or is not eligible for order % fulfillment', 
                                NEW.fulfilling_capture_id, NEW.id;
                        END IF;
                    END IF;
                END IF;

                -- Invariant: fulfilling_capture_id can never be cleared back to NULL
                IF OLD.fulfilling_capture_id IS NOT NULL AND NEW.fulfilling_capture_id IS NULL THEN
                    RAISE EXCEPTION 'Illegal state violation: fulfilling_capture_id cannot be cleared once set (order_id=%)', OLD.id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_orders_fulfilling_capture_immutable
        BEFORE INSERT OR UPDATE ON orders
        FOR EACH ROW
        EXECUTE FUNCTION check_order_fulfilling_capture();
        """
    )

    # 4. Create payment_refunds table
    op.create_table(
        "payment_refunds",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "capture_id",
            sa.Uuid(),
            sa.ForeignKey("payment_captures.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_refund_id", sa.String(128), unique=True, nullable=True),
        sa.Column("idempotency_key", sa.String(128), unique=True, nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'REFUND_REQUESTED'"),
            index=True,
        ),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_description", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["capture_id", "order_id"],
            ["payment_captures.id", "payment_captures.order_id"],
            name="fk_refunds_capture_same_order",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "order_id"],
            ["payments.id", "payments.order_id"],
            name="fk_refunds_payment_same_order",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount_paise > 0", name="chk_refund_amount_paise"),
        sa.CheckConstraint(
            "status IN ('REFUND_REQUESTED', 'REFUND_PENDING', 'REFUND_PROCESSED', 'REFUND_FAILED')",
            name="chk_refund_status",
        ),
    )

    # 5. Create webhook_events table
    op.create_table(
        "webhook_events",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'RAZORPAY'"),
        ),
        sa.Column("provider_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'PENDING'"),
            index=True,
        ),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_provider_event"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'IGNORED', 'FAILED')",
            name="chk_webhook_status",
        ),
    )

    op.create_index(
        "ix_webhook_claim",
        "webhook_events",
        ["status", "claim_expires_at"],
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_orders_fulfilling_capture_immutable ON orders;"
    )
    op.execute("DROP FUNCTION IF EXISTS check_order_fulfilling_capture();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_payment_captures_protect_immutable ON payment_captures;"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_payment_capture_immutable_facts();")
    op.drop_table("webhook_events")
    op.drop_table("payment_refunds")
    op.drop_constraint(
        "fk_orders_fulfilling_capture_same_order", "orders", type_="foreignkey"
    )
    op.drop_column("orders", "fulfilling_capture_id")
    op.drop_table("payment_captures")
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS chk_order_payment_status;")
    op.execute(
        """
        ALTER TABLE orders ADD CONSTRAINT chk_order_payment_status CHECK (
            payment_status IN ('NOT_INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'REFUNDED')
        );
        """
    )
    op.drop_table("payments")
