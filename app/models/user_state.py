"""
User state model for conversation management.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.conversation import ConversationState
from app.models.order import OrderData


class UserState(BaseModel):
    """
    User state model for tracking conversation state and data.
    """

    # User identification
    user_id: int = Field(..., description="Telegram user ID")
    chat_id: int = Field(..., description="Telegram chat ID")

    # Current conversation state
    current_state: ConversationState = Field(
        default=ConversationState.CHOOSE, description="Current conversation state"
    )

    # Order data
    order_data: OrderData = Field(
        default_factory=OrderData, description="Order data for current conversation"
    )

    # Blocking state (for rate limiting or temporary blocks)
    blocked: bool = Field(
        default=False, description="Whether user is temporarily blocked"
    )
    blocked_until: Optional[datetime] = Field(
        None, description="Timestamp when block expires"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When state was created"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="When state was last updated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123456789,
                "chat_id": 123456789,
                "current_state": "WAIT_RECEIPT",
                "order_data": {
                    "order_type": "buy",
                    "thb_amount": 1000.0,
                    "exchange_rate": 0.0035,
                },
                "blocked": False,
                "blocked_until": None,
                "created_at": "2023-11-10T10:00:00",
                "last_updated": "2023-11-10T10:05:00",
            }
        }

    def update_timestamp(self):
        """Update the last_updated timestamp to current time."""
        self.last_updated = datetime.utcnow()
