"""
Receipt validation service for verifying extracted receipt data against expected values.
"""

import logging
from difflib import SequenceMatcher
from typing import Optional

from app.models.receipt import ReceiptData, ValidationResult, BankAccount

logger = logging.getLogger(__name__)


class ReceiptValidator:
    """
    Service for validating extracted receipt data against expected bank account details.
    """

    def __init__(
        self,
        bank_name_threshold: float = 0.7,
        account_name_threshold: float = 0.7,
        amount_tolerance: float = 0.01,
    ):
        """
        Initialize receipt validator with configurable thresholds.

        Args:
            bank_name_threshold: Minimum similarity score for bank name matching (0-1)
            account_name_threshold: Minimum similarity score for account name matching (0-1)
            amount_tolerance: Tolerance for amount validation as percentage (e.g., 0.01 = ±1%)
        """
        self.bank_name_threshold = bank_name_threshold
        self.account_name_threshold = account_name_threshold
        self.amount_tolerance = amount_tolerance

    def fuzzy_match(self, str1: str, str2: str) -> float:
        """
        Calculate fuzzy matching similarity between two strings.

        Args:
            str1: First string to compare
            str2: Second string to compare

        Returns:
            Similarity score between 0 and 1
        """
        # Normalize strings: lowercase and strip whitespace
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()

        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, s1, s2).ratio()

        return similarity

    def validate_bank_name(
        self, extracted: str, expected: str
    ) -> tuple[bool, float, Optional[str]]:
        """
        Validate bank name using fuzzy matching.

        Args:
            extracted: Bank name extracted from receipt
            expected: Expected bank name

        Returns:
            Tuple of (is_valid, similarity_score, error_message)
        """
        if not extracted:
            return False, 0.0, "Bank name not found in receipt"

        similarity = self.fuzzy_match(extracted, expected)

        if similarity >= self.bank_name_threshold:
            return True, similarity, None
        else:
            return (
                False,
                similarity,
                (
                    f"Bank name mismatch: Expected '{expected}', "
                    f"found '{extracted}' (similarity: {similarity:.2%})"
                ),
            )

    def validate_account_number(
        self, extracted: str, expected: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate account number using exact matching or last 4 digits matching.

        Args:
            extracted: Account number extracted from receipt
            expected: Expected account number

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not extracted:
            return False, "Account number not found in receipt"

        # Remove spaces and dashes for comparison
        extracted_clean = extracted.replace(" ", "").replace("-", "")
        expected_clean = expected.replace(" ", "").replace("-", "")

        # Check exact match
        if extracted_clean == expected_clean:
            return True, None

        # Check last 4 digits match (common in receipts)
        if len(extracted_clean) >= 4 and len(expected_clean) >= 4:
            if extracted_clean[-4:] == expected_clean[-4:]:
                logger.info(
                    f"Account number matched on last 4 digits: {extracted_clean[-4:]}"
                )
                return True, None

        return False, (
            f"Account number mismatch: Expected '{expected}', " f"found '{extracted}'"
        )

    def validate_account_name(
        self, extracted: str, expected: str
    ) -> tuple[bool, float, Optional[str]]:
        """
        Validate account holder name using fuzzy matching.

        Args:
            extracted: Account name extracted from receipt
            expected: Expected account name

        Returns:
            Tuple of (is_valid, similarity_score, error_message)
        """
        if not extracted:
            return False, 0.0, "Account holder name not found in receipt"

        similarity = self.fuzzy_match(extracted, expected)

        if similarity >= self.account_name_threshold:
            return True, similarity, None
        else:
            # Generate warning instead of error if similarity is close
            if similarity >= 0.5:
                return (
                    False,
                    similarity,
                    (
                        f"Account name may not match: Expected '{expected}', "
                        f"found '{extracted}' (similarity: {similarity:.2%})"
                    ),
                )
            else:
                return (
                    False,
                    similarity,
                    (
                        f"Account name mismatch: Expected '{expected}', "
                        f"found '{extracted}' (similarity: {similarity:.2%})"
                    ),
                )

    def validate_amount(
        self, extracted: float, expected: float
    ) -> tuple[bool, Optional[str]]:
        """
        Validate transfer amount with configurable tolerance.

        Args:
            extracted: Amount extracted from receipt
            expected: Expected transfer amount

        Returns:
            Tuple of (is_valid, error_message)
        """
        if extracted <= 0:
            return False, "Transfer amount not found or invalid in receipt"

        # Calculate tolerance range
        tolerance_amount = expected * self.amount_tolerance
        min_amount = expected - tolerance_amount
        max_amount = expected + tolerance_amount

        if min_amount <= extracted <= max_amount:
            return True, None
        else:
            return False, (
                f"Amount mismatch: Expected {expected:.2f}, "
                f"found {extracted:.2f} "
                f"(tolerance: ±{self.amount_tolerance:.1%})"
            )

    def validate(
        self,
        extracted: ReceiptData,
        expected_bank: BankAccount,
        expected_amount: Optional[float] = None,
    ) -> ValidationResult:
        """
        Validate extracted receipt data against expected bank account and amount.

        Args:
            extracted: Receipt data extracted from OCR
            expected_bank: Expected bank account details
            expected_amount: Expected transfer amount (optional)

        Returns:
            ValidationResult with validation status, errors, and warnings
        """
        errors = []
        warnings = []
        confidence_scores = []

        # Validate bank name
        bank_valid, bank_similarity, bank_error = self.validate_bank_name(
            extracted.bank_name, expected_bank.bank_name
        )
        confidence_scores.append(bank_similarity)

        if not bank_valid:
            if bank_similarity >= 0.5:
                warnings.append(bank_error)
            else:
                errors.append(bank_error)

        # Validate account number
        account_valid, account_error = self.validate_account_number(
            extracted.account_number, expected_bank.account_number
        )

        if not account_valid:
            errors.append(account_error)
        else:
            confidence_scores.append(1.0)

        # Validate account holder name
        name_valid, name_similarity, name_error = self.validate_account_name(
            extracted.account_name, expected_bank.account_name
        )
        confidence_scores.append(name_similarity)

        if not name_valid:
            if name_similarity >= 0.5:
                warnings.append(name_error)
            else:
                errors.append(name_error)

        # Validate amount if provided
        if expected_amount is not None:
            amount_valid, amount_error = self.validate_amount(
                extracted.amount, expected_amount
            )

            if not amount_valid:
                errors.append(amount_error)
            else:
                confidence_scores.append(1.0)

        # Include OCR confidence score
        if extracted.confidence_score > 0:
            confidence_scores.append(extracted.confidence_score)

        # Calculate overall confidence
        overall_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 0.0
        )

        # Determine if validation passed
        is_valid = len(errors) == 0

        # Can skip if only warnings (no errors)
        can_skip = len(warnings) > 0 and len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence=overall_confidence,
            can_skip=can_skip,
        )

        logger.info(
            f"Validation result: valid={is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}, "
            f"confidence={overall_confidence:.2%}"
        )

        return result

    def validate_admin_receipt(
        self, extracted: ReceiptData, expected_amount: float, order_type: str
    ) -> ValidationResult:
        """
        Validate admin confirmation receipt for common mistakes.

        Args:
            extracted: Receipt data extracted from admin's receipt
            expected_amount: Expected transfer amount
            order_type: Type of order ("buy" or "sell")

        Returns:
            ValidationResult with validation status and warnings
        """
        errors = []
        warnings = []

        # Check for common MMK/THB confusion
        # For buy orders: admin sends MMK, so MMK amount should be > 0
        # For sell orders: admin sends THB, so THB amount should be > 0
        if order_type == "buy":
            # Admin should send MMK to user
            if extracted.amount == 0:
                warnings.append(
                    "⚠️ Warning: Amount shows 0. Please verify this is correct."
                )
            # Check if bank name suggests wrong currency
            if (
                "thai" in extracted.bank_name.lower()
                or "kasikorn" in extracted.bank_name.lower()
            ):
                warnings.append(
                    "⚠️ Warning: Bank appears to be Thai bank, but order type is 'buy' "
                    "(admin should send MMK). Please verify."
                )
        elif order_type == "sell":
            # Admin should send THB to user
            if extracted.amount == 0:
                warnings.append(
                    "⚠️ Warning: Amount shows 0. Please verify this is correct."
                )
            # Check if bank name suggests wrong currency
            if (
                "myanmar" in extracted.bank_name.lower()
                or "kbz" in extracted.bank_name.lower()
            ):
                warnings.append(
                    "⚠️ Warning: Bank appears to be Myanmar bank, but order type is 'sell' "
                    "(admin should send THB). Please verify."
                )

        # Validate amount matches expected
        if extracted.amount > 0:
            amount_valid, amount_error = self.validate_amount(
                extracted.amount, expected_amount
            )

            if not amount_valid:
                warnings.append(amount_error)

        # Admin receipt validation is more lenient - only warnings, no hard errors
        is_valid = len(errors) == 0
        can_skip = len(warnings) > 0

        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            confidence=extracted.confidence_score,
            can_skip=can_skip,
        )

        logger.info(
            f"Admin receipt validation: valid={is_valid}, "
            f"warnings={len(warnings)}, can_skip={can_skip}"
        )

        return result
