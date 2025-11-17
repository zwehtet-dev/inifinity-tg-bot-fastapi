"""
Webhook endpoints for Telegram and Backend notifications.
"""

from fastapi import APIRouter, Request, HTTPException, Header, Depends
from typing import Optional
from pydantic import BaseModel

from app.config import get_settings
from app.logging_config import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhooks"])


# Pydantic models for request validation
class BackendWebhookPayload(BaseModel):
    """Payload from backend webhook notifications."""

    event: str
    order_id: str
    status: Optional[str] = (
        None  # Required for order_status_changed, not for admin_replied or order_verified
    )
    admin_receipt: Optional[str] = None
    telegram_id: str
    chat_id: int
    amount: Optional[float] = None
    order_type: Optional[str] = None
    # Fields for admin_replied event
    message_content: Optional[str] = None
    message_id: Optional[int] = None
    # Fields for order_verified event
    price: Optional[float] = None
    user_bank: Optional[str] = None
    receipt: Optional[str] = None


# Dependency for settings
def get_app_settings():
    return get_settings()


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    settings=Depends(get_app_settings),
):
    """
    Webhook endpoint for receiving updates from Telegram.

    Validates the secret token and processes incoming updates.
    """
    # Validate webhook secret
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning(
            "Invalid Telegram webhook secret",
            extra={
                "received_token": (
                    x_telegram_bot_api_secret_token[:10]
                    if x_telegram_bot_api_secret_token
                    else None
                )
            },
        )
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Get the update data
    try:
        update_data = await request.json()
        logger.debug(
            "Received Telegram update",
            extra={"update_id": update_data.get("update_id")},
        )

        # Get the telegram handler from app state
        telegram_handler = request.app.state.telegram_handler

        # Process the update
        await telegram_handler.process_update(update_data)

        return {"status": "ok"}

    except Exception as e:
        logger.error(
            "Error processing Telegram webhook", extra={"error": str(e)}, exc_info=True
        )
        # Return 200 to prevent Telegram from retrying
        return {"status": "error", "message": str(e)}


@router.post("/backend")
async def backend_webhook(
    payload: BackendWebhookPayload,
    request: Request,
    x_backend_secret: Optional[str] = Header(None),
    settings=Depends(get_app_settings),
):
    """
    Webhook endpoint for receiving notifications from backend.

    Handles order status updates and admin replies.
    """
    # Validate webhook secret
    if x_backend_secret != settings.backend_webhook_secret:
        logger.warning(
            "Invalid backend webhook secret",
            extra={
                "received_token": x_backend_secret[:10] if x_backend_secret else None
            },
        )
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        logger.info(
            "Received backend webhook",
            extra={
                "event": payload.event,
                "order_id": payload.order_id,
                "status": payload.status,
            },
        )

        # Get the backend webhook handler from app state
        backend_handler = request.app.state.backend_webhook_handler

        # Process the webhook based on event type
        if payload.event == "order_verified":
            await backend_handler.handle_order_verified(payload)
        elif payload.event == "order_status_changed":
            await backend_handler.handle_order_status_changed(payload)
        elif payload.event == "admin_replied":
            await backend_handler.handle_admin_replied(payload)
        else:
            logger.warning(f"Unknown webhook event type: {payload.event}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(
            "Error processing backend webhook",
            extra={"error": str(e), "payload": payload.dict()},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
