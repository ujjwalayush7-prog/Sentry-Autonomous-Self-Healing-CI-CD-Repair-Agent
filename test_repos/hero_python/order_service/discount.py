def calculate_discount(order_amount: float, tier: str) -> float:
    """
    Calculates discount amount to be deducted from the total order amount.
    VIP tier receives a 20% discount (0.20 * order_amount).
    GOLD tier receives a 10% discount (0.10 * order_amount).
    """
    if tier == "VIP":
        # BUG: Erroneously returns net price factor rather than deduction amount
        return order_amount * 0.8
    elif tier == "GOLD":
        return order_amount * 0.1
    return 0.0
