#!/usr/bin/env python3
"""
Test script for OCR amount detection.
Usage: python scripts/test_ocr_amount.py <image_path>
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_ocr_amount(image_path: str):
    """Test OCR amount extraction from an image."""
    import base64
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    from app.models.receipt import ReceiptData
    from app.config import get_settings

    # Load settings
    settings = get_settings()

    # Read image
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    print(f"📸 Testing OCR with image: {image_path}")
    print(f"   Image size: {len(image_bytes)} bytes")
    print()

    # Encode image
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{image_base64}"

    # Simplified prompt for staff receipts
    prompt = """You are analyzing a bank transfer receipt. Your ONLY task is to find and extract the MAIN TRANSFER AMOUNT.

**STEP 1: Find the MAIN AMOUNT**
Look for the LARGEST, most PROMINENT number on the receipt. This is usually:
- Displayed at the TOP or CENTER of the screen
- The biggest text/number
- Near words like: "Payment Successful", "Transfer Complete", "โอนเงินสำเร็จ", "ငွေလွှဲပြီးပါပြီ"

**STEP 2: Extract the NUMBER**
Remove ALL formatting and extract ONLY the numeric value:

**Myanmar Format Examples:**
- "-398,500.00 (Ks)" → Extract: 398500.00
- "-398,500.00 Ks" → Extract: 398500.00
- "398,500 MMK" → Extract: 398500
- "398500 K" → Extract: 398500

**Thai Format Examples:**
- "1,234.56 บาท" → Extract: 1234.56
- "1,234.56 THB" → Extract: 1234.56
- "1,234.56 ฿" → Extract: 1234.56

**CRITICAL RULES:**
1. Remove MINUS signs (-) - they just mean "outgoing"
2. Remove COMMAS (,)
3. Remove ALL currency symbols: Ks, K, MMK, THB, ฿, บาท, ကျပ်
4. Keep ONLY the number (with decimal point if present)
5. Look for the MAIN amount, NOT fees or commissions

**Common Receipt Layouts:**

Myanmar KBZ Bank:
```
Payment Successful
-398,500.00 (Ks)  ← THIS IS THE MAIN AMOUNT
Transaction No: 0100397607145683791
Amount: -398,500.00 Ks  ← Same amount repeated
Commission: 0.00 Ks  ← IGNORE this
```
Extract: 398500.00

Thai Banking:
```
โอนเงินสำเร็จ
1,234.56 บาท  ← THIS IS THE MAIN AMOUNT
เลขที่บัญชี: XXX-X-XXXXX-X
```
Extract: 1234.56

**What to IGNORE:**
- Commission/Fee amounts (usually 0.00 or small)
- Account numbers
- Transaction IDs
- Dates and times
- Balance amounts

**If you find the amount, return:**
{
    "amount": <the_numeric_value>,
    "bank_name": "STAFF_RECEIPT",
    "account_number": "N/A",
    "account_name": "N/A",
    "confidence_score": 1.0
}

**If you CANNOT find a clear amount, return:**
{
    "amount": 0,
    "bank_name": "UNCLEAR",
    "account_number": "N/A",
    "account_name": "N/A",
    "confidence_score": 0.0
}

Remember: Find the BIGGEST, most PROMINENT number near "Payment Successful" or similar success message!"""

    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=settings.openai_api_key,
        max_tokens=500,
    ).with_structured_output(ReceiptData)

    # Create message
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_data_url, "detail": "high"},
            },
        ]
    )

    print("🔍 Sending to OpenAI GPT-4o-mini...")
    print()

    try:
        # Invoke with timeout
        result = await asyncio.wait_for(llm.ainvoke([message]), timeout=30)

        print("=" * 80)
        print("OCR RESULT")
        print("=" * 80)
        if result:
            print(f"✅ Amount: {result.amount}")
            print(f"   Bank Name: {result.bank_name}")
            print(f"   Account Number: {result.account_number}")
            print(f"   Account Name: {result.account_name}")
            print(f"   Transaction Date: {result.transaction_date}")
            print(f"   Transaction ID: {result.transaction_id}")
            print(f"   Confidence: {result.confidence_score}")
            print()

            if result.amount > 0:
                print(f"✅ SUCCESS: Extracted amount = {result.amount:,.2f}")
            else:
                print("❌ FAILED: Amount is 0 or not found")
        else:
            print("❌ FAILED: Result is None")
        print("=" * 80)

    except asyncio.TimeoutError:
        print("❌ ERROR: Request timed out after 30 seconds")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_ocr_amount.py <image_path>")
        print()
        print("Example:")
        print("  python scripts/test_ocr_amount.py receipt.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found: {image_path}")
        sys.exit(1)

    # Run async test
    asyncio.run(test_ocr_amount(image_path))


if __name__ == "__main__":
    main()
