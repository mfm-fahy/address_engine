"""
Standalone script to load db/customers_export.csv (Shopify export, treated as f3 source)
into postgres customers and raw_orders tables.

Usage (from server/ directory):
    .venv/bin/python scripts/load_csv_f3.py
    .venv/bin/python scripts/load_csv_f3.py --dry-run
"""
import asyncio
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.postgres import connect, get_pool, close
from pipeline.normalizers import normalize_phone

BATCH_SIZE = 500
SOURCE = "f3"


def parse_row(row):
    first = (row.get("First Name") or "").strip()
    last = (row.get("Last Name") or "").strip()
    name = f"{first} {last}".strip()

    phone = normalize_phone(row.get("Phone") or row.get("Default Address Phone") or "")
    if not phone:
        return None

    email = (row.get("Email") or "").strip()
    total_spent = float(row.get("Total Spent") or 0)
    total_orders = int(float(row.get("Total Orders") or 0))

    street_parts = [
        (row.get("Default Address Address1") or "").strip(),
        (row.get("Default Address Address2") or "").strip(),
    ]
    street = ", ".join(p for p in street_parts if p)

    address = {}
    if street or row.get("Default Address City"):
        address = {
            "street": street,
            "city": (row.get("Default Address City") or "").strip(),
            "state": (row.get("Default Address Province Code") or "").strip(),
            "postcode": (row.get("Default Address Zip") or "").strip(),
            "country": (row.get("Default Address Country Code") or "IN").strip(),
        }

    return {
        "phone": phone,
        "name": name,
        "email": email,
        "total_orders": total_orders,
        "total_spent": total_spent,
        "address": address,
    }


async def main():
    dry_run = "--dry-run" in sys.argv

    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "customers_export.csv")
    print(f"\n=== Loading CSV from {filepath} ===")
    if dry_run:
        print("*** DRY RUN — no data will be written ***")
    t0 = time.time()

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    print(f"Total CSV rows: {len(raw_rows)}")

    customers = {}
    skipped = 0
    for row in raw_rows:
        parsed = parse_row(row)
        if not parsed:
            skipped += 1
            continue

        phone = parsed["phone"]
        cid = f"CUST{phone}"

        if cid not in customers:
            customers[cid] = {
                "customer_id": cid,
                "phone": phone,
                "name": parsed["name"],
                "email": parsed["email"],
                "total_orders": parsed["total_orders"],
                "total_spent": parsed["total_spent"],
                "address": parsed["address"],
            }
        else:
            c = customers[cid]
            if len(parsed["name"]) > len(c["name"]):
                c["name"] = parsed["name"]
            if parsed["email"] and not c["email"]:
                c["email"] = parsed["email"]
            c["total_orders"] = max(c["total_orders"], parsed["total_orders"])
            c["total_spent"] = max(c["total_spent"], parsed["total_spent"])
            if parsed["address"] and not c["address"]:
                c["address"] = parsed["address"]

    print(f"Parsed: {len(customers)} unique customers, {skipped} skipped (no phone)")

    if dry_run:
        sample = list(customers.values())[:5]
        for s in sample:
            print(f"  {s['customer_id']} | {s['name']} | {s['phone']} | orders={s['total_orders']} spent={s['total_spent']}")
        elapsed = time.time() - t0
        print(f"\nDry run complete in {elapsed:.1f}s")
        return

    await connect()
    pool = get_pool()

    # Build customer rows
    cust_rows = []
    for c in customers.values():
        cust_rows.append((
            c["customer_id"], c["phone"], c["name"], c["email"],
            c["total_orders"], round(c["total_spent"], 2),
            json.dumps([], default=str),
            [SOURCE], None,
            json.dumps(c["address"], default=str),
        ))

    print(f"\nUpserting {len(cust_rows)} customers...")
    async with pool.acquire() as conn:
        async with conn.transaction():
            for i in range(0, len(cust_rows), BATCH_SIZE):
                batch = cust_rows[i:i + BATCH_SIZE]
                await conn.executemany(
                    """INSERT INTO customers (
                           customer_id, phone, name, email, username,
                           total_orders, total_bills, total_spent,
                           orders, bills, sources, last_activity, updated_at,
                           metadata, stores, needs_analysis, address
                       ) VALUES ($1, $2, $3, $4, '', $5, 0, $6, $7::jsonb, '[]'::jsonb, $8::text[], $9::timestamptz, NOW(), '{}'::jsonb, '[]'::jsonb, TRUE, $10::jsonb)
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
                if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(cust_rows):
                    print(f"  Progress: {min(i + BATCH_SIZE, len(cust_rows))}/{len(cust_rows)}")

    await close()
    elapsed = time.time() - t0
    print(f"\nDone: {len(cust_rows)} customers upserted in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
