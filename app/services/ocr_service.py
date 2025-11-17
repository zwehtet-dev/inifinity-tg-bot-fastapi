"""
OCR service for extracting receipt information using OpenAI Vision API with Pydantic structured outputs.
Enhanced version with better error handling, caching, retry logic, and validation.
"""

import asyncio
import base64
import hashlib
import json
import logging
from io import BytesIO
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from PIL import Image
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import openai

from app.models.receipt import ReceiptData

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Base exception for OCR-related errors."""

    pass


class InvalidImageError(OCRError):
    """Exception raised when image format is invalid or corrupted."""

    pass


class RateLimitError(OCRError):
    """Exception raised when OpenAI API rate limit is exceeded."""

    pass


class OCRTimeoutError(OCRError):
    """Exception raised when OCR processing times out."""

    pass


class NotAReceiptError(OCRError):
    """Exception raised when image is not a valid receipt."""

    pass


class OCRService:
    """
    Enhanced OCR service for extracting structured data from receipt images.

    Features:
    - Pydantic structured outputs for reliable parsing
    - In-memory caching to avoid duplicate API calls
    - Automatic retry with exponential backoff
    - Image preprocessing and optimization
    - Admin bank account validation
    - Comprehensive error handling
    - Minimum confidence threshold validation
    """

    def __init__(
        self,
        openai_api_key: str,
        model: str = "gpt-4o-mini",
        admin_banks: list = None,
        enable_cache: bool = True,
        cache_ttl: int = 3600,
        min_confidence: float = 0.80,
    ):
        """
        Initialize OCR service with OpenAI API key.

        Args:
            openai_api_key: OpenAI API key for authentication
            model: OpenAI model to use (gpt-4o-mini is cost-effective and fast)
            admin_banks: List of admin bank accounts to validate against
            enable_cache: Enable in-memory caching of OCR results
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
            min_confidence: Minimum confidence score required (default: 0.75 = 75%)
        """
        self.openai_api_key = openai_api_key
        self.model = model
        self.admin_banks = admin_banks or []
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.min_confidence = min_confidence

        # In-memory cache: {image_hash: (result, timestamp)}
        self._cache: Dict[str, tuple[ReceiptData, datetime]] = {}

        # Initialize LangChain ChatOpenAI with structured output
        self.llm = ChatOpenAI(
            model=model, temperature=0, openai_api_key=openai_api_key, max_tokens=1500
        ).with_structured_output(ReceiptData)

        logger.info(
            f"OCR Service initialized with {model}, "
            f"cache={'enabled' if enable_cache else 'disabled'}, "
            f"min_confidence={min_confidence:.0%}"
        )
        if self.admin_banks:
            logger.info(
                f"Configured with {len(self.admin_banks)} admin bank accounts for validation"
            )

    def _build_admin_banks_context(self) -> str:
        """Build formatted text of admin bank accounts for the prompt."""
        if not self.admin_banks:
            return "No admin banks configured - validation disabled"

        banks_text = []
        for i, bank in enumerate(self.admin_banks, 1):
            bank_name = bank.get("bank_name", "Unknown")
            account_number = bank.get("account_number", "Unknown")
            account_name = bank.get("account_name", "Unknown")
            banks_text.append(f"{i}. {bank_name} - {account_number} - {account_name}")

        return "\n".join(banks_text)

    def update_admin_banks(self, admin_banks: list):
        """
        Update the list of admin bank accounts and clear cache.

        Args:
            admin_banks: List of admin bank account dictionaries
        """
        self.admin_banks = admin_banks
        self._cache.clear()  # Clear cache when admin banks change
        logger.info(f"Updated admin banks: {len(admin_banks)} accounts, cache cleared")

    def _compute_image_hash(self, image_bytes: bytes) -> str:
        """
        Compute SHA256 hash of image for caching.

        Args:
            image_bytes: Image bytes

        Returns:
            Hex string of image hash
        """
        return hashlib.sha256(image_bytes).hexdigest()

    def _get_cached_result(self, image_hash: str) -> Optional[ReceiptData]:
        """
        Get cached OCR result if available and not expired.

        Args:
            image_hash: Hash of the image

        Returns:
            Cached ReceiptData or None if not found/expired
        """
        if not self.enable_cache:
            return None

        if image_hash in self._cache:
            result, timestamp = self._cache[image_hash]
            age = datetime.now() - timestamp

            if age.total_seconds() < self.cache_ttl:
                logger.info(
                    f"Cache hit for image {image_hash[:12]}... (age: {age.total_seconds():.1f}s)"
                )
                return result
            else:
                # Expired, remove from cache
                del self._cache[image_hash]
                logger.debug(f"Cache expired for image {image_hash[:12]}...")

        return None

    def _cache_result(self, image_hash: str, result: ReceiptData):
        """
        Cache OCR result.

        Args:
            image_hash: Hash of the image
            result: ReceiptData to cache
        """
        if self.enable_cache:
            self._cache[image_hash] = (result, datetime.now())
            logger.debug(
                f"Cached result for image {image_hash[:12]}... (cache size: {len(self._cache)})"
            )

    def clear_cache(self):
        """Clear all cached OCR results."""
        self._cache.clear()
        logger.info("OCR cache cleared")

    def preprocess_image(
        self, image_bytes: bytes, max_size: tuple = (2048, 2048)
    ) -> bytes:
        """
        Preprocess image for OCR: validate, resize, and optimize.

        Args:
            image_bytes: Raw image bytes
            max_size: Maximum dimensions (width, height) for resizing

        Returns:
            Preprocessed image bytes

        Raises:
            InvalidImageError: If image cannot be processed
        """
        try:
            # Validate image bytes
            if not image_bytes or len(image_bytes) == 0:
                raise InvalidImageError("Image bytes are empty")

            # Open and verify image
            try:
                image = Image.open(BytesIO(image_bytes))
                image.verify()
                # Reopen after verify (verify closes the file)
                image = Image.open(BytesIO(image_bytes))
            except Exception as e:
                raise InvalidImageError(f"Cannot open or verify image: {e}")

            # Check minimum size
            if image.size[0] < 100 or image.size[1] < 100:
                raise InvalidImageError(
                    f"Image too small: {image.size}. Minimum size is 100x100"
                )

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
                logger.debug(f"Converted image from {image.mode} to RGB")
            elif image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            # Resize if image is too large (use thumbnail to maintain aspect ratio)
            original_size = image.size
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image from {original_size} to {image.size}")

            # Save to bytes with optimization
            output = BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
            processed_bytes = output.getvalue()

            # Validate output
            if not processed_bytes or len(processed_bytes) == 0:
                raise InvalidImageError("Processed image is empty")

            logger.debug(
                f"Image preprocessed: {len(image_bytes)} -> {len(processed_bytes)} bytes"
            )
            return processed_bytes

        except InvalidImageError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error preprocessing image: {e}")
            raise InvalidImageError(f"Image preprocessing failed: {e}")

    def encode_image_base64(self, image_bytes: bytes) -> str:
        """
        Encode image bytes to base64 string for API transmission.

        Args:
            image_bytes: Image bytes to encode

        Returns:
            Base64 encoded string
        """
        return base64.b64encode(image_bytes).decode("utf-8")

    def _build_extraction_prompt(self) -> str:
        """
        Build the OCR extraction prompt with admin bank validation.

        Returns:
            Formatted prompt string
        """
        admin_banks_text = self._build_admin_banks_context()

        prompt = f"""**FIRST: Verify this is a valid bank transfer receipt!**

Check if the image contains:
- Bank transfer/payment information
- Amount/money value
- Bank names or logos
- Account numbers
- Transaction details

**If this is NOT a bank transfer receipt (e.g., random photo, screenshot, meme, document), you MUST set:**
- amount: 0
- bank_name: "NOT_A_RECEIPT"
- account_number: "INVALID"
- account_name: "INVALID"
- confidence_score: 0.0

**If this IS a valid bank transfer receipt, proceed with extraction:**

**Admin Bank Accounts (Expected Recipients):**
{admin_banks_text}

**Extract the following from the receipt:**
- Transfer amount (numeric value only, no currency symbols or commas)
- Receiver Bank name (the bank receiving the money - use full name or common abbreviation)
- Receiver Account number (recipient's account number, may have some digits hidden with *)
- Receiver Account holder name (recipient's name as shown on receipt)
- Transaction date (if visible, format: YYYY-MM-DD or as shown)
- Transaction ID or reference number (if visible)

**CRITICAL: Extract RECEIVER/RECIPIENT information, NOT sender information!**

**Validation Rules:**
1. Bank Name Matching (Weight: 0.20 max):
   - Match common abbreviations (SCB = Siam Commercial Bank, BBL = Bangkok Bank, KBANK = Kasikorn Bank)
   - Case insensitive matching
   - Partial matches acceptable if clear
   - Score: 0.20 for perfect match, 0.10-0.15 for partial match, 0.01-0.05 for weak match

2. Account Number Matching (Weight: 0.50 max):
   - Some digits may be hidden with asterisks (*)
   - Match visible digits with admin account numbers
   - If at least 4 consecutive visible digits match, consider it valid
   - Score: 0.50 for perfect match, 0.30-0.40 for good match, 0.10-0.20 for partial match

3. Account Holder Name Matching (Weight: 0.30 max):
   - Case insensitive
   - Ignore prefixes like Mr., Mrs., Miss, Ms., Dr., MR, MISS
   - Allow partial matches (at least 70% similarity)
   - Ignore extra spaces or punctuation
   - Score: 0.30 for perfect match, 0.20-0.25 for good match, 0.05-0.15 for partial match

4. Confidence Score Calculation (REQUIRED):
   Calculate confidence_score by adding the scores from each field:
   - Account Number Score (0.01 to 0.50) - MOST IMPORTANT
   - Account Name Score (0.01 to 0.30) - IMPORTANT
   - Bank Name Score (0.01 to 0.20) - LESS IMPORTANT
   
   Total confidence_score = account_number_score + account_name_score + bank_name_score
   
   Examples:
   - Perfect match all fields: 0.50 + 0.30 + 0.20 = 1.00 (100%)
   - Good match: 0.40 + 0.25 + 0.15 = 0.80 (80%)
   - Partial match: 0.30 + 0.15 + 0.10 = 0.55 (55%)
   - Weak match: 0.10 + 0.05 + 0.05 = 0.20 (20%)
   - No match: 0.01 + 0.01 + 0.01 = 0.03 (3%)
   - NOT a receipt: 0.0 (0%)

**Important:**
- REJECT non-receipt images by setting bank_name="NOT_A_RECEIPT" and confidence_score=0.0
- Extract ONLY the recipient/destination account information
- Calculate confidence_score using the weighted scoring system above
- Account number matching is MOST important (50% weight)
- If the receipt does NOT match any admin account well, confidence will be low
- For amount, extract only the numeric value (e.g., 1000.50, not "1,000.50 THB")
- Look for keywords indicating success: "สำเร็จ", "Success", "Completed", "Complete"

Return the extracted data in valid JSON format matching the ReceiptData schema."""

        return prompt

    async def extract_receipt_data(
        self, image_bytes: bytes, timeout: int = 60, use_cache: bool = True
    ) -> Optional[ReceiptData]:
        """
        Extract structured data from receipt image using OpenAI Vision API.

        Args:
            image_bytes: Receipt image as bytes
            timeout: Timeout in seconds for API call
            use_cache: Whether to use cached results if available

        Returns:
            ReceiptData object with extracted information, or None if extraction fails

        Raises:
            InvalidImageError: If image is invalid or corrupted
            RateLimitError: If OpenAI API rate limit is exceeded
            OCRTimeoutError: If processing times out
            OCRError: For other OCR-related errors
        """
        try:
            # Preprocess image (raises InvalidImageError if invalid)
            processed_image = self.preprocess_image(image_bytes)

            # Check cache
            if use_cache:
                image_hash = self._compute_image_hash(processed_image)
                cached_result = self._get_cached_result(image_hash)
                if cached_result:
                    return cached_result

            # Encode image to base64
            image_base64 = self.encode_image_base64(processed_image)
            image_data_url = f"data:image/jpeg;base64,{image_base64}"

            # Build prompt
            prompt_text = self._build_extraction_prompt()

            # Log the prompt (without full image data)
            logger.info("=" * 80)
            logger.info("SENDING OCR REQUEST TO OPENAI")
            logger.info("=" * 80)
            logger.info(f"Model: {self.model}")
            logger.info(f"Image size: {len(processed_image)} bytes")
            logger.info(f"Admin banks: {len(self.admin_banks)}")
            logger.info("=" * 80)

            # Create message with image
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url, "detail": "high"},
                    },
                ]
            )

            # Invoke the model with timeout and structured output
            try:
                result = await asyncio.wait_for(
                    self.llm.ainvoke([message]), timeout=timeout
                )
            except asyncio.TimeoutError:
                raise OCRTimeoutError(
                    f"OCR processing timed out after {timeout} seconds"
                )

            # Validate result
            if not isinstance(result, ReceiptData):
                logger.error(f"Unexpected result type: {type(result)}")
                raise OCRError(f"Invalid result type: {type(result)}")

            # Check if this is actually a receipt
            if (
                result.bank_name == "NOT_A_RECEIPT"
                or result.account_number == "INVALID"
                or result.confidence_score == 0.0
            ):
                logger.warning("Image is not a valid bank transfer receipt")
                raise NotAReceiptError(
                    "This image does not appear to be a valid bank transfer receipt. "
                    "Please upload a clear photo of your transfer receipt showing the amount, "
                    "bank name, and account details."
                )

            # Additional validation: check for suspicious values
            if result.amount <= 0:
                logger.warning(f"Invalid amount detected: {result.amount}")
                raise NotAReceiptError(
                    "Could not find a valid transfer amount in this image. "
                    "Please upload a clear bank transfer receipt."
                )

            # Check minimum confidence threshold
            if result.confidence_score < self.min_confidence:
                logger.warning(
                    f"Confidence score {result.confidence_score:.0%} is below minimum threshold {self.min_confidence:.0%}"
                )
                raise NotAReceiptError(
                    f"Receipt validation confidence is too low ({result.confidence_score:.0%}).\n\n"
                    f"This receipt does not match our admin bank accounts well enough.\n"
                    f"Required confidence: {self.min_confidence:.0%}\n\n"
                    f"Possible reasons:\n"
                    f"• Receipt is for a different bank account\n"
                    f"• Image is unclear or partially visible\n"
                    f"• Not a valid transfer receipt\n\n"
                    f"Please upload a clear receipt showing transfer to one of our admin accounts."
                )

            # Match with admin banks to get bank ID
            matched_bank_id = self._find_matching_bank_id(result)
            if matched_bank_id:
                result.matched_bank_id = matched_bank_id
                logger.info(f"Matched admin bank ID: {matched_bank_id}")

            # Log the AI response
            logger.info("=" * 80)
            logger.info("OCR EXTRACTION SUCCESSFUL")
            logger.info("=" * 80)
            logger.info(f"Amount: {result.amount}")
            logger.info(f"Bank Name: {result.bank_name}")
            logger.info(f"Account Number: {result.account_number}")
            logger.info(f"Account Holder: {result.account_name}")
            logger.info(f"Transaction Date: {result.transaction_date}")
            logger.info(f"Transaction ID: {result.transaction_id}")
            logger.info(f"Confidence Score: {result.confidence_score:.2f}")
            logger.info(f"Matched Bank ID: {result.matched_bank_id}")
            logger.info("=" * 80)

            # Cache the result
            if use_cache:
                self._cache_result(image_hash, result)

            return result

        except InvalidImageError:
            logger.error("Invalid image provided for OCR")
            raise
        except OCRTimeoutError:
            logger.error("OCR processing timed out")
            raise
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise RateLimitError(f"Rate limit exceeded: {e}")
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise OCRError(f"OpenAI API error: {e}")
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}")
            raise OCRError(f"Connection error: {e}")
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {e}")
            raise OCRError(f"Authentication error: {e}")
        except NotAReceiptError:
            # Re-raise NotAReceiptError without wrapping
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error extracting receipt data: {e}", exc_info=True
            )
            raise OCRError(f"OCR extraction failed: {e}")

    def _find_matching_bank_id(self, receipt_data: ReceiptData) -> Optional[int]:
        """
        Find the matching admin bank ID based on receipt data.

        Args:
            receipt_data: Extracted receipt data

        Returns:
            Bank ID if match found, None otherwise
        """
        if not self.admin_banks:
            return None

        # Try to find exact or close match
        for bank in self.admin_banks:
            bank_id = bank.get("id")
            bank_name = bank.get("bank_name", "").lower()
            account_number = bank.get("account_number", "")
            account_name = bank.get("account_name", "").lower()

            receipt_bank = receipt_data.bank_name.lower()
            receipt_account = receipt_data.account_number
            receipt_name = receipt_data.account_name.lower()

            # Check if bank names match (fuzzy)
            bank_match = bank_name in receipt_bank or receipt_bank in bank_name

            # Check if account numbers match (allowing for masked digits)
            account_match = False
            if account_number and receipt_account:
                # Remove common separators
                clean_admin = account_number.replace("-", "").replace(" ", "")
                clean_receipt = (
                    receipt_account.replace("-", "").replace(" ", "").replace("*", "")
                )

                # Check if receipt account contains admin account digits
                if clean_receipt in clean_admin or clean_admin in clean_receipt:
                    account_match = True

            # Check if account names match (fuzzy)
            name_match = account_name in receipt_name or receipt_name in account_name

            # If we have a good match, return this bank ID
            if (bank_match and account_match) or (account_match and name_match):
                logger.info(f"Matched receipt to admin bank ID {bank_id}: {bank_name}")
                return bank_id

        logger.warning("Could not find matching admin bank ID")
        return None

    async def extract_with_retry(
        self,
        image_bytes: bytes,
        max_retries: int = 2,
        base_delay: float = 1.0,
        use_cache: bool = True,
    ) -> Optional[ReceiptData]:
        """
        Extract receipt data with retry logic and exponential backoff for transient failures.

        Args:
            image_bytes: Receipt image as bytes
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            use_cache: Whether to use cached results if available

        Returns:
            ReceiptData object or None if all attempts fail
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self.extract_receipt_data(
                    image_bytes, use_cache=use_cache
                )
                if result:
                    if attempt > 0:
                        logger.info(
                            f"✓ OCR succeeded on attempt {attempt + 1}/{max_retries + 1}"
                        )
                    return result

            except InvalidImageError as e:
                # Don't retry for invalid images
                logger.error(f"✗ Invalid image, not retrying: {e}")
                last_error = e
                break

            except NotAReceiptError as e:
                # Don't retry for non-receipt images
                logger.error(f"✗ Not a receipt, not retrying: {e}")
                last_error = e
                break

            except RateLimitError as e:
                # Retry with longer delay for rate limits
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (3**attempt)  # Longer backoff for rate limits
                    logger.warning(
                        f"⚠ Rate limit hit on attempt {attempt + 1}/{max_retries + 1}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"✗ Rate limit persists after {max_retries + 1} attempts"
                    )

            except OCRTimeoutError as e:
                # Retry timeouts
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"⚠ Timeout on attempt {attempt + 1}/{max_retries + 1}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"✗ Timeout persists after {max_retries + 1} attempts")

            except OCRError as e:
                # Retry general OCR errors
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"⚠ OCR error on attempt {attempt + 1}/{max_retries + 1}: {e}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"✗ OCR failed after {max_retries + 1} attempts: {e}")

            except Exception as e:
                # Unexpected errors
                last_error = e
                logger.error(
                    f"✗ Unexpected error on attempt {attempt + 1}/{max_retries + 1}: {e}"
                )
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                else:
                    break

        # Log final failure
        logger.error(
            f"✗ All OCR attempts failed after {max_retries + 1} tries. "
            f"Last error: {last_error}"
        )
        return None

    def should_fallback_to_manual_review(self, error: Exception) -> bool:
        """
        Determine if OCR failure should fallback to manual admin review.

        Args:
            error: The exception that occurred

        Returns:
            True if should fallback to manual review, False otherwise
        """
        # Don't fallback for non-receipt images - reject immediately
        if isinstance(error, NotAReceiptError):
            return False

        # Always fallback for these error types
        if isinstance(error, (InvalidImageError, OCRTimeoutError)):
            return True

        # Fallback for rate limits (admin can review while waiting)
        if isinstance(error, RateLimitError):
            return True

        # Fallback for general OCR errors
        if isinstance(error, OCRError):
            return True

        return True  # Default to manual review for safety

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if not self.enable_cache:
            return {"enabled": False}

        now = datetime.now()
        valid_entries = 0
        expired_entries = 0

        for image_hash, (result, timestamp) in self._cache.items():
            age = now - timestamp
            if age.total_seconds() < self.cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "enabled": True,
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_ttl": self.cache_ttl,
        }
