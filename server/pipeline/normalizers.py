import re
from datetime import datetime


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = str(phone).strip()
    phone = re.sub(r"[\s\-\(\)\+]", "", phone)
    phone = re.sub(r"^0+", "", phone)
    if phone.startswith("91") and len(phone) > 10:
        phone = phone[2:]
    if phone.startswith("1") and len(phone) > 10:
        phone = phone[1:]
    phone = phone[-10:] if len(phone) >= 10 else phone
    return phone


_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def normalize_date(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def normalize_status(status: str) -> str:
    return (status or "").strip().lower()


def build_billzzy_address(cust: dict) -> str:
    addr = cust.get("address", "") or ""
    if addr:
        return addr
    parts = [cust.get("flatNo", ""), cust.get("street", ""),
             cust.get("district", ""), cust.get("state", ""),
             cust.get("pincode", "")]
    return ", ".join(p for p in parts if p)


def extract_source_phone(source: str, order: dict) -> str:
    if source == "gowhats":
        return order.get("customerPhone", "") or order.get("customerDetails", {}).get("phone", "")
    elif source == "instaxbot":
        return order.get("customer", {}).get("phone", "")
    elif source == "f3":
        cust = order.get("customerDetails", {})
        return cust.get("phone", order.get("customerPhone", ""))
    return ""


def extract_source_name(source: str, order: dict) -> str:
    if source == "gowhats":
        return order.get("customerDetails", {}).get("name", "")
    elif source == "instaxbot":
        return order.get("customer", {}).get("name", "")
    elif source == "f3":
        cust = order.get("customerDetails", {})
        return cust.get("name", order.get("customerName", ""))
    return ""
