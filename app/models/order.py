"""
Order data model.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class OrderData(BaseModel):
    """
    Order data model for tracking order information during conversation.
    """

    # Order type: "buy" (user sends THB, receives MMK) or "sell" (user sends MMK, receives THB)
    order_type: str = Field(..., description="Order type: 'buy' or 'sell'")

    # Amount in THB
    thb_amount: Optional[float] = Field(None, description="Amount in Thai Baht")

    # Amount in MMK
    mmk_amount: Optional[float] = Field(None, description="Amount in Myanmar Kyat")

    # Exchange rate
    exchange_rate: Optional[float] = Field(
        None, description="Exchange rate used for conversion"
    )

    # Receipt file IDs from Telegram (supports multiple receipts)
    receipt_file_ids: List[str] = Field(
        default_factory=list, description="Telegram file IDs for receipt images"
    )

    # Multiple receipt support
    receipt_amounts: List[float] = Field(
        default_factory=list, description="Amount from each receipt"
    )
    receipt_bank_ids: List[int] = Field(
        default_factory=list, description="Bank ID from each receipt"
    )
    expected_bank_id: Optional[int] = Field(
        None, description="First receipt's bank ID (all receipts must match)"
    )
    expected_bank_name: Optional[str] = Field(
        None, description="Expected bank name for display"
    )
    expected_account_number: Optional[str] = Field(
        None, description="Expected account number for display"
    )
    total_amount: float = Field(default=0.0, description="Sum of all receipt amounts")
    receipt_count: int = Field(default=0, description="Number of verified receipts")

    # User's bank information
    user_bank_info: Optional[str] = Field(
        None, description="User's bank account information"
    )

    # QR code file ID from Telegram (legacy - for receipt QR)
    qr_file_id: Optional[str] = Field(
        None, description="Telegram file ID for QR code image"
    )

    # User's bank QR code file ID
    user_bank_qr_file_id: Optional[str] = Field(
        None, description="Telegram file ID for user's bank QR code image"
    )

    # Selected Myanmar bank account
    myanmar_bank_account: Optional[str] = Field(
        None, description="Selected Myanmar bank account name"
    )

    # Admin bank detected from OCR
    detected_admin_bank_id: Optional[int] = Field(
        None, description="Admin bank ID detected from receipt OCR"
    )

    # Selected payment bank (bank user pays TO - selected before sending receipt)
    selected_payment_bank_id: Optional[int] = Field(
        None, description="Bank ID user selected to pay to"
    )
    selected_payment_bank_name: Optional[str] = Field(
        None, description="Bank name user selected to pay to"
    )

    # User's selected bank details (bank user receives FROM)
    selected_user_bank_id: Optional[int] = Field(
        None, description="User's selected bank ID"
    )
    selected_user_bank_name: Optional[str] = Field(
        None, description="User's selected bank name"
    )
    user_account_number: Optional[str] = Field(
        None, description="User's account number"
    )
    user_account_name: Optional[str] = Field(
        None, description="User's account holder name"
    )

    # Order ID from backend (after submission)
    order_id: Optional[str] = Field(None, description="Order ID from backend system")

    # Media group ID for handling multiple photos
    media_group_id: Optional[str] = Field(None, description="Telegram media group ID")

    # Collected photos in media group
    collected_photos: List[str] = Field(
        default_factory=list, description="Collected photo file IDs in media group"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "order_type": "buy",
                "thb_amount": 1000.0,
                "mmk_amount": 285714.29,
                "exchange_rate": 0.0035,
                "receipt_file_ids": ["AgACAgIAAxkBAAIC..."],
                "user_bank_info": "KBZ Bank - 1234567890 - John Doe",
                "qr_file_id": "AgACAgIAAxkBAAIC...",
                "myanmar_bank_account": "KBZ",
                "order_id": "ORD-20231110-001",
            }
        }
