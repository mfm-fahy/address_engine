"""
Load remaining files into customers table:
  - DB OF 2023 (1).json  (17K+ orders, monthly structure)
  - combackup.json        (2,732 records)
  - old.json              (332MB F3-DB, customer profiles only)
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.postgres import connect, get_pool, close
from pipeline.normalizers import normalize_phone, normalize_date

BATCH_SIZE = 1000
SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sql")
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")


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


def extract_phones_from_db2023():
    """Parse DB OF 2023 (1).json - monthly order data."""
    filepath = os.path.join(SQL_DIR, "DB OF 2023 (1).json")
    print(f"\n=== DB OF 2023: {filepath} ===")
    t0 = time.time()

    with open(filepath, "r") as f:
        data = json.load(f)

    phone_to_cust = {}
    total_rows = 0

    for month, rows in data.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            total_rows += 1

            vals = list(row.values())
            if len(vals) < 11:
                continue

            email = str(vals[1] or "").strip()
            first = str(vals[3] or "").strip()
            last = str(vals[4] or "").strip()
            name = f"{first} {last}".strip()
            addr1 = str(vals[5] or "").strip()
            addr2 = str(vals[6] or "").strip()
            street = ", ".join(p for p in [addr1, addr2] if p)
            city = str(vals[7] or "").strip()
            state = str(vals[8] or "").strip()
            postcode = str(vals[9] or "").strip()
            phone_raw = vals[10]
            order_value = vals[11] if len(vals) > 11 else 0

            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                continue

            address = build_address(street, city, state, postcode)
            total_spent = 0
            try:
                total_spent = float(order_value or 0)
            except (ValueError, TypeError):
                pass

            if phone not in phone_to_cust:
                phone_to_cust[phone] = {
                    "name": name, "email": email, "address": address,
                    "total_orders": 1, "total_spent": total_spent,
                    "sources": ["db_2023"],
                }
            else:
                existing = phone_to_cust[phone]
                existing["total_orders"] += 1
                existing["total_spent"] += total_spent
                if not existing["name"] and name:
                    existing["name"] = name
                if not existing["email"] and email:
                    existing["email"] = email
                if not existing["address"].get("city") and address.get("city"):
                    existing["address"] = address

    elapsed = time.time() - t0
    print(f"  Parsed {total_rows} rows, {len(phone_to_cust)} unique phones in {elapsed:.1f}s")
    return phone_to_cust


def extract_phones_from_combackup():
    """Parse combackup.json - Google Sheets export with value-based keys."""
    filepath = os.path.join(SQL_DIR, "combackup.json")
    print(f"\n=== combackup: {filepath} ===")
    t0 = time.time()

    with open(filepath, "r") as f:
        data = json.load(f)

    phone_to_cust = {}
    total = 0

    for item in data:
        if not isinstance(item, dict):
            continue

        phone_raw = item.get("9790708124", "")
        phone = normalize_phone(str(phone_raw)) if phone_raw else ""
        if not phone or len(phone) < 7:
            continue

        total += 1
        email = str(item.get("apoorvakutty1@gmail.com", "") or "").strip()
        first = str(item.get("Tv", "") or "").strip()
        last = str(item.get("Apoorva", "") or "").strip()
        name = f"{first} {last}".strip()
        addr1 = str(item.get("No.17/10 ram nagar 1st Street triplicane Chennai -5", "") or "").strip()
        addr2 = str(item.get("__EMPTY_1", "") or "").strip()
        street = ", ".join(p for p in [addr1, addr2] if p)
        city = str(item.get("Chennai", "") or "").strip()
        state = str(item.get("TN", "") or "").strip()

        address = build_address(street, city, state, "")

        if phone not in phone_to_cust:
            phone_to_cust[phone] = {
                "name": name, "email": email, "address": address,
                "sources": ["combackup"],
            }
        else:
            existing = phone_to_cust[phone]
            if not existing["name"] and name:
                existing["name"] = name
            if not existing["email"] and email:
                existing["email"] = email

    elapsed = time.time() - t0
    print(f"  Parsed {total} phones, {len(phone_to_cust)} unique in {elapsed:.1f}s")
    return phone_to_cust


def extract_phones_from_old_json():
    """Stream old.json (332MB) - F3-DB.addressengines data."""
    filepath = os.path.join(DB_DIR, "old.json")
    print(f"\n=== old.json: {filepath} (streaming) ===")
    t0 = time.time()

    import ijson

    phone_to_cust = {}
    total = 0

    with open(filepath, "rb") as f:
        parser = ijson.items(f, "F3-DB.addressengines.item")
        for rec in parser:
            total += 1
            phone_raw = rec.get("phone", "") or rec.get("originalPhone", "")
            phone = normalize_phone(str(phone_raw)) if phone_raw else ""
            if not phone or len(phone) < 7:
                continue

            name = rec.get("customerName", "")
            email = rec.get("email", "")
            order_history = rec.get("orderHistory", [])
            addr = rec.get("shippingAddress", {}) or rec.get("billingAddress", {}) or {}
            total_orders = len(order_history)
            total_spent = sum(float(oh.get("amount", 0) or 0) for oh in order_history)

            address = build_address(
                street=addr.get("street", "") or addr.get("address1", ""),
                city=addr.get("city", ""),
                state=addr.get("state", ""),
                postcode=addr.get("postcode", "") or addr.get("zip", ""),
                country=addr.get("country", "IN"),
            )

            if phone not in phone_to_cust:
                phone_to_cust[phone] = {
                    "name": name, "email": email, "address": address,
                    "total_orders": total_orders, "total_spent": round(total_spent, 2),
                    "sources": ["f3"],
                }
            else:
                existing = phone_to_cust[phone]
                existing["total_orders"] += total_orders
                existing["total_spent"] += round(total_spent, 2)
                if not existing["name"] and name:
                    existing["name"] = name
                if not existing["email"] and email:
                    existing["email"] = email
                if not existing["address"].get("city") and address.get("city"):
                    existing["address"] = address

            if total % 50000 == 0:
                print(f"  Streamed {total} records, {len(phone_to_cust)} phones...")

    elapsed = time.time() - t0
    print(f"  Done: {total} records, {len(phone_to_cust)} unique phones in {elapsed:.1f}s")
    return phone_to_cust


async def insert_customers(pool, phone_to_cust, label):
    all_rows = []
    for ph, inf in phone_to_cust.items():
        all_rows.append((
            build_customer_id(ph), ph,
            inf.get("name", ""), inf.get("email", ""),
            inf.get("total_orders", 0),
            min(round(inf.get("total_spent", 0), 2), 99999999.99),
            inf.get("sources", [label]),
            json.dumps(inf.get("address", {}), default=str),
        ))

    print(f"\nInserting {len(all_rows)} customers ({label})...")
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
                                 '[]'::jsonb, '[]'::jsonb, $7::text[], NULL, NOW(),
                                 '{}'::jsonb, '[]'::jsonb, FALSE, $8::jsonb)
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

    print(f"Done: {len(all_rows)} customers upserted ({label})")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_phones = {}

    # 1. DB OF 2023
    db2023 = extract_phones_from_db2023()
    for ph, inf in db2023.items():
        all_phones[ph] = inf

    # 2. combackup
    combackup = extract_phones_from_combackup()
    for ph, inf in combackup.items():
        if ph not in all_phones:
            all_phones[ph] = inf
        else:
            existing = all_phones[ph]
            if not existing["name"] and inf["name"]:
                existing["name"] = inf["name"]
            if not existing["email"] and inf["email"]:
                existing["email"] = inf["email"]
            existing["sources"] = list(set(existing["sources"] + inf["sources"]))

    # 3. old.json
    old = extract_phones_from_old_json()
    for ph, inf in old.items():
        if ph not in all_phones:
            all_phones[ph] = inf
        else:
            existing = all_phones[ph]
            existing["total_orders"] = existing.get("total_orders", 0) + inf.get("total_orders", 0)
            existing["total_spent"] = existing.get("total_spent", 0) + inf.get("total_spent", 0)
            if not existing["name"] and inf["name"]:
                existing["name"] = inf["name"]
            if not existing["email"] and inf["email"]:
                existing["email"] = inf["email"]
            if not existing["address"].get("city") and inf["address"].get("city"):
                existing["address"] = inf["address"]
            existing["sources"] = list(set(existing["sources"] + inf["sources"]))

    print(f"\nTotal unique phones across all files: {len(all_phones)}")

    if args.dry_run:
        print("Dry run complete (no DB writes)")
        return

    print("\nConnecting to database...")
    await connect()
    pool = get_pool()
    await insert_customers(pool, all_phones, "combined")
    await close()
    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
