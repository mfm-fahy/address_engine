"""
Standalone script to load customer-data JSON files from db/sql/ into postgres.

Reads WordPress WooCommerce exported customer data (customer-data.json and its parts),
matches order addresses to customers by email, builds customer profiles from phone
numbers, and upserts into the customers table.

Usage (from server/ directory):
    .venv/bin/python scripts/load_customer_data.py
"""
import asyncio
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime
from config.postgres import connect, get_pool, close
from pipeline.normalizers import normalize_phone, normalize_date

BATCH_SIZE = 1000

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "sql")
PART_FILES = [
    "customer-data.json",
    "customer-data.part1.json",
    "customer-data.part2.json",
    "customer-data.part3.json",
]


def build_customer_id(phone: str) -> str:
    return f"CUST{phone}"


def build_address_json(addr: dict) -> dict:
    parts = [
        addr.get("address_1", ""),
        addr.get("address_2", ""),
        addr.get("company", ""),
    ]
    street = ", ".join(p for p in parts if p)
    return {
        "street": street,
        "city": addr.get("city", ""),
        "state": addr.get("state", ""),
        "postcode": addr.get("postcode", ""),
        "country": addr.get("country", ""),
    }


def merge_customer_data(existing: dict, new_data: dict) -> dict:
    merged = dict(existing)
    for key in ("name", "email", "username"):
        if not merged.get(key) and new_data.get(key):
            merged[key] = new_data[key]
    if new_data.get("address"):
        if not merged.get("address"):
            merged["address"] = new_data["address"]
    merged["total_orders"] = max(merged.get("total_orders", 0), new_data.get("total_orders", 0))
    merged["total_spent"] = max(merged.get("total_spent", 0.0), new_data.get("total_spent", 0.0))
    for src in new_data.get("sources", []):
        if src not in merged.get("sources", []):
            merged.setdefault("sources", []).append(src)
    return merged


def parse_part_file(filepath: str) -> tuple[dict, list[dict]]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    entry = data[0] if isinstance(data, list) else data
    tables = entry.get("tables", {})

    customers_lookup = tables.get("wp_wc_customer_lookup", [])
    addresses = tables.get("wp_wc_order_addresses", [])

    email_to_customer = {}
    for c in customers_lookup:
        email = (c.get("email") or "").strip().lower()
        if not email:
            continue
        first = c.get("first_name", "") or ""
        last = c.get("last_name", "") or ""
        name = f"{first} {last}".strip()
        city = c.get("city", "") or ""
        state = c.get("state", "") or ""
        postcode = c.get("postcode", "") or ""
        country = c.get("country", "") or ""

        email_to_customer[email] = {
            "name": name,
            "email": email,
            "username": c.get("username", "") or "",
            "address": {
                "city": city,
                "state": state,
                "postcode": postcode,
                "country": country,
            },
        }

    return email_to_customer, addresses


async def load_customer_data(pool):
    print("\n=== Loading customer-data JSON files into customers table ===")
    t0 = time.time()

    phone_to_cust = {}
    skipped = 0

    for part_file in PART_FILES:
        filepath = os.path.join(DATA_DIR, part_file)
        if not os.path.exists(filepath):
            print(f"  Skipping {part_file} (not found)")
            continue

        print(f"\n--- Processing {part_file} ---")
        email_to_cust, addresses = parse_part_file(filepath)
        print(f"  Loaded {len(email_to_cust)} customer lookups, {len(addresses)} addresses")

        for addr in addresses:
            raw_phone = addr.get("phone", "")
            phone = normalize_phone(str(raw_phone)) if raw_phone else ""
            if not phone or len(phone) < 7:
                skipped += 1
                continue

            email = (addr.get("email") or "").strip().lower()
            lookup_cust = email_to_cust.get(email, {})

            first = addr.get("first_name", "") or ""
            last = addr.get("last_name", "") or ""
            addr_name = f"{first} {last}".strip()
            name = addr_name or lookup_cust.get("name", "")
            email_val = addr.get("email", "") or lookup_cust.get("email", "")
            username = lookup_cust.get("username", "")
            address_json = build_address_json(addr)
            if not address_json.get("city") and lookup_cust.get("address", {}).get("city"):
                address_json = lookup_cust["address"]

            cust = {
                "customer_id": build_customer_id(phone),
                "phone": phone,
                "name": name,
                "email": email_val,
                "username": username,
                "total_orders": 0,
                "total_spent": 0.0,
                "sources": ["wordpress"],
                "address": address_json,
            }

            if phone in phone_to_cust:
                phone_to_cust[phone] = merge_customer_data(phone_to_cust[phone], cust)
            else:
                phone_to_cust[phone] = cust

        print(f"  Running total: {len(phone_to_cust)} unique phones, {skipped} skipped")

    print(f"\nTotal unique phones to upsert: {len(phone_to_cust)}")
    print(f"Total skipped: {skipped}")

    all_rows = []
    for ph, inf in phone_to_cust.items():
        last_act = None
        if inf.get("last_activity"):
            last_act = normalize_date(inf["last_activity"])
        all_rows.append((
            inf["customer_id"],
            inf["phone"],
            inf["name"],
            inf["email"],
            inf.get("username", ""),
            inf.get("total_orders", 0),
            inf.get("total_spent", 0.0),
            json.dumps([], default=str),
            inf.get("sources", ["wordpress"]),
            last_act,
            json.dumps(inf.get("address", {}), default=str),
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
                       ) VALUES ($1, $2, $3, $4, $5, $6, 0, $7,
                                 $8::jsonb, '[]'::jsonb, $9::text[], $10::timestamptz, NOW(),
                                 '{}'::jsonb, '[]'::jsonb, FALSE, $11::jsonb)
                       ON CONFLICT (customer_id) DO UPDATE SET
                           name = CASE
                               WHEN EXCLUDED.name != '' AND length(EXCLUDED.name) > length(customers.name) THEN EXCLUDED.name
                               ELSE customers.name
                           END,
                           email = CASE
                               WHEN EXCLUDED.email != '' AND (customers.email IS NULL OR customers.email = '') THEN EXCLUDED.email
                               ELSE customers.email
                           END,
                           username = CASE
                               WHEN EXCLUDED.username != '' THEN EXCLUDED.username
                               ELSE customers.username
                           END,
                           total_orders = GREATEST(customers.total_orders, EXCLUDED.total_orders),
                           total_spent = GREATEST(customers.total_spent, EXCLUDED.total_spent),
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

    elapsed = time.time() - t0
    print(f"\nDone: {len(all_rows)} customers upserted in {elapsed:.1f}s")
    return len(all_rows)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load customer-data JSON into postgres")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print stats without DB insert")
    args = parser.parse_args()

    if args.dry_run:
        print("\n=== DRY RUN: Parsing customer-data JSON files ===")
        t0 = time.time()
        phone_to_cust = {}
        skipped = 0
        for part_file in PART_FILES:
            filepath = os.path.join(DATA_DIR, part_file)
            if not os.path.exists(filepath):
                continue
            print(f"\n--- Processing {part_file} ---")
            email_to_cust, addresses = parse_part_file(filepath)
            print(f"  Loaded {len(email_to_cust)} customer lookups, {len(addresses)} addresses")
            for addr in addresses:
                raw_phone = addr.get("phone", "")
                phone = normalize_phone(str(raw_phone)) if raw_phone else ""
                if not phone or len(phone) < 7:
                    skipped += 1
                    continue
                email = (addr.get("email") or "").strip().lower()
                lookup_cust = email_to_cust.get(email, {})
                first = addr.get("first_name", "") or ""
                last = addr.get("last_name", "") or ""
                addr_name = f"{first} {last}".strip()
                name = addr_name or lookup_cust.get("name", "")
                email_val = addr.get("email", "") or lookup_cust.get("email", "")
                username = lookup_cust.get("username", "")
                address_json = build_address_json(addr)
                if not address_json.get("city") and lookup_cust.get("address", {}).get("city"):
                    address_json = lookup_cust["address"]
                cust = {
                    "customer_id": build_customer_id(phone),
                    "phone": phone, "name": name, "email": email_val,
                    "username": username, "total_orders": 0, "total_spent": 0.0,
                    "sources": ["wordpress"], "address": address_json,
                }
                if phone in phone_to_cust:
                    phone_to_cust[phone] = merge_customer_data(phone_to_cust[phone], cust)
                else:
                    phone_to_cust[phone] = cust
            print(f"  Running total: {len(phone_to_cust)} unique phones, {skipped} skipped")
        elapsed = time.time() - t0
        print(f"\nTotal unique phones: {len(phone_to_cust)}")
        print(f"Total skipped (no phone): {skipped}")
        print(f"Parsed in {elapsed:.1f}s")
        print("Dry run complete (no DB writes)")
        return

    print("Connecting to database...")
    await connect()
    pool = get_pool()
    await load_customer_data(pool)
    await close()
    print("\n=== Summary ===")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
