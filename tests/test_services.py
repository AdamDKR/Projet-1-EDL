import pytest

from services import ValidationError, compute_balances, format_cents, parse_amount


@pytest.mark.parametrize(
    "value, expected",
    [(30, 3000), ("30", 3000), ("12,5", 1250), ("12.50", 1250), (19.99, 1999), ("0,01", 1)],
)
def test_parse_amount(value, expected):
    assert parse_amount(value) == expected


def test_too_long_amount_is_rejected():
    with pytest.raises(ValidationError):
        parse_amount("9" * 5000)


@pytest.mark.parametrize(
    "cents, expected", [(2000, "+20.00"), (-333, "-3.33"), (-5, "-0.05"), (0, "0.00")]
)
def test_format_signed_cents(cents, expected):
    assert format_cents(cents, signed=True) == expected


@pytest.mark.parametrize("amount", range(1, 200))
def test_balances_always_sum_to_zero(amount):
    expenses = [
        {"amount_cents": amount, "payer_id": 1, "participants": [2, 3, 4]},
        {"amount_cents": amount + 1, "payer_id": 2, "participants": [4, 1, 3, 2]},
    ]
    assert sum(compute_balances([1, 2, 3, 4], expenses).values()) == 0
