import asyncio

import httpx

from pipeline.normalizers import normalize_phone, build_billzzy_address


async def fetch_url(url: str, api_key: str, params: dict = None, timeout: int = 60, headers_extra: dict = None):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **(headers_extra or {})}
    parsed = httpx.URL(url)
    merged = dict(parsed.params)
    if params:
        merged.update(params)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(str(parsed.copy_with(params=None)), headers=headers, params=merged)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[connector] Error fetching {url}: {e}")
            return None


async def fetch_paginated(source_name: str, url: str, api_key: str, per_request_timeout: int = 60):
    if source_name == "f3":
        data = await fetch_url(url, api_key, timeout=per_request_timeout)
        if not data:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("orders", []))
        return []

    all_orders = []
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


async def fetch_billzzy_all(url: str, api_key: str, per_request_timeout: int = 120):
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

    return all_customers, all_transactions
