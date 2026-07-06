import asyncio
import httpx
import json
import re
from datetime import datetime
from config.settings import API_KEYS
from config.postgres import get_pool

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    phone = str(phone).strip()
    phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    phone = re.sub(r'^0+', '', phone)
    if phone.startswith('91') and len(phone) > 10:
        phone = phone[2:]
    if phone.startswith('1') and len(phone) > 10:
        phone = phone[1:]
    phone = phone[-10:] if len(phone) >= 10 else phone
    return phone

async def fetch_url(url: str, api_key: str, params: dict = {}, timeout: int = 60, headers_extra: dict = {}):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **headers_extra}
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

async def fetch_billzzy(url: str, api_key: str, per_request_timeout: int = 120):
    all_customers = []
    all_transactions = []
    limit = 100
    offset = 0

    while True:
        data = await fetch_url(url, api_key,
                               params={"limit": limit, "offset": offset},
                               timeout=per_request_timeout,
                               headers_extra={"x-api-key": api_key})
        if not data:
            break

        orgs = data.get("organisations", [])
        if not orgs:
            break

        for org in orgs:
            org_id = org.get("id")
            org_name = org.get("name", "")
            org_phone = normalize_phone(org.get("phone", ""))

            cust_id_to_phone = {}
            for cust in org.get("customers", []):
                phone = normalize_phone(cust.get("phone", ""))
                cust_id_to_phone[str(cust.get("id"))] = phone
                cust_address = build_billzzy_address(cust)
                all_customers.append({
                    "source": "bill",
                    "order_id": f"bill_cust_{org_id}_{cust.get('id', '')}",
                    "phone": phone,
                    "customer_name": cust.get("name", ""),
                    "customer_id": str(cust.get("id", "")),
                    "address": cust_address,
                    "customer_total_spent": float(cust.get("totalSpent", 0) or 0),
                    "raw_data": {
                        "type": "customer",
                        "org_id": org_id,
                        "org_name": org_name,
                        "_bill_customer": cust
                    }
                })

            for tx in org.get("transactions", []):
                tx_customer = tx.get("customer", {})
                tx_customer_id = str(tx.get("customerId") or tx.get("customer_id") or "")
                tx_phone = (
                    normalize_phone(tx_customer.get("phone", "") or tx_customer.get("mobile", ""))
                    or cust_id_to_phone.get(str(tx.get("id")))
                    or cust_id_to_phone.get(tx_customer_id)
                    or org_phone
                )
                all_transactions.append({
                    "order_id": f"bill_tx_{org_id}_{tx.get('id', '')}",
                    "phone": tx_phone,
                    "org_id": str(org_id) if org_id is not None else "",
                    "org_name": org_name,
                    "bill_id": str(tx.get("id", "")) if tx.get("id") is not None else "",
                    "bill_no": tx.get("billNo"),
                    "amount": float(tx.get("totalPrice", 0) or 0),
                    "amount_paid": float(tx.get("amountPaid", 0) or 0),
                    "balance": float(tx.get("balance", 0) or 0),
                    "billing_mode": tx.get("billingMode", ""),
                    "status": tx.get("status", ""),
                    "payment_status": tx.get("paymentStatus", ""),
                    "date": tx.get("date", ""),
                    "notes": tx.get("notes", ""),
                    "customer_id": tx_customer_id,
                    "address": build_billzzy_address(tx_customer) if tx_customer else "",
                    "raw_transaction": tx
                })

        if len(orgs) < limit:
            break
        offset += limit

    print(f"  -> {len(all_customers)} customers, {len(all_transactions)} transactions from Billzzy")
    return {"customers": all_customers, "transactions": all_transactions}

async def fetch_all_paginated(source_name: str, url: str, api_key: str, per_request_timeout: int = 60):
    all_orders = []

    # F3: single page, no pagination
    if source_name == "f3":
        data = await fetch_url(url, api_key, timeout=per_request_timeout)
        if not data:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("orders", []))
        return []

    # GoWhats / Instaxbot: paginated with page + limit
    page = 1
    while True:
        data = await fetch_url(url, api_key, params={"page": page, "limit": 100}, timeout=per_request_timeout)
        if not data:
            break

        orders = []
        if isinstance(data, dict):
            if "orders" in data and isinstance(data["orders"], list):
                orders = data["orders"]
            elif "data" in data and isinstance(data["data"], dict):
                orders = data["data"].get("orders", [])
            elif "data" in data and isinstance(data["data"], list):
                orders = data["data"]

        if not orders:
            break

        all_orders.extend(orders)

        total = data.get("total") if isinstance(data, dict) else None
        fetched_so_far = (page - 1) * 100 + len(orders)
        if total is not None:
            if fetched_so_far >= total:
                break
        elif len(orders) < 100:
            break

        page += 1

    return all_orders

async def fetch_and_store_all():
    pool = get_pool()
    all_results = {}

    async with pool.acquire() as conn:
        for source_name, config in API_KEYS.items():
            print(f"Fetching {source_name}...")
            source_timeout = config.get("timeout", 60)
            per_request_timeout = config.get("per_request_timeout", 60)

            if source_name == "bill":
                await conn.execute("DELETE FROM raw_orders WHERE source = 'bill'")
                await conn.execute("DELETE FROM bill_transactions")
                try:
                    result = await asyncio.wait_for(
                        fetch_billzzy(config["url"], config["key"], per_request_timeout=per_request_timeout),
                        timeout=source_timeout
                    )
                except asyncio.TimeoutError:
                    print(f"  -> SKIPPED (timeout)")
                    all_results[source_name] = -1
                    continue
                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    all_results[source_name] = -1
                    continue

                for doc in result["customers"]:
                    await conn.execute("""
                        INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, customer_id, address, customer_total_spent, fetched_at)
                        VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (source, order_id) DO UPDATE SET
                            raw_data = EXCLUDED.raw_data,
                            phone = EXCLUDED.phone,
                            customer_name = EXCLUDED.customer_name,
                            customer_id = EXCLUDED.customer_id,
                            address = EXCLUDED.address,
                            customer_total_spent = EXCLUDED.customer_total_spent,
                            fetched_at = EXCLUDED.fetched_at
                    """,
                        "bill", doc["order_id"], json.dumps(doc["raw_data"], default=str),
                        doc["phone"], doc["customer_name"], doc.get("customer_id", ""),
                        doc.get("address", ""), doc.get("customer_total_spent", 0),
                        datetime.utcnow()
                    )

                for doc in result["transactions"]:
                    await conn.execute("""
                        INSERT INTO bill_transactions (order_id, phone, org_id, org_name, bill_id, bill_no, amount, amount_paid, balance, billing_mode, status, payment_status, date, notes, customer_id, address, raw_transaction, fetched_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb, $18)
                        ON CONFLICT (order_id) DO UPDATE SET
                            phone = EXCLUDED.phone, org_id = EXCLUDED.org_id, org_name = EXCLUDED.org_name,
                            bill_id = EXCLUDED.bill_id, bill_no = EXCLUDED.bill_no, amount = EXCLUDED.amount,
                            amount_paid = EXCLUDED.amount_paid, balance = EXCLUDED.balance,
                            billing_mode = EXCLUDED.billing_mode, status = EXCLUDED.status,
                            payment_status = EXCLUDED.payment_status, date = EXCLUDED.date,
                            notes = EXCLUDED.notes, customer_id = EXCLUDED.customer_id,
                            address = EXCLUDED.address, raw_transaction = EXCLUDED.raw_transaction,
                            fetched_at = EXCLUDED.fetched_at
                    """,
                        doc["order_id"], doc["phone"], doc.get("org_id", ""), doc.get("org_name", ""),
                        doc.get("bill_id"), doc.get("bill_no"), doc.get("amount", 0),
                        doc.get("amount_paid", 0), doc.get("balance", 0),
                        doc.get("billing_mode", ""), doc.get("status", ""), doc.get("payment_status", ""),
                        doc.get("date", ""), doc.get("notes", ""), doc.get("customer_id", ""),
                        doc.get("address", ""), json.dumps(doc.get("raw_transaction", {}), default=str),
                        datetime.utcnow()
                    )

                all_results["bill"] = {"customers": len(result["customers"]), "transactions": len(result["transactions"])}
                print(f"  -> {len(result['customers'])} customers + {len(result['transactions'])} transactions")
                continue

            try:
                orders = await asyncio.wait_for(
                    fetch_all_paginated(source_name, config["url"], config["key"], per_request_timeout=per_request_timeout),
                    timeout=source_timeout
                )
            except asyncio.TimeoutError:
                print(f"  -> SKIPPED (timeout)")
                all_results[source_name] = -1
                continue
            except Exception as e:
                print(f"  -> ERROR: {e}")
                all_results[source_name] = -1
                continue

            if orders:
                for order in orders:
                    phone = extract_phone(source_name, order)
                    normalized = normalize_phone(phone)
                    order_id = order.get("id") or order.get("transactionId") or order.get("_id") or order.get("orderId", "")
                    await conn.execute("""
                        INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, fetched_at)
                        VALUES ($1, $2, $3::jsonb, $4, $5, $6)
                        ON CONFLICT (source, order_id) DO UPDATE SET
                            raw_data = EXCLUDED.raw_data,
                            phone = EXCLUDED.phone,
                            customer_name = EXCLUDED.customer_name,
                            fetched_at = EXCLUDED.fetched_at
                    """,
                        source_name, str(order_id), json.dumps(order, default=str),
                        normalized, extract_name(source_name, order),
                        datetime.utcnow()
                    )
                all_results[source_name] = len(orders)
                print(f"  -> {len(orders)} orders stored")
            else:
                all_results[source_name] = 0
                print(f"  -> 0 orders")

    return all_results

def build_billzzy_address(cust: dict) -> str:
    addr = cust.get("address", "") or ""
    if addr:
        return addr
    parts = [cust.get("flatNo", ""), cust.get("street", ""),
             cust.get("district", ""), cust.get("state", ""),
             cust.get("pincode", "")]
    return ", ".join(p for p in parts if p)


def extract_phone(source: str, order: dict) -> str:
    if source == "gowhats":
        return order.get("customerPhone", "") or order.get("customerDetails", {}).get("phone", "")
    elif source == "instaxbot":
        return order.get("customer", {}).get("phone", "")
    elif source == "f3":
        cust = order.get("customerDetails", {})
        return cust.get("phone", order.get("customerPhone", ""))
    return ""

def extract_name(source: str, order: dict) -> str:
    if source == "gowhats":
        return order.get("customerDetails", {}).get("name", "")
    elif source == "instaxbot":
        return order.get("customer", {}).get("name", "")
    elif source == "f3":
        cust = order.get("customerDetails", {})
        return cust.get("name", order.get("customerName", ""))
    return ""
