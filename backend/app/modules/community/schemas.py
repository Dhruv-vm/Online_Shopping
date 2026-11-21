import datetime
import uuid

from pydantic import BaseModel, Field, model_validator


class CampaignCreateRequest(BaseModel):
    listing_id: uuid.UUID
    title: str | None = Field(None, min_length=3, max_length=160)
    min_participants: int = Field(..., ge=2, le=1000)
    max_participants: int = Field(..., ge=2, le=1000)
    discount_percent: float = Field(..., gt=0, le=90)
    duration_hours: int = Field(..., ge=1, le=336)
    max_quantity_per_member: int = Field(5, ge=1, le=10)

    @model_validator(mode="after")
    def _bounds(self):
        if self.max_participants < self.min_participants:
            raise ValueError("max_participants must be >= min_participants")
        return self


class JoinRequest(BaseModel):
    quantity: int = Field(1, ge=1, le=10)


class CampaignItem(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    product_name: str
    image_url: str | None
    title: str
    min_participants: int
    max_participants: int
    current_participants: int
    participants_needed: int
    total_quantity: int
    max_quantity_per_member: int
    discount_percent: float
    list_price_paise: int
    group_price_paise: int
    status: str
    expires_at: datetime.datetime
    seconds_remaining: int
    started_by_customer: bool = False
    # Initials only (no names/contacts) so customers can see real members.
    participant_initials: list[str] = []
    my_membership: dict | None = None


class CampaignListResponse(BaseModel):
    items: list[CampaignItem]
    total: int


class ShareResponse(BaseModel):
    url: str
    message: str
    whatsapp_url: str
    sms_url: str


class TemplateUpsertRequest(BaseModel):
    """Retailer terms under which customers may start a group buy on a listing."""

    listing_id: uuid.UUID
    min_participants: int = Field(..., ge=2, le=1000)
    max_participants: int = Field(..., ge=2, le=1000)
    discount_percent: float = Field(..., gt=0, le=90)
    duration_hours: int = Field(48, ge=1, le=336)
    max_quantity_per_member: int = Field(2, ge=1, le=10)
    max_open_campaigns: int = Field(3, ge=1, le=50)

    @model_validator(mode="after")
    def _bounds(self):
        if self.max_participants < self.min_participants:
            raise ValueError("max_participants must be >= min_participants")
        return self


class TemplateItem(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    product_name: str
    image_url: str | None
    min_participants: int
    max_participants: int
    discount_percent: float
    duration_hours: int
    max_quantity_per_member: int
    max_open_campaigns: int
    open_campaigns: int
    list_price_paise: int
    group_price_paise: int
    is_active: bool


class TemplateListResponse(BaseModel):
    items: list[TemplateItem]
    total: int


class CustomerStartRequest(BaseModel):
    template_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=10)
    title: str | None = Field(None, min_length=3, max_length=160)


class InviteResponse(BaseModel):
    """A new invitation. ``token`` is shown once; only its hash is stored."""

    token: str
    url: str
    expires_at: datetime.datetime
    message: str
    whatsapp_url: str
    sms_url: str


class InvitePreview(BaseModel):
    """Public view of an invitation: campaign facts only, never who sent it."""

    campaign_id: uuid.UUID
    title: str
    product_name: str
    list_price_paise: int
    group_price_paise: int
    discount_bps: int
    current_participants: int
    min_participants: int
    max_participants: int
    campaign_expires_at: datetime.datetime
    invite_expires_at: datetime.datetime
    can_join: bool
    reason: str | None = None


class InviteJoinRequest(BaseModel):
    quantity: int = Field(default=1, ge=1, le=50)
