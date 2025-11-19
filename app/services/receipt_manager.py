"""
Receipt manager service for handling multiple receipts with bank verification.
"""

from typing import Optional, Tuple, List, Dict, Any
from app.models.receipt import ReceiptData
from app.logging_config import get_logger

logger = get_logger(__name__)


class ReceiptManager:
    """
    Manages multiple receipt collection, verification, and summation.
    """

    @staticmethod
    def verify_bank_match(
        receipt_data: ReceiptData,
        expected_bank_id: Optional[int],
        admin_banks: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """
        Verify that receipt is for the expected admin bank account.

        Args:
            receipt_data: Extracted receipt data from OCR
            expected_bank_id: Expected bank ID (from first receipt)
            admin_banks: List of admin bank accounts

        Returns:
            Tuple of (is_match: bool, error_message: str)
        """
        # If this is the first receipt, any valid admin bank is acceptable
        if expected_bank_id is None:
            if receipt_data.matched_bank_id:
                return True, ""
            else:
                return False, "Receipt does not match any admin bank account"

        # Check if receipt matches expected bank
        if receipt_data.matched_bank_id == expected_bank_id:
            return True, ""

        # Bank mismatch - build error message
        expected_bank = next(
            (b for b in admin_banks if b.get("id") == expected_bank_id), None
        )
        received_bank = next(
            (b for b in admin_banks if b.get("id") == receipt_data.matched_bank_id),
            None,
        )

        if expected_bank and received_bank:
            error_msg = (
                f"❌ Wrong Bank Account!\n\n"
                f"Expected:\n"
                f"🏦 {expected_bank.get('bank_name', 'Unknown')}\n"
                f"💳 {expected_bank.get('account_number', 'Unknown')}\n\n"
                f"Received:\n"
                f"🏦 {received_bank.get('bank_name', 'Unknown')}\n"
                f"💳 {received_bank.get('account_number', 'Unknown')}\n\n"
                f"All receipts must be for the SAME admin bank account."
            )
        else:
            error_msg = (
                f"❌ Bank account mismatch!\n\n"
                f"All receipts must be for the same admin bank account.\n"
                f"Please send a receipt for the correct account."
            )

        logger.warning(
            "Bank mismatch detected",
            extra={
                "expected_bank_id": expected_bank_id,
                "received_bank_id": receipt_data.matched_bank_id,
            },
        )

        return False, error_msg

    @staticmethod
    def get_bank_details(
        bank_id: int, admin_banks: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get bank name and account number for a given bank ID.

        Args:
            bank_id: Bank ID to look up
            admin_banks: List of admin bank accounts

        Returns:
            Tuple of (bank_name, account_number) or (None, None) if not found
        """
        bank = next((b for b in admin_banks if b.get("id") == bank_id), None)
        if bank:
            return bank.get("bank_name"), bank.get("account_number")
        return None, None

    @staticmethod
    def format_receipt_summary(
        receipt_count: int,
        total_amount: float,
        currency: str,
        bank_name: Optional[str] = None,
        account_number: Optional[str] = None,
    ) -> str:
        """
        Format a summary message for collected receipts.

        Args:
            receipt_count: Number of receipts
            total_amount: Total amount from all receipts
            currency: Currency code (THB or MMK)
            bank_name: Bank name (optional)
            account_number: Account number (optional)

        Returns:
            Formatted summary message
        """
        summary = (
            f"📋 Receipt Summary\n\n"
            f"📸 Receipts: {receipt_count}\n"
            f"💰 Total: {total_amount:,.2f} {currency}\n"
        )

        if bank_name and account_number:
            summary += f"\n🏦 Bank: {bank_name}\n" f"💳 Account: {account_number}\n"

        return summary

    @staticmethod
    def format_receipt_verified_message(
        receipt_number: int,
        amount: float,
        currency: str,
        total_amount: float,
        bank_name: Optional[str] = None,
        account_number: Optional[str] = None,
        is_first: bool = False,
        order_type: str = "buy",
    ) -> str:
        """
        Format a message after receipt verification.

        Args:
            receipt_number: Receipt number (1, 2, 3, ...)
            amount: Amount from this receipt
            currency: Currency code (THB or MMK)
            total_amount: Total amount so far
            bank_name: Bank name (optional, shown for first receipt)
            account_number: Account number (optional, shown for first receipt)
            is_first: Whether this is the first receipt
            order_type: "buy" or "sell"

        Returns:
            Formatted verification message
        """
        # Determine order type text
        order_type_text = (
            "Buy MMK (Send THB)" if order_type == "buy" else "Sell MMK (Send MMK)"
        )
        
        # Build order summary message
        message = (
            f"📋 Order Summary\n\n"
            f"Type: {order_type_text}\n"
            f"📸 Receipts: {receipt_number}\n"
            f"💰 Total Amount: {total_amount:,.2f} {currency}\n\n"
            f"Bank Account:\n"
            f"🏦 {bank_name}\n"
            f"💳 {account_number}\n\n"
            f"Ready to submit?"
        )

        return message

    @staticmethod
    def format_order_summary(
        order_type: str,
        receipt_count: int,
        total_amount: float,
        currency: str,
        bank_name: str,
        account_number: str,
    ) -> str:
        """
        Format final order summary before submission.

        Args:
            order_type: "buy" or "sell"
            receipt_count: Number of receipts
            total_amount: Total amount
            currency: Currency code
            bank_name: Bank name
            account_number: Account number

        Returns:
            Formatted order summary
        """
        order_type_text = (
            "Buy MMK (Send THB)" if order_type == "buy" else "Sell MMK (Send MMK)"
        )

        summary = (
            f"📋 Order Summary\n\n"
            f"Type: {order_type_text}\n"
            f"📸 Receipts: {receipt_count}\n"
            f"💰 Total Amount: {total_amount:,.2f} {currency}\n\n"
            f"Bank Account:\n"
            f"🏦 {bank_name}\n"
            f"💳 {account_number}\n\n"
            f"Ready to submit?"
        )

        return summary

    @staticmethod
    def calculate_total(amounts: List[float]) -> float:
        """
        Calculate total from list of amounts.

        Args:
            amounts: List of amounts

        Returns:
            Total sum
        """
        return sum(amounts)

    @staticmethod
    def validate_receipt_limit(
        receipt_count: int, max_receipts: int = 10
    ) -> Tuple[bool, str]:
        """
        Validate that receipt count doesn't exceed limit.

        Args:
            receipt_count: Current number of receipts
            max_receipts: Maximum allowed receipts

        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if receipt_count >= max_receipts:
            error_msg = (
                f"⚠️ Maximum Receipt Limit Reached\n\n"
                f"You have reached the maximum of {max_receipts} receipts per order.\n\n"
                f"Please confirm your current receipts or start over."
            )
            return False, error_msg

        return True, ""
