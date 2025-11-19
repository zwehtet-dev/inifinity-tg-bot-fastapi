"""
Receipt data models for OCR extraction and validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ReceiptData(BaseModel):
    """
    Data extracted from a receipt image using OCR.
    """

    amount: float = Field(..., description="Transfer amount extracted from receipt")
    bank_name: str = Field(..., description="Bank name extracted from receipt")
    account_number: str = Field(
        ..., description="Account number extracted from receipt"
    )
    account_name: str = Field(
        ..., description="Account holder name extracted from receipt"
    )
    transaction_date: Optional[str] = Field(
        None, description="Transaction date if visible"
    )
    transaction_id: Optional[str] = Field(None, description="Transaction ID if visible")
    confidence_score: float = Field(
        ...,
        description="REQUIRED: Confidence score (0.0-1.0) based on how well the receipt matches admin bank accounts. "
        "1.0 = perfect match, 0.8-0.9 = good match, 0.5-0.7 = partial match, <0.5 = no match",
        ge=0.0,
        le=1.0,
    )
    matched_bank_id: Optional[int] = Field(
        None, description="ID of the matched admin bank account from the database"
    )


class ValidationResult(BaseModel):
    """
    Result of receipt validation against expected bank account details.
    """

    is_valid: bool = Field(..., description="Whether the receipt passed validation")
    errors: List[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list, description="List of validation warnings"
    )
    confidence: float = Field(default=0.0, description="Overall confidence score (0-1)")
    can_skip: bool = Field(
        default=False, description="Whether validation can be skipped (warnings only)"
    )


class BankAccount(BaseModel):
    """
    Expected bank account details for validation.
    """

    bank_name: str = Field(..., description="Expected bank name")
    account_number: str = Field(..., description="Expected account number")
    account_name: str = Field(..., description="Expected account holder name")
    qr_image: Optional[str] = Field(None, description="QR code image URL or path")
    display_name: Optional[str] = Field(None, description="Display name for the bank")
    id: Optional[int] = Field(None, description="Bank account ID")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "bank_name": "Kasikorn Bank",
                "account_number": "1234567890",
                "account_name": "John Doe",
                "qr_image": "/static/qr/kasikorn.jpg",
                "display_name": "MMN (Kbank)",
                "id": 1,
            }
        }
