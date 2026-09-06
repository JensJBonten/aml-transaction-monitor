def require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    return value


def format_transaction_id(transaction_id: str) -> str:
    number = int(transaction_id.split("-")[-1])
    return f"Case {number}"


def format_customer_id(customer_id: str) -> str:
    number = int(customer_id.split("-")[-1])
    return f"Customer {number:03d}"


def format_nok(amount: float, decimals: int = 0) -> str:
    formatted_amount = f"{amount:,.{decimals}f}".replace(",", " ")
    return f"NOK {formatted_amount}"
