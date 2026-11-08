from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator


class Register(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    company_name: str = Field(min_length=1, max_length=120)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class CompanyInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    logo_url: str | None = None
    accent: str = Field(default="#4f46e5", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("logo_url")
    @classmethod
    def safe_url(cls, value):
        if value and not value.startswith("https://res.cloudinary.com/"):
            raise ValueError("Use a Cloudinary HTTPS media URL")
        return value


class PaymentMethod(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    details: str = Field(min_length=1, max_length=3000)


class LinkInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=3000)
    category: Literal["tuition", "invoice", "service", "donation", "other"] = "tuition"
    amount: int = Field(strict=True, ge=100, le=100000000)
    currency: Literal[
        "USD",
        "NGN",
        "GBP",
        "EUR",
        "SAR",
        "CNY",
        "AED",
        "AUD",
        "CAD",
        "CHF",
        "HKD",
        "INR",
        "KES",
        "ZAR",
        "SGD",
        "NZD",
        "GHS",
        "EGP",
        "TRY",
        "MYR",
        "PKR",
        "BDT",
        "BRL",
        "MXN",
        "THB",
    ] = "USD"
    methods: list[PaymentMethod] = Field(min_length=1, max_length=10)
    receipt_heading: str = Field(default="Payment receipt", min_length=1, max_length=100)
    receipt_footer: str = Field(default="Thank you for your payment.", max_length=1000)
    theme: Literal["classic", "minimal", "bold"] = "classic"
    hero_url: str | None = None
    recipient_name: str | None = Field(default=None, max_length=120)
    recipient_email: EmailStr | None = None
    note: str = Field(default="", max_length=1000)
    _media = field_validator("hero_url")(CompanyInput.safe_url.__func__)


class CheckoutInput(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    method_index: int = Field(ge=0, le=9)
    transfer_reference: str = Field(default="", max_length=255)
    request_key: UUID


class ReviewInput(BaseModel):
    decision: Literal["paid", "rejected"]


class ActiveInput(BaseModel):
    active: bool
