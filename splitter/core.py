"""Pure functions for splitting shared expenses and settling up.

Money is handled as integer cents so every sum is exact and the balances
always add up to zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence


class SplitError(ValueError):
    """Raised when the input cannot be turned into a valid split."""


@dataclass(frozen=True)
class Expense:
    payer: str
    cents: int
    description: str = ""


@dataclass(frozen=True)
class Transfer:
    sender: str
    receiver: str
    cents: int


def fmt(cents: int) -> str:
    """1250 -> '12.50', -5 -> '-0.05'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def parse_amount(value) -> int:
    """Turn '12.50', '$1,234', 25.5 or 3 into cents. Rounds half-up to the cent."""
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned:
        raise SplitError("amount is missing")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise SplitError(f"'{value}' is not a valid amount") from None
    if amount.is_nan() or amount.is_infinite():
        raise SplitError(f"'{value}' is not a valid amount")
    if amount < 0:
        raise SplitError(f"amount '{value}' cannot be negative")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_expenses(text: str) -> List[Expense]:
    """Parse one expense per line: ``name amount [description]``.

    Blank lines and lines starting with ``#`` are ignored. Errors name the line.
    """
    expenses: List[Expense] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            raise SplitError(
                f"line {lineno}: expected 'name amount description', got '{line}'"
            )
        try:
            cents = parse_amount(parts[1])
        except SplitError as exc:
            raise SplitError(f"line {lineno}: {exc}") from exc
        description = parts[2] if len(parts) == 3 else ""
        expenses.append(Expense(payer=parts[0], cents=cents, description=description))
    return expenses


def expenses_from_records(records) -> List[Expense]:
    """Build expenses from JSON-style objects: {"payer": "Alice", "amount": 12.5}."""
    if not isinstance(records, list):
        raise SplitError("'expenses' must be a string or a list of objects")
    expenses: List[Expense] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise SplitError(f"expense {index}: expected an object with payer and amount")
        payer = str(record.get("payer", "")).strip()
        if not payer:
            raise SplitError(f"expense {index}: payer is required")
        if "amount" not in record:
            raise SplitError(f"expense {index}: amount is required")
        try:
            cents = parse_amount(record["amount"])
        except SplitError as exc:
            raise SplitError(f"expense {index}: {exc}") from exc
        description = str(record.get("description") or "")
        expenses.append(Expense(payer=payer, cents=cents, description=description))
    return expenses


def parse_participants(value) -> List[str]:
    """Accept 'Alice, Bob' or ['Alice', 'Bob'] (or nothing) and return clean names."""
    if value is None:
        return []
    items = value.replace("\n", ",").split(",") if isinstance(value, str) else value
    return [str(item).strip() for item in items if str(item).strip()]


def _people(expenses: Iterable[Expense], participants: Sequence[str]) -> Dict[str, str]:
    """Unique people keyed case-insensitively; the first spelling seen is kept."""
    seen: Dict[str, str] = {}
    for name in list(participants) + [expense.payer for expense in expenses]:
        seen.setdefault(name.casefold(), name)
    return seen


def summarize(expenses: Sequence[Expense], participants: Sequence[str] = ()) -> List[dict]:
    """Per-person paid / fair share / balance in cents.

    The total is split equally; any leftover cents go to the first people
    listed, so the balances always sum to exactly zero. A positive balance
    means the person is owed money, negative means they owe.
    """
    people = _people(expenses, participants)
    if not people:
        raise SplitError("add at least one expense or participant")
    paid = {key: 0 for key in people}
    for expense in expenses:
        paid[expense.payer.casefold()] += expense.cents
    total = sum(paid.values())
    share, remainder = divmod(total, len(people))
    rows = []
    for position, (key, name) in enumerate(people.items()):
        person_share = share + (1 if position < remainder else 0)
        rows.append(
            {
                "name": name,
                "paid_cents": paid[key],
                "share_cents": person_share,
                "balance_cents": paid[key] - person_share,
            }
        )
    return rows


def settle(balances: Dict[str, int]) -> List[Transfer]:
    """Greedy settlement: biggest debtor pays biggest creditor until everyone is even.

    Produces at most ``len(balances) - 1`` transfers.
    """
    creditors = sorted(
        ((name, amount) for name, amount in balances.items() if amount > 0),
        key=lambda item: (-item[1], item[0]),
    )
    debtors = sorted(
        ((name, -amount) for name, amount in balances.items() if amount < 0),
        key=lambda item: (-item[1], item[0]),
    )
    transfers: List[Transfer] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, owes = debtors[i]
        creditor, owed = creditors[j]
        amount = min(owes, owed)
        transfers.append(Transfer(sender=debtor, receiver=creditor, cents=amount))
        debtors[i] = (debtor, owes - amount)
        creditors[j] = (creditor, owed - amount)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


def split_expenses(expenses: Sequence[Expense], participants: Sequence[str] = ()) -> dict:
    """The whole pipeline: balances plus the payments that settle them."""
    rows = summarize(expenses, participants)
    transfers = settle({row["name"]: row["balance_cents"] for row in rows})
    total = sum(row["paid_cents"] for row in rows)
    return {
        "total_cents": total,
        "total": fmt(total),
        "people": [
            {
                **row,
                "paid": fmt(row["paid_cents"]),
                "share": fmt(row["share_cents"]),
                "balance": fmt(row["balance_cents"]),
            }
            for row in rows
        ],
        "transfers": [
            {
                "from": transfer.sender,
                "to": transfer.receiver,
                "cents": transfer.cents,
                "amount": fmt(transfer.cents),
            }
            for transfer in transfers
        ],
    }
