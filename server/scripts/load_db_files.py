"""
Standalone script to load db/f3.json and db/old.json into postgres.
Uses batch inserts with explicit transactions for reliability.

Usage (from server/ directory):
    .venv/bin/python scripts/load_db_files.py
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
from pipeline.normalizers import normalize_phone, extract_source_phone, extract_source_name, normalize_date

BATCH_SIZE = 500


async def load_f3_json(pool):
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "f3.json")
    print(f"\n=== Loading f3.json from {filepath} ===")
    t0 = time.time()

    with open(filepath, "r") as f:
        records = json.load(f)

    print(f"Total records: {len(records)}")

    rows = []
    for order in records:
        try:
            phone = normalize_phone(extract_source_phone("f3", order))
            order_id = order.get("id") or order.get("transactionId") or order.get("_id") or order.get("orderId", "")
            if not order_id:
                raw_str = f"{order.get('orderDate', '')}_{order.get('orderValue', '')}_{order.get('customerName', '')}_{phone}"
                order_id = f"f3_{hashlib.md5(raw_str.encode()).hexdigest()[:12]}"
            name = extract_source_name("f3", order)
            rows.append((order_id, json.dumps(order, default=str), phone, name))
        except Exception as e:
            print(f"  Skip error: {e}")

    async with pool.acquire() as conn:
        async with conn.transaction():
            for i in range(0, len(rows), BATCH_SIZE):
                batch = rows[i:i+BATCH_SIZE]
                await conn.executemany(
                    """INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, fetched_at)
                       VALUES ('f3', $1, $2::jsonb, $3, $4, NOW())
                       ON CONFLICT (source, order_id) DO UPDATE SET
                           raw_data = EXCLUDED.raw_data,
                           phone = EXCLUDED.phone,
                           customer_name = EXCLUDED.customer_name,
                           fetched_at = EXCLUDED.fetched_at""",
                    batch,
                )
                if (i + BATCH_SIZE) % 2000 == 0 or i + BATCH_SIZE >= len(rows):
                    print(f"  Progress: {min(i+BATCH_SIZE, len(rows))}/{len(rows)}")

    elapsed = time.time() - t0
    print(f"Done: {len(rows)} orders in {elapsed:.1f}s")
    return len(rows)


async def load_old_json(pool):
    import ijson

    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "old.json")
    print(f"\n=== Streaming old.json (317MB) for F3-DB.addressengines ===")
    t0 = time.time()

    order_rows = []
    seen_phones = {}
    skipped = 0

    with open(filepath, "rb") as f:
        parser = ijson.items(f, "F3-DB.addressengines.item")

        for rec in parser:
            try:
                phone = normalize_phone(str(rec.get("phone", "") or rec.get("originalPhone", "")))
                if not phone:
                    skipped += 1
                    continue

                customer_name = rec.get("customerName", "")
                email = rec.get("email", "")
                order_history = rec.get("orderHistory", [])

                for oh in order_history:
                    order_id = oh.get("orderId") or oh.get("_id") or ""
                    if not order_id:
                        oid_raw = f"{phone}_{oh.get('orderNumber', '')}_{oh.get('date', '')}"
                        order_id = f"f3_old_{hashlib.md5(oid_raw.encode()).hexdigest()[:12]}"

                    order_data = {
                        "customerName": customer_name,
                        "customerPhone": phone,
                        "customerEmail": email,
                        "orderDate": oh.get("date", ""),
                        "orderValue": oh.get("amount", 0),
                        "status": oh.get("status", ""),
                        "sourcePlatform": "f3",
                        "tenantId": rec.get("tenantId", ""),
                        "tenantName": rec.get("tenantName", ""),
                        "shippingAddress": rec.get("shippingAddress", {}),
                        "billingAddress": rec.get("billingAddress", {}),
                        "products": oh.get("products", []),
                    }
                    order_rows.append((order_id, json.dumps(order_data, default=str), phone, customer_name))

                # Aggregate customer info
                if phone not in seen_phones:
                    seen_phones[phone] = {
                        "customer_id": f"CUST{phone}",
                        "phone": phone,
                        "name": customer_name,
                        "email": email,
                        "total_orders": len(order_history),
                        "total_spent": sum(float(oh.get("amount", 0) or 0) for oh in order_history),
                        "sources": ["f3"],
                        "last_order_date": rec.get("lastOrderDate", ""),
                        "address": rec.get("shippingAddress", {}) or rec.get("billingAddress", {}) or {},
                    }
                else:
                    seen_phones[phone]["total_orders"] += len(order_history)
                    seen_phones[phone]["total_spent"] += sum(float(oh.get("amount", 0) or 0) for oh in order_history)
                    if not seen_phones[phone]["name"] and customer_name:
                        seen_phones[phone]["name"] = customer_name
                    if not seen_phones[phone]["email"] and email:
                        seen_phones[phone]["email"] = email

            except Exception as e:
                skipped += 1
                if skipped <= 10:
                    print(f"  Skip error: {e}")

            total = len(order_rows) + skipped
            if total % 2000 == 0 and total > 0:
                print(f"  Streaming: {len(order_rows)} orders, {len(seen_phones)} phones, {skipped} skipped")

    print(f"  Streaming done: {len(order_rows)} orders, {len(seen_phones)} phones, {skipped} skipped")

    # Batch insert orders in explicit transaction
    print(f"  Inserting orders...")
    async with pool.acquire() as conn:
        async with conn.transaction():
            for i in range(0, len(order_rows), BATCH_SIZE):
                batch = order_rows[i:i+BATCH_SIZE]
                await conn.executemany(
                    """INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, fetched_at)
                       VALUES ('f3', $1, $2::jsonb, $3, $4, NOW())
                       ON CONFLICT (source, order_id) DO UPDATE SET
                           raw_data = EXCLUDED.raw_data,
                           phone = EXCLUDED.phone,
                           customer_name = EXCLUDED.customer_name,
                           fetched_at = EXCLUDED.fetched_at""",
                    batch,
                )
                if (i + BATCH_SIZE) % 10000 == 0 or i + BATCH_SIZE >= len(order_rows):
                    print(f"  Orders: {min(i+BATCH_SIZE, len(order_rows))}/{len(order_rows)}")

    # Build customer rows
    all_cust_rows = []
    for ph, inf in seen_phones.items():
        lad = None
        lod = inf["last_order_date"]
        if lod:
            if isinstance(lod, dict) and "$date" in lod:
                lad = lod["$date"]
            else:
                lad = str(lod)
        lad_dt = normalize_date(lad) if lad else None
        all_cust_rows.append((
            inf["customer_id"], inf["phone"], inf["name"], inf["email"],
            inf["total_orders"], round(inf["total_spent"], 2),
            json.dumps([], default=str),
            inf["sources"], lad_dt,
            json.dumps(inf["address"], default=str),
        ))

    # Batch insert customers in explicit transaction
    print(f"  Inserting {len(all_cust_rows)} customers...")
    async with pool.acquire() as conn:
        async with conn.transaction():
            for i in range(0, len(all_cust_rows), BATCH_SIZE):
                batch = all_cust_rows[i:i+BATCH_SIZE]
                await conn.executemany(
                    """INSERT INTO customers (
                           customer_id, phone, name, email, username,
                           total_orders, total_bills, total_spent,
                           orders, bills, sources, last_activity, updated_at,
                           metadata, stores, needs_analysis, address
                       ) VALUES ($1, $2, $3, $4, '', $5, 0, $6, $7::jsonb, '[]'::jsonb, $8::text[], $9::timestamptz, NOW(), '{}'::jsonb, '[]'::jsonb, TRUE, $10::jsonb)
                       ON CONFLICT (customer_id) DO UPDATE SET
                           name = EXCLUDED.name,
                           email = EXCLUDED.email,
                           total_orders = EXCLUDED.total_orders,
                           total_spent = EXCLUDED.total_spent,
                           orders = EXCLUDED.orders,
                           last_activity = GREATEST(customers.last_activity, EXCLUDED.last_activity),
                           updated_at = NOW(),
                           address = CASE
                               WHEN customers.address IS NULL OR customers.address = '{}'::jsonb THEN EXCLUDED.address
                               ELSE customers.address
                           END""",
                    batch,
                )
                if (i + BATCH_SIZE) % 5000 == 0 or i + BATCH_SIZE >= len(all_cust_rows):
                    print(f"  Customers: {min(i+BATCH_SIZE, len(all_cust_rows))}/{len(all_cust_rows)}")

    elapsed = time.time() - t0
    print(f"Done: {len(order_rows)} orders, {len(all_cust_rows)} customers in {elapsed:.1f}s")
    return len(order_rows)


async def main():
    print("Connecting to database...")
    await connect()
    pool = get_pool()

    await load_f3_json(pool)
    await load_old_json(pool)

    await close()
    print(f"\n=== Summary ===")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
