import datetime
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: str = Field(..., max_length=255, description="Customer email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters)",
    )
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str | None = Field(None, max_length=15)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email_field(cls, v: str) -> str:
        return v.strip().lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(
        None, description="Optional plaintext refresh token if not sent in cookie"
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    phone: str | None
    full_name: str
    role: str
    is_active: bool
    retailer_id: uuid.UUID | None = None
    store_name: str | None = None
    verification_status: str | None = None
    preferred_language: str = "en"
    created_at: datetime.datetime


class RetailerRegisterRequest(BaseModel):
    # Owner credentials
    email: str = Field(..., max_length=255, description="Retailer business email")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(
        ..., min_length=2, max_length=255, description="Store owner / manager name"
    )
    phone: str = Field(
        ..., min_length=10, max_length=15, description="Primary contact phone"
    )

    # Store details
    store_name: str = Field(
        ..., min_length=2, max_length=255, description="Business / Store display name"
    )
    state: str = Field(
        ..., min_length=2, max_length=100, description="Store state (e.g. MH, KA, DL)"
    )
    business_address: str = Field(
        ..., min_length=5, description="Registered business / warehouse address"
    )
    contact_email: str | None = Field(None, max_length=255)
    contact_phone: str | None = Field(None, max_length=15)
    description: str | None = Field(None, max_length=2000)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format.")
        return v

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email_opt(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    csrf_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    csrf_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class AddressCreateRequest(BaseModel):
    recipient_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=10, max_length=15)
    line1: str = Field(..., min_length=3, max_length=255)
    line2: str | None = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., description="6-digit Indian PIN code")
    landmark: str | None = Field(None, max_length=255)
    is_default: bool = False

    @field_validator("postal_code")
    @classmethod
    def validate_pin_code(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[1-9][0-9]{5}$", v):
            raise ValueError("Postal code must be a valid 6-digit Indian PIN code.")
        return v


class AddressUpdateRequest(BaseModel):
    recipient_name: str | None = Field(None, min_length=2, max_length=255)
    phone: str | None = Field(None, min_length=10, max_length=15)
    line1: str | None = Field(None, min_length=3, max_length=255)
    line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, min_length=2, max_length=100)
    state: str | None = Field(None, min_length=2, max_length=100)
    postal_code: str | None = None
    landmark: str | None = Field(None, max_length=255)
    is_default: bool | None = None

    @field_validator("postal_code")
    @classmethod
    def validate_pin_code_opt(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not re.match(r"^[1-9][0-9]{5}$", v):
                raise ValueError("Postal code must be a valid 6-digit Indian PIN code.")
            return v
        return None


class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    recipient_name: str
    phone: str
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    landmark: str | None
    is_default: bool
    created_at: datetime.datetime
