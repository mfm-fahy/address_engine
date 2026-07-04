import asyncio
import httpx
import re
from datetime import datetime
from config.settings import API_KEYS
from config.database import get_db

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
            for cust in org.get("customers", []):
                phone = normalize_phone(cust.get("phone", ""))
                all_customers.append({
                    "source": "bill",
                    "order_id": f"bill_cust_{org_id}_{cust.get('id', '')}",
                    "phone": phone,
                    "customer_name": cust.get("name", ""),
                    "raw_data": {
                        "type": "customer",
                        "org_id": org_id,
                        "org_name": org_name,
                        "_bill_customer": cust
                    }
                })
            for tx in org.get("transactions", []):
                all_transactions.append({
                    "order_id": f"bill_tx_{org_id}_{tx.get('id', '')}",
                    "phone": org_phone,
                    "org_id": org_id,
                    "org_name": org_name,
                    "bill_id": tx.get("id"),
                    "bill_no": tx.get("billNo"),
                    "amount": float(tx.get("totalPrice", 0) or 0),
                    "amount_paid": float(tx.get("amountPaid", 0) or 0),
                    "balance": float(tx.get("balance", 0) or 0),
                    "billing_mode": tx.get("billingMode", ""),
                    "status": tx.get("status", ""),
                    "payment_status": tx.get("paymentStatus", ""),
                    "date": tx.get("date", ""),
                    "notes": tx.get("notes", ""),
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
    db = get_db()
    raw_col = db["raw_orders"]
    all_results = {}

    for source_name, config in API_KEYS.items():
        print(f"Fetching {source_name}...")
        source_timeout = config.get("timeout", 60)
        per_request_timeout = config.get("per_request_timeout", 60)

        if source_name == "bill":
            await raw_col.delete_many({"source": "bill"})
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

            from pymongo import UpdateOne
            batch = []
            for doc in result["customers"]:
                batch.append(UpdateOne(
                    {"source": "bill", "order_id": doc["order_id"]},
                    {"$set": {
                        "source": "bill",
                        "order_id": doc["order_id"],
                        "raw_data": doc["raw_data"],
                        "phone": doc["phone"],
                        "customer_name": doc["customer_name"],
                        "fetched_at": datetime.utcnow()
                    }},
                    upsert=True
                ))
                if len(batch) >= 500:
                    await raw_col.bulk_write(batch)
                    batch = []
            if batch:
                await raw_col.bulk_write(batch)

            tx_col = db["bill_transactions"]
            tx_batch = []
            for doc in result["transactions"]:
                tx_batch.append(UpdateOne(
                    {"order_id": doc["order_id"]},
                    {"$set": {
                        **doc,
                        "fetched_at": datetime.utcnow()
                    }},
                    upsert=True
                ))
                if len(tx_batch) >= 500:
                    await tx_col.bulk_write(tx_batch)
                    tx_batch = []
            if tx_batch:
                await tx_col.bulk_write(tx_batch)

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
            from pymongo import UpdateOne
            batch = []
            for order in orders:
                phone = extract_phone(source_name, order)
                normalized = normalize_phone(phone)
                order_id = order.get("id") or order.get("transactionId") or order.get("_id") or order.get("orderId", "")
                batch.append(UpdateOne(
                    {"source": source_name, "order_id": str(order_id)},
                    {"$set": {
                        "source": source_name,
                        "order_id": str(order_id),
                        "raw_data": order,
                        "phone": normalized,
                        "customer_name": extract_name(source_name, order),
                        "fetched_at": datetime.utcnow()
                    }},
                    upsert=True
                ))
                if len(batch) >= 500:
                    await raw_col.bulk_write(batch)
                    batch = []
            if batch:
                await raw_col.bulk_write(batch)
            all_results[source_name] = len(orders)
            print(f"  -> {len(orders)} orders stored")
        else:
            all_results[source_name] = 0
            print(f"  -> 0 orders")

    return all_results

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
