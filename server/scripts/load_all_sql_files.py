"""
Standalone script to load ALL remaining JSON files from db/sql/ into postgres.

Handles multiple file formats:
  - WooCommerce Admin Exports (Phone, Order ID, Total, etc.)
  - WooCommerce with {"data": [...]} wrapper
  - WooCommerce .COM exports (Column19, Column3, etc.)
  - Tamil-labeled exports
  - Autocrat __EMPTY positional keys
  - UAE files (Billing Contact, Billing Name, etc.)
  - Operation Bhurj Khalifa (NVScriptsProperties wrapper)
  - Tracking files (Phone number, WhatsApp Number)
  - MongoDB address collections (phone, billingAddress, etc.)
  - Revenue analysis (Phone, Monetary)
  - Business contacts (Whatsapp Number, Name)
  - Razorpay webhook exports (scientific notation phones)

Skips broken/irrelevant files: jsonsql.json, COD_Orders.json,
Orders Vaseegrahveda.com.json, combackup.json, product report files,
1_4to21_06admin.json.

Usage (from server/ directory):
    .venv/bin/python scripts/load_all_sql_files.py [--dry-run]
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.postgres import connect, get_pool, close
from pipeline.normalizers import normalize_phone

BATCH_SIZE = 1000
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sql")
EXCEL_EPOCH = datetime(1899, 12, 30)

SKIP_FILES = {
    "jsonsql.json", "COD_Orders.json", "Orders Vaseegrahveda.com.json",
    "combackup.json", "nov 16 to 29.com.json", "nov 30 .com.json",
    "sales_2023-11-01 to 30 shopyfy .json",
    "sales_2023-11-01_2023-11-26 sopify.json",
    "customer-data.json", "customer-data.part1.json",
    "customer-data.part2.json", "customer-data.part3.json",
}

FILES_TO_LOAD = [
    "ORDERS DATA 2021.json", "ORDERS DATA 2021 (1).json",
    "2022- Jan to Mar.json", "2022- Apr to Jun.json",
    "2022- Jul to Sep.json", "2023- Jan to Mar.json",
    "2021- Oct to Dec.json", "2020- Sep to Dec (1).json",
    "2021-Orders.json",
    "comorder.json", "22 nov to 26 nov .json", "22 nov to 26 nov  (1).json",
    "Copy of Admin Integration.json", "Copy of .COM Integration.json",
    "january_2024.json", "comorder2023.json", "comoct2024.json",
    "copygmail.json",
    "F3-DB.addressengines.json",
    "Operation Bhurj Khalifa.json", "Operation Burj Khalifa-Part 2.json",
    "Bhurj kalifha dec .json", "Customer Info in UAE (2).json",
    "copytracking.json", "Main tracking sheet.json",
    "potential_customers_revenue_wise.json", "Business.json",
    "excel-to-json.json",
    "address.json", "jsonfile.json", "add.json", "datas.json",
    "java.json", "js.json",
    "Manual_Orders .json", "1_4to21_06admin.json",
]


def excel_serial_to_datetime(serial):
    if not serial or not isinstance(serial, (int, float)):
        return None
    try:
        if serial < 1:
            return None
        return EXCEL_EPOCH + timedelta(days=serial)
    except Exception:
        return None


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return excel_serial_to_datetime(value) if value > 40000 else None
    s = str(value).strip()
    if not s:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
        "%d.%m.%y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def build_customer_id(phone):
    return f"CUST{phone}"


def build_address(street="", city="", state="", postcode="", country="IN"):
    return {
        "street": str(street).strip() if street else "",
        "city": str(city).strip() if city else "",
        "state": str(state).strip() if state else "",
        "postcode": str(postcode).strip() if postcode else "",
        "country": str(country).strip() if country else "IN",
    }


def is_valid_email(email):
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    return "@" in email and "." in email


def is_phone_like(val):
    if not val:
        return False
    s = str(val).replace(" ", "").replace("-", "").replace("+", "")
    return s.isdigit() and len(s) >= 7


def merge_customer(existing, new):
    merged = dict(existing)
    for key in ("name", "email", "username"):
        if not merged.get(key) and new.get(key):
            merged[key] = new[key]
    if new.get("address") and not merged.get("address"):
        merged["address"] = new["address"]
    merged["total_orders"] = max(merged.get("total_orders", 0), new.get("total_orders", 0))
    merged["total_spent"] = max(merged.get("total_spent", 0.0), new.get("total_spent", 0.0))
    for src in new.get("sources", []):
        if src not in merged.get("sources", []):
            merged.setdefault("sources", []).append(src)
    if new.get("orders_list"):
        el = merged.setdefault("orders_list", [])
        for o in new["orders_list"]:
            if o not in el:
                el.append(o)
    return merged


def extract_orders(record, phone, source):
    oid = record.get("Order ID") or record.get("order id") or record.get("__EMPTY_13") or record.get("__EMPTY_11")
    if not oid:
        return []
    total = record.get("Total") or record.get("__EMPTY_12") or record.get("__EMPTY_14") or record.get("Amount") or 0
    try:
        total = float(total)
    except (ValueError, TypeError):
        total = 0.0
    date_val = record.get("Date") or record.get("DATE") or record.get("Date & Time") or record.get("autocratn") or record.get("__EMPTY")
    od = None
    if isinstance(date_val, (int, float)) and date_val > 40000:
        od = excel_serial_to_datetime(date_val)
    else:
        od = parse_date(date_val)
    products = record.get("Order") or record.get("Products") or ""
    if not isinstance(products, str):
        products = str(products)
    return [{"orderId": str(oid), "date": od.isoformat() if od else "", "amount": total, "products": products, "source": source}]


def make_cust(phone, name="", email="", address=None, orders=None, total_spent=0.0, sources=None, last_activity=None):
    return {
        "customer_id": build_customer_id(phone), "phone": phone,
        "name": name,
        "email": email if is_valid_email(email) else "",
        "total_orders": len(orders) if orders else 0,
        "total_spent": total_spent, "orders_list": orders or [],
        "sources": sources or ["sql"],
        "last_activity": last_activity.isoformat() if isinstance(last_activity, datetime) else None,
        "address": address or {},
    }


def load_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def unwrap(data):
    if isinstance(data, dict):
        if "_id" in data or "phone" in data or "customerName" in data:
            return [data]
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
        for k in data:
            if isinstance(data[k], list):
                return data[k]
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict):
            if "_id" in data[0] or "phone" in data[0] or "customerName" in data[0]:
                return data
            for k in data[0]:
                if isinstance(data[0][k], list):
                    return data[0][k]
        return data
    return []


def parse_mongodb_record(rec, source="f3"):
    phone_raw = rec.get("phone") or rec.get("originalPhone") or ""
    if not phone_raw:
        billing = rec.get("billingAddress", {}) or {}
        phone_raw = billing.get("phone", "")
    phone = normalize_phone(str(phone_raw)) if phone_raw else ""
    if not phone or len(phone) < 7:
        return None
    name = rec.get("customerName") or ""
    if not name:
        billing = rec.get("billingAddress", {}) or {}
        name = f"{billing.get('firstName', '')} {billing.get('lastName', '')}".strip()
    email = rec.get("email") or ""
    if not email:
        email = (rec.get("billingAddress", {}) or {}).get("email", "")
    billing = rec.get("billingAddress") or {}
    shipping = rec.get("shippingAddress") or {}
    addr = billing or shipping
    address = build_address(
        street=f"{addr.get('address1', '')} {addr.get('address2', '')}".strip(),
        city=addr.get("city", ""), state=addr.get("state", ""),
        postcode=addr.get("postcode", ""), country=addr.get("country", "IN"),
    )
    order_history = rec.get("orderHistory", [])
    orders = []
    for oh in order_history:
        oid = oh.get("orderId") or oh.get("orderNumber") or ""
        if oid:
            orders.append({"orderId": str(oid), "source": source})
    lad = rec.get("lastOrderDate")
    if isinstance(lad, dict):
        lad = lad.get("$date")
    last_activity = parse_date(lad)
    return make_cust(phone, name, email, address, orders, 0.0, [source], last_activity)


def add_cust(phone_to_cust, cust):
    phone = cust["phone"]
    if phone in phone_to_cust:
        phone_to_cust[phone] = merge_customer(phone_to_cust[phone], cust)
    else:
        phone_to_cust[phone] = cust


def extract_nvscripts(data):
    records = []
    if isinstance(data, dict) and "NVScriptsProperties" in data:
        records = data["NVScriptsProperties"]
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "NVScriptsProperties" in item:
                records = item["NVScriptsProperties"]
                break
    skip = {"dataSheetName", "v", "dataSheetId", "updateTime", "ssId", "vp"}
    return [r for r in records if isinstance(r, dict)
            and r.get("autocratn", "") not in skip
            and ("Column4" in r or "Column12" in r)]


def process_file(filepath, phone_to_cust):
    filename = os.path.basename(filepath)
    data = load_json_file(filepath)
    if data is None:
        return 0, "FAILED to parse"

    records_loaded = 0
    skipped = 0
    source = "sql"

    records = unwrap(data)

    if filename == "F3-DB.addressengines.json":
        source = "f3"
        for rec in records:
            if not isinstance(rec, dict):
                continue
            cust = parse_mongodb_record(rec, source)
            if cust:
                add_cust(phone_to_cust, cust)
                records_loaded += 1
            else:
                skipped += 1
        return records_loaded, f"{records_loaded} customers, {skipped} skipped"

    if filename == "Operation Bhurj Khalifa.json":
        records = extract_nvscripts(data)
        source = "uae_bhurj"
        for rec in records:
            phone_raw = rec.get("Column12") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Column4") or "").strip()
            last = str(rec.get("Column5") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("autocratp") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Column7") or "").strip()
            addr2 = str(rec.get("Column8") or "").strip()
            if addr2 and addr2 != street:
                street = f"{street}, {addr2}" if street else addr2
            city = str(rec.get("Column9") or "").strip()
            state = str(rec.get("Column10") or "").strip()
            address = build_address(street, city, state, "")
            total = 0
            try:
                total = float(rec.get("Column15") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Column14") or ""
            last_activity = parse_date(rec.get("autocratn"))
            orders = [{"orderId": str(oid), "date": last_activity.isoformat() if last_activity else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], last_activity)
            add_cust(phone_to_cust, cust)
            records_loaded += 1
        return records_loaded, f"{records_loaded} customers, {skipped} skipped"

    for rec in records:
        if not isinstance(rec, dict):
            skipped += 1
            continue

        cust = None

        if filename in ("address.json", "jsonfile.json", "add.json", "datas.json", "java.json", "js.json"):
            cust = parse_mongodb_record(rec, "f3_small")

        elif filename == "copytracking.json":
            phone_raw = rec.get("Phone number") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            name = str(rec.get("Name") or "").strip()
            email = rec.get("Email") or ""
            cust = make_cust(phone, name, email, sources=["tracking"])

        elif filename == "Main tracking sheet.json":
            phone_raw = rec.get("Whatsapp Number") or rec.get("WhatsApp Number") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            name = str(rec.get("Name") or "").strip()
            cust = make_cust(phone, name, sources=["tracking_main"])

        elif filename == "potential_customers_revenue_wise.json":
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            monetary = 0
            try:
                monetary = float(rec.get("Monetary") or 0)
            except (ValueError, TypeError):
                pass
            freq = 0
            try:
                freq = int(rec.get("Frequency") or 0)
            except (ValueError, TypeError):
                pass
            cust = make_cust(phone, total_spent=monetary, sources=["rfm"])
            cust["total_orders"] = freq

        elif filename == "Business.json":
            phone_raw = rec.get("Whatsapp Number") or rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            name = str(rec.get("Name") or "").strip()
            cust = make_cust(phone, name, sources=["business"])

        elif filename == "excel-to-json.json":
            phone_str = str(rec.get("Phone Number") or "").strip()
            if not phone_str or not is_phone_like(phone_str):
                skipped += 1
                continue
            phone = normalize_phone(phone_str)
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            email = rec.get("Email") or ""
            total = 0
            try:
                total = float(str(rec.get("Amount") or 0).replace(",", ""))
            except (ValueError, TypeError):
                pass
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": "razorpay"}] if oid else []
            cust = make_cust(phone, email=email, orders=orders, total_spent=total, sources=["razorpay"], last_activity=la)

        elif filename in ("Operation Burj Khalifa-Part 2.json",):
            source = "uae_burj2"
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            address = build_address(street, city, state, "")
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "Bhurj kalifha dec .json":
            source = "uae_dec"
            phone_raw = rec.get("Billing Contact") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            name = str(rec.get("Billing Name") or "").strip()
            email = rec.get("Billing Mail") or ""
            if not is_valid_email(email):
                email = ""
            flat = str(rec.get("Flat Number") or "").strip()
            addr1 = str(rec.get("Billing Address 1") or "").strip()
            addr2 = str(rec.get("Billing Address") or rec.get("Billing Address ") or "").strip()
            street = ", ".join(p for p in [flat, addr1, addr2] if p)
            city = str(rec.get("City") or "").strip()
            emirates = str(rec.get("Emirates") or "").strip()
            address = build_address(street, city, emirates, "")
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "Customer Info in UAE (2).json":
            source = "uae_info"
            phone_raw = rec.get("Billing Contact") or rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            name = str(rec.get("Billing Name") or "").strip()
            email = rec.get("Billing Mail") or ""
            if not is_valid_email(email):
                email = ""
            flat = str(rec.get("Flat Number") or "").strip()
            addr1 = str(rec.get("Billing Address 1") or "").strip()
            addr2 = str(rec.get("Billing Address ") or rec.get("Billing Address") or "").strip()
            street = ", ".join(p for p in [flat, addr1, addr2] if p)
            city = str(rec.get("City") or "").strip()
            emirates = str(rec.get("Emirates") or "").strip()
            address = build_address(street, city, emirates, "")
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, 0.0, [source], la)

        elif filename == "comoct2024.json":
            source = "woo_com_oct2024"
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            if not name:
                skipped += 1
                continue
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date & Time") or rec.get("Date"))
            orders = []
            if oid:
                try:
                    int(str(oid))
                    orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}]
                except (ValueError, TypeError):
                    pass
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "copygmail.json":
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            oid = rec.get("Order ID") or ""
            orders = [{"orderId": str(oid), "source": "woo_gmail"}] if oid else []
            cust = make_cust(phone, name, email, address, orders, 0.0, ["woo_gmail"])

        elif filename in ("comorder.json", "2021-Orders.json"):
            source = "woo_com"
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            la = parse_date(rec.get("Date"))
            orders = extract_orders(rec, phone, source)
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename in ("ORDERS DATA 2021.json", "ORDERS DATA 2021 (1).json"):
            source = "woo_orders_2021"
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            la = parse_date(rec.get("Date"))
            orders = extract_orders(rec, phone, source)
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename in ("2022- Jan to Mar.json", "2022- Apr to Jun.json",
                          "2022- Jul to Sep.json", "2023- Jan to Mar.json",
                          "2021- Oct to Dec.json"):
            source = "woo_quarterly"
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            la = parse_date(rec.get("Date"))
            orders = extract_orders(rec, phone, source)
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "2020- Sep to Dec (1).json":
            source = "woo_2020"
            phone_raw = rec.get("__EMPTY_11") or rec.get("__EMPTY_9") or rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("__EMPTY_3") or rec.get("Billing First name") or "").strip()
            last = str(rec.get("__EMPTY_4") or rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("__EMPTY_1") or rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("__EMPTY_6") or rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("__EMPTY_7") or rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("__EMPTY_8") or rec.get("City") or "").strip()
            state = str(rec.get("__EMPTY_9") or rec.get("State") or "").strip()
            postcode = str(rec.get("__EMPTY_10") or rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("__EMPTY_14") or rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            la = parse_date(rec.get("__EMPTY") or rec.get("Date"))
            orders = extract_orders(rec, phone, source)
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "january_2024.json":
            source = "woo_jan2024"
            phone_raw = rec.get("Phone") or rec.get("WhatsApp") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("First Name/ முதல் பெயர்") or "").strip()
            last = str(rec.get("Last Name/ துணை பெயர்\n") or "").strip()
            name = f"{first} {last}".strip()
            street = str(rec.get("Address line 1") or "").strip()
            city = str(rec.get("City/District -  நகரம் /மாவட்டம்_1") or "").strip()
            state = str(rec.get("State/ மாநிலம்") or "").strip()
            postcode = str(rec.get("Pincode /  பின்கோடு") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            la = parse_date(rec.get("DATE") or rec.get("Date"))
            orders = extract_orders(rec, phone, source)
            cust = make_cust(phone, name, address=address, orders=orders, total_spent=total, sources=[source], last_activity=la)

        elif filename == "comorder2023.json":
            source = "woo_com2023"
            phone_raw = rec.get("__EMPTY_9") or rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("__EMPTY_1") or "").strip()
            last = str(rec.get("__EMPTY_2") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("autocratp") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("__EMPTY_4") or "").strip()
            street2 = str(rec.get("__EMPTY_5") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("__EMPTY_6") or "").strip()
            state = str(rec.get("__EMPTY_7") or "").strip()
            postcode = str(rec.get("__EMPTY_8") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("__EMPTY_12") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("__EMPTY_11") or ""
            la = parse_date(rec.get("autocratn") or rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename in ("22 nov to 26 nov .json", "22 nov to 26 nov  (1).json",
                          "Copy of Admin Integration.json", "Copy of .COM Integration.json"):
            source = "woo_dotcom"
            phone_raw = rec.get("Column19") or rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Column3") or rec.get("Billing First name") or "").strip()
            last = str(rec.get("Column16") or rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Column11") or rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("Column4") or rec.get("City") or "").strip()
            state = str(rec.get("Column5") or rec.get("State") or "").strip()
            postcode = str(rec.get("Column12") or rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Column13") or rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Column2") or rec.get("Order ID") or ""
            la = parse_date(rec.get("Date") or rec.get("Date & Time"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "Manual_Orders .json":
            source = "manual_orders"
            if "Merged Doc ID" in str(rec):
                skipped += 1
                continue
            phone_raw = rec.get("Phone") or ""
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue
            first = str(rec.get("Billing First name") or "").strip()
            last = str(rec.get("Billing Last name") or "").strip()
            name = f"{first} {last}".strip()
            email = rec.get("Billing Email") or ""
            if not is_valid_email(email):
                email = ""
            street = str(rec.get("Billing Address 1") or "").strip()
            street2 = str(rec.get("Billing Address 2") or "").strip()
            if street2:
                street = f"{street}, {street2}" if street else street2
            city = str(rec.get("City") or "").strip()
            state = str(rec.get("State") or "").strip()
            postcode = str(rec.get("Postcode") or "").strip()
            address = build_address(street, city, state, postcode)
            total = 0
            try:
                total = float(rec.get("Total") or 0)
            except (ValueError, TypeError):
                pass
            oid = rec.get("Order ID") or ""
            la = parse_date(rec.get("Date"))
            orders = [{"orderId": str(oid), "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
            cust = make_cust(phone, name, email, address, orders, total, [source], la)

        elif filename == "1_4to21_06admin.json":
            source = "admin_apr_jun"
            admin_data = None
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                for k in data[0]:
                    if isinstance(data[0][k], list):
                        admin_data = data[0][k]
                        break
            elif isinstance(data, dict):
                for k in data:
                    if isinstance(data[k], list):
                        admin_data = data[k]
                        break
            if not admin_data or len(admin_data) < 2:
                return 0, "No admin data found"
            header_rec = admin_data[0]
            keys = list(header_rec.keys())
            for aidx in range(1, len(admin_data)):
                arec = admin_data[aidx]
                if not isinstance(arec, dict):
                    skipped += 1
                    continue
                vals = [arec.get(k, "") for k in keys]
                if len(vals) < 11:
                    skipped += 1
                    continue
                phone_raw = vals[10] if len(vals) > 10 else ""
                phone = normalize_phone(str(phone_raw)) if phone_raw else ""
                if not phone or len(phone) < 7:
                    skipped += 1
                    continue
                first = str(vals[3] if len(vals) > 3 else "").strip()
                last = str(vals[4] if len(vals) > 4 else "").strip()
                name = f"{first} {last}".strip()
                email = str(vals[1] if len(vals) > 1 else "").strip()
                if not is_valid_email(email):
                    email = ""
                addr1 = str(vals[5] if len(vals) > 5 else "").strip()
                addr2 = str(vals[6] if len(vals) > 6 else "").strip()
                street = ", ".join(p for p in [addr1, addr2] if p)
                city = str(vals[7] if len(vals) > 7 else "").strip()
                state = str(vals[8] if len(vals) > 8 else "").strip()
                postcode = str(vals[9] if len(vals) > 9 else "").strip()
                address = build_address(street, city, state, postcode)
                total = 0
                try:
                    total = float(vals[12] if len(vals) > 12 else 0)
                except (ValueError, TypeError):
                    pass
                oid = str(vals[11] if len(vals) > 11 else "").strip()
                la = parse_date(vals[0] if len(vals) > 0 else "")
                orders = [{"orderId": oid, "date": la.isoformat() if la else "", "amount": total, "source": source}] if oid else []
                acust = make_cust(phone, name, email, address, orders, total, [source], la)
                add_cust(phone_to_cust, acust)
                records_loaded += 1
            return records_loaded, f"{records_loaded} customers, {skipped} skipped"

        else:
            skipped += 1
            continue

        if cust:
            add_cust(phone_to_cust, cust)
            records_loaded += 1
        else:
            skipped += 1

    return records_loaded, f"{records_loaded} customers, {skipped} skipped"


async def run_insert(pool, phone_to_cust):
    all_rows = []
    for ph, inf in phone_to_cust.items():
        la = None
        if inf.get("last_activity"):
            la = parse_date(inf["last_activity"])
        orders_json = json.dumps(inf.get("orders_list", []), default=str)
        all_rows.append((
            inf["customer_id"], inf["phone"], inf["name"], inf["email"],
            inf.get("total_orders", 0), inf.get("total_spent", 0.0),
            orders_json, inf.get("sources", ["sql"]),
            la, json.dumps(inf.get("address", {}), default=str),
        ))

    print(f"\nInserting {len(all_rows)} customers...")
    async with pool.acquire() as conn:
        for i in range(0, len(all_rows), BATCH_SIZE):
            batch = all_rows[i:i + BATCH_SIZE]
            async with conn.transaction():
                await conn.executemany(
                    """INSERT INTO customers (
                           customer_id, phone, name, email, username,
                           total_orders, total_bills, total_spent,
                           orders, bills, sources, last_activity, updated_at,
                           metadata, stores, needs_analysis, address
                       ) VALUES ($1, $2, $3, $4, '', $5, 0, $6,
                                 $7::jsonb, '[]'::jsonb, $8::text[], $9::timestamptz, NOW(),
                                 '{}'::jsonb, '[]'::jsonb, FALSE, $10::jsonb)
                       ON CONFLICT (customer_id) DO UPDATE SET
                           name = CASE
                               WHEN EXCLUDED.name != '' AND length(EXCLUDED.name) > length(customers.name) THEN EXCLUDED.name
                               ELSE customers.name
                           END,
                           email = CASE
                               WHEN EXCLUDED.email != '' AND (customers.email IS NULL OR customers.email = '') THEN EXCLUDED.email
                               ELSE customers.email
                           END,
                           total_orders = GREATEST(customers.total_orders, EXCLUDED.total_orders),
                           total_spent = GREATEST(customers.total_spent, EXCLUDED.total_spent),
                           orders = CASE
                               WHEN customers.orders = '[]'::jsonb THEN EXCLUDED.orders
                               ELSE customers.orders
                           END,
                           sources = (
                               SELECT array_agg(DISTINCT s)
                               FROM unnest(customers.sources || EXCLUDED.sources) AS s
                           ),
                           last_activity = GREATEST(customers.last_activity, EXCLUDED.last_activity),
                           updated_at = NOW(),
                           address = CASE
                               WHEN customers.address IS NULL OR customers.address = '{}'::jsonb THEN EXCLUDED.address
                               ELSE customers.address
                           END""",
                    batch,
                )
            done = min(i + BATCH_SIZE, len(all_rows))
            print(f"  Progress: {done}/{len(all_rows)}")

    print(f"Done: {len(all_rows)} customers upserted")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Load all db/sql JSON files into postgres")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print stats without DB insert")
    args = parser.parse_args()

    print("=== Loading ALL db/sql JSON files ===")
    t0 = time.time()
    phone_to_cust = {}
    file_stats = []

    for filename in FILES_TO_LOAD:
        if filename in SKIP_FILES:
            continue
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            file_stats.append((filename, "NOT FOUND"))
            continue
        fsize = os.path.getsize(filepath) / (1024 * 1024)
        print(f"\n--- {filename} ({fsize:.1f}MB) ---")
        try:
            count, msg = process_file(filepath, phone_to_cust)
            file_stats.append((filename, msg))
            print(f"  {msg}")
        except Exception as e:
            file_stats.append((filename, f"ERROR: {e}"))
            print(f"  ERROR: {e}")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"PARSE SUMMARY ({elapsed:.1f}s)")
    print(f"{'='*60}")
    for fn, msg in file_stats:
        print(f"  {fn}: {msg}")
    print(f"\nTotal unique phones: {len(phone_to_cust)}")

    if args.dry_run:
        print("\nDry run complete (no DB writes)")
        return

    print("\nConnecting to database...")
    await connect()
    pool = get_pool()
    await run_insert(pool, phone_to_cust)
    await close()
    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
