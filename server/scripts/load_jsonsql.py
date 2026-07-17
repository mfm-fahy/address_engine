"""
Standalone script to parse jsonsql.json (WordPress MySQL dump) and load
customer data into the customers table.

Streams the 1.3GB SQL dump line by line, extracts wp_wc_customer_lookup
and wp_wc_order_addresses data, builds customer profiles from phone
numbers, and upserts into the customers table.

Usage (from server/ directory):
    .venv/bin/python scripts/load_jsonsql.py [--dry-run]
"""
import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.postgres import connect, get_pool, close
from pipeline.normalizers import normalize_phone

BATCH_SIZE = 1000
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sql")
SQL_FILE = os.path.join(DATA_DIR, "jsonsql.json")

TABLE_CUSTOMER = "wp_wc_customer_lookup"
TABLE_ADDRESSES = "wp_wc_order_addresses"

INSERT_RE = re.compile(r"INSERT INTO `([^`]+)` VALUES ", re.IGNORECASE)
TABLE_RE = re.compile(r"^# Table: `([^`]+)`")


def parse_sql_value(val):
    if val == "NULL":
        return None
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("\\'", "'").replace("''", "'")
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1].replace('\\"', '"').replace('""', '"')
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def split_tuple_values(inner):
    vals = []
    cv = ""
    ci = False
    cc = None
    ce = False
    for ch in inner:
        if ce:
            cv += ch
            ce = False
            continue
        if ch == "\\":
            cv += ch
            ce = True
            continue
        if ci:
            cv += ch
            if ch == cc:
                if len(cv) >= 2 and cv[-2] == cc:
                    pass
                else:
                    ci = False
            continue
        if ch in ("'", '"'):
            ci = True
            cc = ch
            cv += ch
            continue
        if ch == ",":
            vals.append(parse_sql_value(cv.strip()))
            cv = ""
            continue
        cv += ch
    if cv.strip():
        vals.append(parse_sql_value(cv.strip()))
    return vals


def extract_tuple(line):
    stripped = line.strip()
    if stripped.startswith("(") and (stripped.endswith("),") or stripped.endswith(")")):
        inner = stripped[1:]
        if inner.endswith("),"):
            inner = inner[:-2]
        elif inner.endswith(")"):
            inner = inner[:-1]
        return split_tuple_values(inner)
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


def process_customer_row(vals):
    if len(vals) < 12:
        return None
    email = (vals[5] or "").strip()
    first = (vals[3] or "").strip()
    last = (vals[4] or "").strip()
    name = f"{first} {last}".strip()
    username = (vals[2] or "").strip()
    city = (vals[10] or "").strip()
    state = (vals[11] or "").strip()
    postcode = (vals[9] or "").strip()
    country = (vals[8] or "").strip()
    last_active = vals[6]
    address = build_address(city=city, state=state, postcode=postcode, country=country)
    return {
        "name": name, "email": email, "username": username,
        "address": address,
        "last_active": str(last_active) if last_active else None,
    }


def process_address_row(vals, email_to_cust):
    if len(vals) < 14:
        return None
    phone_raw = vals[13] or ""
    phone = normalize_phone(str(phone_raw)) if phone_raw else ""
    if not phone or len(phone) < 7:
        return None
    email = (vals[12] or "").strip().lower()
    first = (vals[3] or "").strip()
    last = (vals[4] or "").strip()
    name = f"{first} {last}".strip()
    addr1 = (vals[6] or "").strip()
    addr2 = (vals[7] or "").strip()
    street = ", ".join(p for p in [addr1, addr2] if p)
    city = (vals[8] or "").strip()
    state = (vals[9] or "").strip()
    postcode = (vals[10] or "").strip()
    country = (vals[11] or "IN").strip()
    address = build_address(street, city, state, postcode, country)

    cust_lookup = email_to_cust.get(email, {})
    if not name and cust_lookup.get("name"):
        name = cust_lookup["name"]
    if not address.get("city") and cust_lookup.get("address", {}).get("city"):
        address = cust_lookup["address"]

    return {
        "phone": phone, "name": name,
        "email": email if "@" in (email or "") else "",
        "address": address,
        "last_active": cust_lookup.get("last_active"),
    }


def parse_jsonsql():
    print(f"\n=== Parsing {SQL_FILE} (streaming) ===")
    t0 = time.time()

    email_to_cust = {}
    phone_to_addr = {}
    current_table = None
    rows_parsed = 0
    customer_rows = 0
    address_rows = 0
    skipped = 0

    with open(SQL_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            table_match = TABLE_RE.match(line)
            if table_match:
                current_table = table_match.group(1)
                continue

            m = INSERT_RE.match(line)
            if m:
                current_table = m.group(1)
                continue

            if current_table not in (TABLE_CUSTOMER, TABLE_ADDRESSES):
                continue

            vals = extract_tuple(line)
            if vals is None:
                continue

            rows_parsed += 1

            if current_table == TABLE_CUSTOMER:
                cust = process_customer_row(vals)
                if cust:
                    email = cust["email"].lower()
                    if email:
                        email_to_cust[email] = cust
                    customer_rows += 1
                else:
                    skipped += 1

            elif current_table == TABLE_ADDRESSES:
                cust = process_address_row(vals, email_to_cust)
                if cust:
                    phone = cust["phone"]
                    if phone not in phone_to_addr:
                        phone_to_addr[phone] = cust
                    else:
                        existing = phone_to_addr[phone]
                        if not existing["name"] and cust["name"]:
                            existing["name"] = cust["name"]
                        if not existing["email"] and cust["email"] and "@" in cust["email"]:
                            existing["email"] = cust["email"]
                        if not existing["address"].get("city") and cust["address"].get("city"):
                            existing["address"] = cust["address"]
                    address_rows += 1
                else:
                    skipped += 1

            if rows_parsed % 10000 == 0:
                print(f"  Parsed {rows_parsed} rows, {customer_rows} customers, {address_rows} addresses, {len(phone_to_addr)} unique phones...")

    elapsed = time.time() - t0
    print(f"\nParse complete: {rows_parsed} rows in {elapsed:.1f}s")
    print(f"  Customer rows: {customer_rows}")
    print(f"  Address rows: {address_rows}")
    print(f"  Skipped: {skipped}")
    print(f"  Email lookups: {len(email_to_cust)}")
    print(f"  Unique phones: {len(phone_to_addr)}")

    return email_to_cust, phone_to_addr


async def run_insert(pool, phone_to_addr):
    all_rows = []
    for ph, inf in phone_to_addr.items():
        all_rows.append((
            build_customer_id(ph), ph, inf.get("name", ""),
            inf.get("email", ""),
            0, 0.0,
            ["f3"],
            None, json.dumps(inf.get("address", {}), default=str),
        ))

    print(f"\nInserting {len(all_rows)} customers from jsonsql...")
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
                                 '[]'::jsonb, '[]'::jsonb, $7::text[], $8::timestamptz, NOW(),
                                 '{}'::jsonb, '[]'::jsonb, FALSE, $9::jsonb)
                       ON CONFLICT (customer_id) DO UPDATE SET
                           name = CASE
                               WHEN EXCLUDED.name != '' AND length(EXCLUDED.name) > length(customers.name) THEN EXCLUDED.name
                               ELSE customers.name
                           END,
                           email = CASE
                               WHEN EXCLUDED.email != '' AND (customers.email IS NULL OR customers.email = '') THEN EXCLUDED.email
                               ELSE customers.email
                           END,
                           sources = (
                               SELECT array_agg(DISTINCT s)
                               FROM unnest(customers.sources || EXCLUDED.sources) AS s
                           ),
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
    parser = argparse.ArgumentParser(description="Load jsonsql.json into postgres")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print stats without DB insert")
    args = parser.parse_args()

    email_to_cust, phone_to_addr = parse_jsonsql()

    if args.dry_run:
        print("\nDry run complete (no DB writes)")
        return

    print("\nConnecting to database...")
    await connect()
    pool = get_pool()
    await run_insert(pool, phone_to_addr)
    await close()
    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
