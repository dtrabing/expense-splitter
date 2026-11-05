import pytest

from splitter import (
    Expense,
    SplitError,
    expenses_from_records,
    fmt,
    parse_amount,
    parse_expenses,
    parse_participants,
    settle,
    split_expenses,
    summarize,
)


def test_parse_amount_handles_dollars_commas_and_rounding():
    assert parse_amount("12.50") == 1250
    assert parse_amount("$1,234") == 123400
    assert parse_amount(25.5) == 2550
    assert parse_amount(3) == 300
    assert parse_amount("0.005") == 1  # rounds half-up to the cent


@pytest.mark.parametrize("bad", ["", "abc", "-5", "nan", "$"])
def test_parse_amount_rejects_junk(bad):
    with pytest.raises(SplitError):
        parse_amount(bad)


def test_parse_expenses_skips_blank_lines_and_comments():
    text = "# who paid what\nAlice 60 groceries\n\nBob 25.50 gas\n"
    assert parse_expenses(text) == [
        Expense("Alice", 6000, "groceries"),
        Expense("Bob", 2550, "gas"),
    ]


def test_parse_expenses_reports_the_bad_line():
    with pytest.raises(SplitError, match="line 2"):
        parse_expenses("Alice 10\nBob ten\n")
    with pytest.raises(SplitError, match="line 1"):
        parse_expenses("Alice")


def test_expenses_from_records_validates_each_record():
    assert expenses_from_records([{"payer": "Alice", "amount": "12.5", "description": "x"}]) == [
        Expense("Alice", 1250, "x")
    ]
    with pytest.raises(SplitError, match="expense 1: payer"):
        expenses_from_records([{"amount": 5}])
    with pytest.raises(SplitError, match="expense 1: amount"):
        expenses_from_records([{"payer": "Alice"}])
    with pytest.raises(SplitError, match="list"):
        expenses_from_records("Alice 5")


def test_parse_participants_accepts_strings_and_lists():
    assert parse_participants("Alice, Bob,,Carol ") == ["Alice", "Bob", "Carol"]
    assert parse_participants(["Alice", " Bob "]) == ["Alice", "Bob"]
    assert parse_participants(None) == []


def test_summarize_balances_sum_to_zero_and_spread_odd_cents():
    rows = summarize([Expense("Alice", 1000)], ["Alice", "Bob", "Carol"])
    assert [row["share_cents"] for row in rows] == [334, 333, 333]
    assert sum(row["balance_cents"] for row in rows) == 0


def test_summarize_merges_names_case_insensitively():
    rows = summarize([Expense("alice", 500), Expense("Alice", 500)], ["Bob"])
    assert [row["name"] for row in rows] == ["Bob", "alice"]
    assert rows[1]["paid_cents"] == 1000


def test_summarize_requires_someone():
    with pytest.raises(SplitError):
        summarize([], [])


def test_settle_clears_every_balance_with_few_transfers():
    balances = {"Alice": 4116, "Bob": -783, "Carol": -3333}
    transfers = settle(balances)
    assert len(transfers) <= len(balances) - 1
    for transfer in transfers:
        balances[transfer.sender] += transfer.cents
        balances[transfer.receiver] -= transfer.cents
    assert all(value == 0 for value in balances.values())


def test_settle_when_everyone_is_even():
    assert settle({"Alice": 0, "Bob": 0}) == []


def test_split_expenses_end_to_end():
    expenses = parse_expenses("Alice 60 groceries\nBob 25.50 gas\nAlice 14.50 snacks")
    result = split_expenses(expenses, ["Alice", "Bob", "Carol"])
    assert result["total"] == "100.00"
    assert [person["name"] for person in result["people"]] == ["Alice", "Bob", "Carol"]
    assert result["transfers"] == [
        {"from": "Carol", "to": "Alice", "cents": 3333, "amount": "33.33"},
        {"from": "Bob", "to": "Alice", "cents": 783, "amount": "7.83"},
    ]


def test_fmt():
    assert fmt(0) == "0.00"
    assert fmt(5) == "0.05"
    assert fmt(1250) == "12.50"
    assert fmt(-1250) == "-12.50"
