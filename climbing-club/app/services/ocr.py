"""פענוח צילום מסך של אישור תשלום (שלב 5).

הפענוח מפיק הצעה בלבד. התשלום נשמר רק לאחר שהמשתמשת בודקת ומאשרת את הנתונים בטופס.
ללא מפתח ANTHROPIC_API_KEY המערכת מציגה טופס ריק להזנה ידנית.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import config

FIELDS = ["paid_on", "amount", "payer_name", "recipient", "reference", "method", "bank_details", "extra"]

_PROMPT = """זהו צילום מסך של אישור תשלום או אסמכתה בנקאית (בעברית או באנגלית).
חלץ ממנו את הפרטים הבאים והחזר JSON בלבד, ללא טקסט נוסף:
{
  "paid_on": "תאריך התשלום בפורמט YYYY-MM-DD או null",
  "amount": מספר (שקלים חדשים) או null,
  "payer_name": "שם המשלם או null",
  "recipient": "שם מקבל התשלום אם מופיע או null",
  "reference": "מספר אסמכתא/אישור או null",
  "method": "אחד מ: bank_transfer, bit, paybox, credit_card, cash, check, other או null",
  "bank_details": "פרטי חשבון בנק אם מופיעים או null",
  "extra": "מידע נוסף שעשוי לסייע בשיוך התשלום או null",
  "confidence": "high | medium | low",
  "unclear": true אם התמונה מטושטשת או שחלק מהפרטים לא ניתנים לקריאה
}"""


@dataclass
class Extraction:
    ok: bool
    fields: dict = field(default_factory=dict)
    confidence: str = "low"
    unclear: bool = True
    error: str = ""


def available() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def extract(path: Path) -> Extraction:
    if not available():
        return Extraction(ok=False, error="פענוח אוטומטי אינו מוגדר (חסר ANTHROPIC_API_KEY) – יש להזין את הפרטים ידנית")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    if media_type not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        return Extraction(ok=False, error="יש להעלות קובץ תמונה (PNG/JPG/WEBP)")
    try:
        import anthropic
    except ImportError:
        return Extraction(ok=False, error="חבילת anthropic אינה מותקנת")
    data = base64.standard_b64encode(path.read_bytes()).decode()
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        resp = client.messages.create(
            model=config.OCR_MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
    except anthropic.RateLimitError:
        return Extraction(ok=False, error="השירות עמוס – נסו שוב בעוד רגע או הזינו ידנית")
    except anthropic.APIStatusError as e:
        return Extraction(ok=False, error=f"שגיאת שירות הפענוח ({e.status_code})")
    except anthropic.APIConnectionError:
        return Extraction(ok=False, error="אין תקשורת לשירות הפענוח")
    if resp.stop_reason == "refusal":
        return Extraction(ok=False, error="שירות הפענוח לא הצליח לעבד את התמונה – יש להזין ידנית")
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return Extraction(ok=False, error="לא התקבלה תשובה מובנית – יש להזין ידנית")
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return Extraction(ok=False, error="תשובת הפענוח אינה תקינה – יש להזין ידנית")
    fields = {k: parsed.get(k) for k in FIELDS}
    if isinstance(fields.get("amount"), str):
        try:
            fields["amount"] = float(re.sub(r"[^\d.]", "", fields["amount"]))
        except ValueError:
            fields["amount"] = None
    return Extraction(
        ok=True,
        fields=fields,
        confidence=str(parsed.get("confidence", "low")),
        unclear=bool(parsed.get("unclear", False)),
    )
