"""
Conversation state enumeration.
"""

from enum import Enum


class ConversationState(str, Enum):
    """
    Enumeration of conversation states for the bot.
    """

    # Initial state - user needs to choose buy or sell
    CHOOSE = "CHOOSE"

    # User selecting which bank to pay to (before sending receipt)
    SELECT_PAYMENT_BANK = "SELECT_PAYMENT_BANK"

    # Waiting for user to send receipt
    WAIT_RECEIPT = "WAIT_RECEIPT"

    # Verifying the receipt with OCR
    VERIFY_RECEIPT = "VERIFY_RECEIPT"

    # Collecting additional receipts (after first receipt verified)
    COLLECTING_RECEIPTS = "COLLECTING_RECEIPTS"

    # User choosing action after receipt verification (add more, confirm, restart)
    RECEIPT_CHOICE = "RECEIPT_CHOICE"

    # Waiting for user bank information (legacy - kept for compatibility)
    WAIT_USER_BANK = "WAIT_USER_BANK"

    # User selecting their bank from buttons
    SELECT_USER_BANK = "SELECT_USER_BANK"

    # Waiting for account number
    WAIT_ACCOUNT_NUMBER = "WAIT_ACCOUNT_NUMBER"

    # Waiting for account holder name
    WAIT_ACCOUNT_NAME = "WAIT_ACCOUNT_NAME"

    # Waiting for user bank QR code (alternative to text input)
    WAIT_USER_BANK_QR = "WAIT_USER_BANK_QR"

    # Order is pending admin approval
    PENDING = "PENDING"

    # Order is complete
    COMPLETE = "COMPLETE"

    # Conversation cancelled
    CANCELLED = "CANCELLED"
