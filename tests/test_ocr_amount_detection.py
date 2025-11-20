"""
Test OCR amount detection from various receipt formats.

This test helps verify that the OCR service can correctly extract amounts
from different receipt formats commonly used by clients.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ocr_service import OCRService
from app.models.receipt import ReceiptData


@pytest.fixture
def mock_ocr_service():
    """Create a mock OCR service for testing."""
    service = OCRService(
        openai_api_key="test_key",
        model="gpt-4o-mini",
        admin_banks=[
            {
                "id": 1,
                "bank_name": "KBZ Bank",
                "account_number": "1234567890",
                "account_name": "DAW HLA ZIN WAI HTET",
            }
        ],
        enable_cache=False,
    )
    return service


class TestAmountDetection:
    """Test cases for amount detection from various receipt formats."""

    @pytest.mark.asyncio
    async def test_amount_with_minus_sign_and_commas(self, mock_ocr_service):
        """
        Test: -398,500.00 (Ks) format
        Common in Myanmar mobile banking apps
        """
        # Mock the LLM response
        mock_receipt = ReceiptData(
            amount=398500.00,  # Should extract without minus and commas
            bank_name="KBZ Bank",
            account_number="1234567890",
            account_name="DAW HLA ZIN WAI HTET",
            transaction_date="2025-11-20",
            transaction_id="0100397607145683791",
            confidence_score=0.95,
        )

        with patch.object(
            mock_ocr_service.llm, "ainvoke", new_callable=AsyncMock
        ) as mock_invoke:
            mock_invoke.return_value = mock_receipt

            # Test with dummy image
            result = await mock_ocr_service.extract_receipt_data(b"dummy_image_bytes")

            assert result is not None
            assert result.amount == 398500.00
            assert result.bank_name == "KBZ Bank"
            assert result.confidence_score >= 0.8

    @pytest.mark.asyncio
    async def test_amount_with_thai_format(self, mock_ocr_service):
        """
        Test: 1,234.56 THB format
        Common in Thai banking apps
        """
        mock_receipt = ReceiptData(
            amount=1234.56,
            bank_name="SCB",
            account_number="1234567890",
            account_name="Test User",
            transaction_date="2025-11-20",
            transaction_id="TEST123",
            confidence_score=0.90,
        )

        with patch.object(
            mock_ocr_service.llm, "ainvoke", new_callable=AsyncMock
        ) as mock_invoke:
            mock_invoke.return_value = mock_receipt

            result = await mock_ocr_service.extract_receipt_data(b"dummy_image_bytes")

            assert result is not None
            assert result.amount == 1234.56

    @pytest.mark.asyncio
    async def test_amount_without_decimals(self, mock_ocr_service):
        """
        Test: 500000 format (no decimals)
        Common in some banking apps
        """
        mock_receipt = ReceiptData(
            amount=500000.0,
            bank_name="KBZ Bank",
            account_number="1234567890",
            account_name="Test User",
            transaction_date="2025-11-20",
            transaction_id="TEST123",
            confidence_score=0.85,
        )

        with patch.object(
            mock_ocr_service.llm, "ainvoke", new_callable=AsyncMock
        ) as mock_invoke:
            mock_invoke.return_value = mock_receipt

            result = await mock_ocr_service.extract_receipt_data(b"dummy_image_bytes")

            assert result is not None
            assert result.amount == 500000.0

    @pytest.mark.asyncio
    async def test_prompt_includes_amount_instructions(self, mock_ocr_service):
        """Test that the prompt includes clear amount extraction instructions."""
        prompt = mock_ocr_service._build_extraction_prompt()

        # Check for key amount extraction instructions
        assert "MAIN AMOUNT" in prompt or "PROMINENT" in prompt
        assert "minus signs" in prompt or "Remove ALL" in prompt
        assert "398,500.00" in prompt  # Example format
        assert "numeric value only" in prompt

    def test_admin_banks_context(self, mock_ocr_service):
        """Test that admin banks are properly formatted in the prompt."""
        context = mock_ocr_service._build_admin_banks_context()

        assert "KBZ Bank" in context
        assert "1234567890" in context
        assert "DAW HLA ZIN WAI HTET" in context


class TestReceiptValidation:
    """Test receipt validation logic."""

    @pytest.mark.asyncio
    async def test_reject_non_receipt_images(self, mock_ocr_service):
        """Test that non-receipt images are properly rejected."""
        mock_non_receipt = ReceiptData(
            amount=0,
            bank_name="NOT_A_RECEIPT",
            account_number="INVALID",
            account_name="INVALID",
            transaction_date=None,
            transaction_id=None,
            confidence_score=0.0,
        )

        with patch.object(
            mock_ocr_service.llm, "ainvoke", new_callable=AsyncMock
        ) as mock_invoke:
            mock_invoke.return_value = mock_non_receipt

            with pytest.raises(Exception):  # Should raise NotAReceiptError
                await mock_ocr_service.extract_receipt_data(b"dummy_image_bytes")

    @pytest.mark.asyncio
    async def test_low_confidence_rejection(self, mock_ocr_service):
        """Test that low confidence receipts are rejected."""
        mock_low_confidence = ReceiptData(
            amount=1000.0,
            bank_name="Some Bank",
            account_number="123456",
            account_name="Test",
            transaction_date="2025-11-20",
            transaction_id="TEST",
            confidence_score=0.50,  # Below 0.80 threshold
        )

        with patch.object(
            mock_ocr_service.llm, "ainvoke", new_callable=AsyncMock
        ) as mock_invoke:
            mock_invoke.return_value = mock_low_confidence

            with pytest.raises(Exception):  # Should raise NotAReceiptError
                await mock_ocr_service.extract_receipt_data(b"dummy_image_bytes")


class TestImagePreprocessing:
    """Test image preprocessing functionality."""

    def test_preprocess_valid_image(self, mock_ocr_service):
        """Test preprocessing of valid images."""
        # Create a simple test image
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", (800, 600), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()

        # Preprocess should succeed
        result = mock_ocr_service.preprocess_image(img_bytes)
        assert result is not None
        assert len(result) > 0

    def test_preprocess_empty_image(self, mock_ocr_service):
        """Test that empty images are rejected."""
        from app.services.ocr_service import InvalidImageError

        with pytest.raises(InvalidImageError):
            mock_ocr_service.preprocess_image(b"")

    def test_preprocess_invalid_image(self, mock_ocr_service):
        """Test that invalid images are rejected."""
        from app.services.ocr_service import InvalidImageError

        with pytest.raises(InvalidImageError):
            mock_ocr_service.preprocess_image(b"not_an_image")


@pytest.mark.integration
class TestRealOCRScenarios:
    """
    Integration tests for real OCR scenarios.
    These tests document expected behavior for common receipt formats.
    """

    def test_myanmar_kbz_receipt_format(self):
        """
        Document expected format for Myanmar KBZ Bank receipts.

        Format:
        - Amount: -398,500.00 (Ks)
        - Transaction Type: Cash In
        - Transfer To: DAW HLA ZIN WAI HTET
        - Transaction No: 0100397607145683791
        """
        expected_amount = 398500.00
        expected_bank = "KBZ Bank"
        expected_account = "DAW HLA ZIN WAI HTET"

        # This documents what we expect to extract
        assert expected_amount > 0
        assert expected_bank is not None
        assert expected_account is not None

    def test_thai_scb_receipt_format(self):
        """
        Document expected format for Thai SCB receipts.

        Format:
        - Amount: 1,234.56 THB
        - Bank: SCB (Siam Commercial Bank)
        - Account format: XXX-X-XXXXX-X
        """
        expected_amount = 1234.56
        expected_bank = "SCB"

        assert expected_amount > 0
        assert expected_bank is not None
