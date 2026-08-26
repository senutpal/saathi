"""Money helpers: integer paise/cents end-to-end, never floats.

Floats cannot represent 0.1 (``19.99 * 100 == 1998.999…``) so every stored
amount is an int of cents; parsing goes through ``Decimal(str)`` which is
exact where ``Decimal(float)`` would bake the drift back in.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MAX_DECIMALS = 2


def parse_to_cents(raw: str) -> int:
    """Exact string -> cents; raises ValueError on garbage or >2 decimals."""
    try:
        value = Decimal(raw.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {raw!r}") from exc
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > MAX_DECIMALS:
        raise ValueError(f"at most {MAX_DECIMALS} decimal places")
    cents = int(value.scaleb(2))
    if cents < 0:
        raise ValueError("amount must be positive")
    return cents


def format_cents(cents: int, *, symbol: str = "₹") -> str:
    """199 -> '₹1.99'; display-only, never round-trips through float."""
    rupees, paise = divmod(cents, 100)
    return f"{symbol}{rupees}.{paise:02d}"
