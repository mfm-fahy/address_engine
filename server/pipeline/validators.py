import re

from pipeline.normalizers import normalize_phone


_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]{2,}$")


def _is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10


def validate_order(order: dict, source: str) -> list[str]:
    errors = []
    order_id = (
        order.get("id")
        or order.get("transactionId")
        or order.get("_id")
        or order.get("orderId")
        or ""
    )
    if not order_id and source != "f3":
        errors.append(f"Missing order_id for source={source}")
    phone_raw = ""
    if source == "instaxbot":
        phone_raw = order.get("customer", {}).get("phone", "")
    elif source == "f3":
        phone_raw = order.get("customerPhone", "")
        if not phone_raw:
            sa = order.get("shippingAddress", {})
            phone_raw = sa.get("phone", "")
    else:
        phone_raw = order.get("customerPhone", "") or order.get("customerDetails", {}).get("phone", "")
    phone = normalize_phone(phone_raw)
    if phone and not _is_valid_phone(phone):
        errors.append(f"Invalid phone '{phone}' for order_id={order_id}, source={source}")
    for field in ("orderValue", "totalAmount", "total", "amount"):
        val = order.get(field)
        if val is not None:
            break
    else:
        if source not in ("gowhats",):
            status = (order.get("status", "") or "").lower()
            if source == "f3" or status not in ("pending", "cancelled"):
                errors.append(f"Missing amount field for order_id={order_id}, source={source}")
    return errors


def validate_bill_customer(cust: dict) -> list[str]:
    errors = []
    cid = cust.get("customer_id") or cust.get("id")
    if not cid:
        errors.append("Missing customer id in bill customer record")
    phone = normalize_phone(str(cust.get("phone", "")))
    if not phone:
        errors.append(f"Missing phone for bill customer id={cid}")
    if cust.get("email") and not _EMAIL_RE.match(str(cust.get("email", ""))):
        errors.append(f"Invalid email for bill customer id={cid}")
    return errors


def validate_bill_tx(tx: dict) -> list[str]:
    errors = []
    tx_id = tx.get("order_id") or tx.get("id") or tx.get("bill_id")
    if not tx_id:
        errors.append("Missing id in bill transaction")
    phone = normalize_phone(str(tx.get("phone", "")))
    if not phone:
        cid = tx.get("customer_id") or tx.get("customerId") or ""
        if not cid:
            errors.append(f"Missing phone and customerId for bill tx id={tx_id}")
    try:
        amount = tx.get("amount") or tx.get("totalPrice")
        if amount:
            float(amount)
    except (ValueError, TypeError):
        errors.append(f"Invalid amount for bill tx id={tx_id}")
    return errors
