import re

# Order matters: card and Aadhaar numbers before the looser phone pattern
PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?:\+91[ -]?|\b0)?\b[6-9]\d{4}[ -]?\d{5}\b")),
]


def mask(text: str) -> str:
    """Replace emails, phone, card, Aadhaar and PAN numbers with [EMAIL], [PHONE] and so on."""
    for label, pattern in PATTERNS:
        text = pattern.sub(f"[{label}]", text)
    return text