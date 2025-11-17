"""
Admin receipt validation service for detecting common mistakes in admin confirmation receipts.
"""

import logging
from typing import Optional, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.ocr_service import (
    OCRService,
    OCRError,
    InvalidImageError,
    NotAReceiptError,
)
from app.models.receipt import ReceiptData, ValidationResult

logger = logging.getLogger(__name__)


class AdminReceiptValidationError(Exception):
    """Base exception for admin receipt validation errors."""

    pass


class AdminReceiptValidator:
    """
    Service for validating admin confirmation receipts to detect common mistakes.

    Common mistakes detected:
    - MMK amount shows value but THB shows 0 (copy-paste error)
    - Amount doesn't match expected transfer amount
    - Receipt is not a valid transfer receipt
    """

    def __init__(self, ocr_service: OCRService, tolerance_percent: float = 1.0):
        """
        Initialize admin receipt validator.

        Args:
            ocr_service: OCR service for extracting receipt data
            tolerance_percent: Tolerance percentage for amount validation (default 1%)
        """
        self.ocr_service = ocr_service
        self.tolerance_percent = tolerance_percent

    async def validate_admin_receipt(
        self,
        receipt_image_bytes: bytes,
        expected_amount: float,
        order_type: str,
        exchange_rate: float,
    ) -> ValidationResult:
        """
        Validate admin confirmation receipt for common mistakes.

        Args:
            receipt_image_bytes: Admin receipt image as bytes
            expected_amount: Expected transfer amount
            order_type: Order type ("buy" or "sell")
            exchange_rate: Exchange rate used for conversion

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            AdminReceiptValidationError: If validation process fails
        """
        try:
            logger.info(
                f"Validating admin receipt for {order_type} order, "
                f"expected amount: {expected_amount}"
            )

            # Extract receipt data using OCR
            try:
                receipt_data = await self.ocr_service.extract_with_retry(
                    receipt_image_bytes
                )
            except InvalidImageError as e:
                logger.error(f"Invalid admin receipt image: {e}")
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Invalid receipt image: {e}"],
                    warnings=[],
                    confidence=0.0,
                    can_skip=False,
                )
            except NotAReceiptError as e:
                logger.error(f"Not a valid receipt: {e}")
                return ValidationResult(
                    is_valid=False,
                    errors=[
                        "❌ This image is not a valid bank transfer receipt.",
                        "Please upload a clear photo of your transfer receipt showing:",
                        "  • Transfer amount",
                        "  • Bank name",
                        "  • Account number",
                        "  • Transaction details",
                    ],
                    warnings=[],
                    confidence=0.0,
                    can_skip=False,  # Don't allow skip for non-receipts
                )
            except OCRError as e:
                logger.error(f"OCR error validating admin receipt: {e}")
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Could not read receipt: {e}"],
                    warnings=["OCR failed - manual review recommended"],
                    confidence=0.0,
                    can_skip=True,  # Allow skip if OCR fails
                )

            if not receipt_data:
                logger.warning("OCR returned no data for admin receipt")
                return ValidationResult(
                    is_valid=False,
                    errors=["Could not extract data from receipt"],
                    warnings=["Receipt may be unclear - manual review recommended"],
                    confidence=0.0,
                    can_skip=True,
                )

            # Validate receipt data
            errors = []
            warnings = []

            # Check for common MMK/THB confusion
            mmk_thb_warning = self._check_mmk_thb_confusion(
                receipt_data, order_type, expected_amount, exchange_rate
            )
            if mmk_thb_warning:
                warnings.append(mmk_thb_warning)

            # Validate amount matches expected
            amount_error = self._validate_amount(
                receipt_data, expected_amount, order_type, exchange_rate
            )
            if amount_error:
                errors.append(amount_error)

            # Check if amount is suspiciously low
            if receipt_data.amount < 100:
                warnings.append(
                    f"⚠️ Amount is very low ({receipt_data.amount}). "
                    "Please verify this is correct."
                )

            # Check confidence score
            if receipt_data.confidence_score < 0.5:
                warnings.append(
                    f"⚠️ Low confidence in OCR extraction ({receipt_data.confidence_score:.1%}). "
                    "Please verify receipt manually."
                )

            # Determine validation result
            is_valid = len(errors) == 0
            can_skip = len(warnings) > 0 and len(errors) == 0

            result = ValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                confidence=receipt_data.confidence_score,
                can_skip=can_skip,
            )

            if is_valid:
                logger.info("Admin receipt validation passed")
            else:
                logger.warning(
                    f"Admin receipt validation failed: {len(errors)} errors, "
                    f"{len(warnings)} warnings"
                )

            return result

        except Exception as e:
            logger.error(
                f"Unexpected error validating admin receipt: {e}", exc_info=True
            )
            raise AdminReceiptValidationError(f"Validation failed: {e}")

    def _check_mmk_thb_confusion(
        self,
        receipt_data: ReceiptData,
        order_type: str,
        expected_amount: float,
        exchange_rate: float,
    ) -> Optional[str]:
        """
        Check for common MMK/THB confusion error.

        Common mistake: Admin copies MMK amount but THB shows 0, or vice versa.

        Args:
            receipt_data: Extracted receipt data
            order_type: Order type ("buy" or "sell")
            expected_amount: Expected transfer amount
            exchange_rate: Exchange rate

        Returns:
            Warning message if confusion detected, None otherwise
        """
        # For buy orders, admin should send MMK
        # For sell orders, admin should send THB

        if order_type == "buy":
            # Admin should send MMK
            expected_mmk = expected_amount / exchange_rate

            # Check if receipt shows THB instead of MMK
            # (amount is close to THB value but should be MMK)
            if abs(receipt_data.amount - expected_amount) < expected_amount * 0.01:
                return (
                    f"⚠️ **Possible Currency Confusion**\n"
                    f"Receipt shows {receipt_data.amount:,.2f} but expected MMK amount is {expected_mmk:,.2f}\n"
                    f"Did you send THB ({expected_amount:,.2f}) instead of MMK?"
                )

        else:  # sell order
            # Admin should send THB
            expected_thb = expected_amount * exchange_rate

            # Check if receipt shows MMK instead of THB
            if (
                abs(receipt_data.amount - (expected_amount / exchange_rate))
                < (expected_amount / exchange_rate) * 0.01
            ):
                return (
                    f"⚠️ **Possible Currency Confusion**\n"
                    f"Receipt shows {receipt_data.amount:,.2f} but expected THB amount is {expected_thb:,.2f}\n"
                    f"Did you send MMK ({expected_amount:,.2f}) instead of THB?"
                )

        return None

    def _validate_amount(
        self,
        receipt_data: ReceiptData,
        expected_amount: float,
        order_type: str,
        exchange_rate: float,
    ) -> Optional[str]:
        """
        Validate receipt amount matches expected amount within tolerance.

        Args:
            receipt_data: Extracted receipt data
            expected_amount: Expected transfer amount
            order_type: Order type ("buy" or "sell")
            exchange_rate: Exchange rate

        Returns:
            Error message if validation fails, None otherwise
        """
        # Calculate expected amount in correct currency
        if order_type == "buy":
            # Admin sends MMK
            expected = expected_amount / exchange_rate
            currency = "MMK"
        else:
            # Admin sends THB
            expected = expected_amount * exchange_rate
            currency = "THB"

        # Calculate tolerance
        tolerance = expected * (self.tolerance_percent / 100)

        # Check if amount is within tolerance
        difference = abs(receipt_data.amount - expected)
        if difference > tolerance:
            return (
                f"❌ **Amount Mismatch**\n"
                f"Expected: {expected:,.2f} {currency}\n"
                f"Receipt shows: {receipt_data.amount:,.2f}\n"
                f"Difference: {difference:,.2f} (tolerance: ±{tolerance:,.2f})"
            )

        return None

    def create_validation_warning_message(
        self, validation_result: ValidationResult, order_id: Optional[str] = None
    ) -> str:
        """
        Create formatted warning message for validation issues.

        Args:
            validation_result: Validation result with warnings/errors
            order_id: Optional order ID for reference

        Returns:
            Formatted warning message
        """
        message = "⚠️ **Admin Receipt Validation Warning**\n\n"

        if order_id:
            message += f"Order ID: {order_id}\n\n"

        if validation_result.errors:
            message += "**Errors:**\n"
            for error in validation_result.errors:
                message += f"{error}\n\n"

        if validation_result.warnings:
            message += "**Warnings:**\n"
            for warning in validation_result.warnings:
                message += f"{warning}\n\n"

        if validation_result.can_skip:
            message += (
                "You can skip this validation if you're confident the receipt is correct, "
                "or send a corrected receipt for re-validation."
            )
        else:
            message += "Please send a corrected receipt."

        return message

    def create_skip_validation_keyboard(self, order_id: str) -> InlineKeyboardMarkup:
        """
        Create inline keyboard with "Skip Validation" button.

        Args:
            order_id: Order ID to include in callback data

        Returns:
            InlineKeyboardMarkup with skip button
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Skip Validation", callback_data=f"skip_validation:{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📸 Send Corrected Receipt",
                    callback_data=f"resend_receipt:{order_id}",
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def handle_skip_validation_callback(
        self, order_id: str, admin_user_id: int
    ) -> Dict[str, Any]:
        """
        Handle skip validation button callback.

        Args:
            order_id: Order ID being validated
            admin_user_id: Admin user who clicked skip

        Returns:
            Dict with skip confirmation details
        """
        logger.info(f"Admin {admin_user_id} skipped validation for order {order_id}")

        return {
            "skipped": True,
            "order_id": order_id,
            "admin_user_id": admin_user_id,
            "message": "✅ Validation skipped. Proceeding with order completion.",
        }

    async def handle_resend_receipt_callback(
        self, order_id: str, admin_user_id: int
    ) -> Dict[str, Any]:
        """
        Handle resend receipt button callback.

        Args:
            order_id: Order ID being validated
            admin_user_id: Admin user who clicked resend

        Returns:
            Dict with resend confirmation details
        """
        logger.info(
            f"Admin {admin_user_id} requested to resend receipt for order {order_id}"
        )

        return {
            "resend_requested": True,
            "order_id": order_id,
            "admin_user_id": admin_user_id,
            "message": "📸 Please send the corrected receipt image.",
        }
