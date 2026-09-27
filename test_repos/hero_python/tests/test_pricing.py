import pytest
from order_service.pricing import calculate_final_price


def test_regular_customer_no_discount():
    # Regular customer: no discount -> $100 + 5% tax ($5.0) = $105.0
    price = calculate_final_price(100.0, "REGULAR", 0.05)
    assert price == 105.0


def test_gold_customer_discount():
    # Gold customer: 10% discount ($10.0) -> $90 subtotal + 5% tax ($4.5) = $94.5
    price = calculate_final_price(100.0, "GOLD", 0.05)
    assert price == 94.5


def test_vip_customer_discount():
    # VIP customer: 20% discount ($20.0) -> $80 subtotal + 5% tax ($4.0) = $84.0
    price = calculate_final_price(100.0, "VIP", 0.05)
    assert price == 84.0, f"Expected VIP final bill to be 84.0, but received {price}"


def test_zero_amount_order():
    price = calculate_final_price(0.0, "VIP", 0.05)
    assert price == 0.0
