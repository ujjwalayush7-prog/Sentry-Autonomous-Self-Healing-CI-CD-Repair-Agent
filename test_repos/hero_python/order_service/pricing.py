from .discount import calculate_discount


def calculate_final_price(order_amount: float, tier: str, tax_rate: float = 0.05) -> float:
    """
    Computes final customer invoice price after deducting tier discounts and applying tax.
    """
    if order_amount < 0:
        raise ValueError("Order amount cannot be negative")

    discount = calculate_discount(order_amount, tier)
    discounted_subtotal = order_amount - discount
    tax = discounted_subtotal * tax_rate
    return round(discounted_subtotal + tax, 2)
