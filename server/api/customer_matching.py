import json
from datetime import datetime
from config.postgres import get_pool

PAID_STATUSES = {
    "paid", "shipped", "delivered", "completed", "confirmed", "processing",
    "tracked", "shipping_selected", "printed", "packed",
    "created", "dispatched"
}


async def build_customer_profiles():
    pool = get_pool()

    async with pool.acquire() as conn:
        bill_cust_id_to_phone = {}
        rows = await conn.fetch("SELECT phone, customer_id FROM raw_orders WHERE source = 'bill' AND raw_data->>'type' = 'customer'")
        for r in rows:
            cid = r["customer_id"]
            if cid:
                bill_cust_id_to_phone[str(cid)] = r["phone"]

        bill_txs_by_phone = {}
        bill_txs_by_id = {}
        tx_rows = await conn.fetch("SELECT * FROM bill_transactions")
        for tx in tx_rows:
            tx = dict(tx)
            phone = tx.get("phone", "")
            if not phone:
                cid = tx.get("customer_id", "")
                phone = bill_cust_id_to_phone.get(str(cid), "")
            if phone not in bill_txs_by_phone:
                bill_txs_by_phone[phone] = []
            bill_txs_by_phone[phone].append(tx)

            bid = tx.get("bill_id")
            if bid is not None:
                bid = str(bid)
                if bid not in bill_txs_by_id:
                    bill_txs_by_id[bid] = []
                bill_txs_by_id[bid].append(tx)

        groups = await conn.fetch("""
            SELECT
                phone,
                jsonb_agg(jsonb_build_object(
                    'source', source,
                    'data', raw_data,
                    'customer_name', customer_name,
                    'customer_total_spent', customer_total_spent
                )) AS records,
                array_agg(DISTINCT customer_name) FILTER (WHERE customer_name != '') AS names,
                array_agg(DISTINCT source) AS sources
            FROM raw_orders
            WHERE phone != ''
            GROUP BY phone
        """)

    now = datetime.utcnow()

    async with pool.acquire() as conn:
        for group in groups:
            phone = group["phone"]
            names_raw = group["names"] or []
            names = [n for n in names_raw if n]
            name = max(set(names), key=names.count) if names else "Unknown"
            records = json.loads(group["records"]) if isinstance(group["records"], str) else group["records"]

            email = ""
            username = ""
            all_orders = []
            all_bills = []
            total_spent = 0.0
            bill_total_from_api = 0.0
            metadata = {}
            bill_customer_id = ""

            for rec in records:
                data = rec["data"]
                source = rec["source"]

                if source == "gowhats":
                    cust = data.get("customerDetails", {})
                    if cust.get("email"):
                        email = cust["email"]
                    all_orders.append({
                        "source": source,
                        "order_id": str(data.get("orderId", data.get("orderNumber", ""))),
                        "amount": data.get("totalAmount", 0),
                        "status": data.get("status", ""),
                        "items": data.get("items", []),
                        "date": data.get("createdAt", ""),
                        "raw": data
                    })
                    if data.get("status", "").lower() in PAID_STATUSES:
                        total_spent += float(data.get("totalAmount", 0) or 0)

                elif source == "instaxbot":
                    cust = data.get("customer", {})
                    if cust.get("email"):
                        email = cust["email"]
                    if cust.get("username"):
                        username = cust["username"]
                    all_orders.append({
                        "source": source,
                        "order_id": data.get("orderId", data.get("id")),
                        "amount": data.get("totalAmount", 0),
                        "status": data.get("status", ""),
                        "items": data.get("items", []),
                        "date": data.get("createdAt", ""),
                        "raw": data
                    })
                    if data.get("status", "").lower() in PAID_STATUSES:
                        total_spent += float(data.get("totalAmount", 0) or 0)

                elif source == "f3":
                    cust = data.get("customerDetails", {})
                    if cust.get("email"):
                        email = cust["email"]
                    if data.get("customerEmail"):
                        email = data["customerEmail"]
                    all_orders.append({
                        "source": source,
                        "order_id": data.get("orderId", data.get("orderNumber", data.get("_id", ""))),
                        "amount": data.get("totalAmount", data.get("total", data.get("amount", 0))),
                        "status": data.get("status", ""),
                        "items": data.get("items", []),
                        "date": data.get("createdAt", data.get("orderDate", "")),
                        "raw": data
                    })
                    if data.get("status", "").lower() in PAID_STATUSES:
                        total_spent += float(data.get("totalAmount", data.get("total", data.get("amount", 0))) or 0)

                elif source == "bill":
                    cust = data.get("_bill_customer", {})
                    if cust.get("email"):
                        email = cust["email"]
                    if cust.get("name"):
                        name = cust["name"]
                    bill_total_from_api = float(rec.get("customer_total_spent", 0) or 0)
                    if cust:
                        metadata = {k: cust[k] for k in cust if k != "id"}
                        address = cust.get("address", "") or ", ".join(
                            p for p in [cust.get("flatNo", ""), cust.get("street", ""),
                                        cust.get("district", ""), cust.get("state", ""),
                                        cust.get("pincode", "")] if p
                        )
                        metadata["address"] = address
                        bill_customer_id = cust.get("id", "")
                    for b in (cust.get("bills") or cust.get("transactions") or []):
                        all_bills.append({
                            "transaction_id": b.get("id") or b.get("billId"),
                            "bill_no": b.get("billNo") or b.get("bill_no"),
                            "amount": float(b.get("totalPrice") or b.get("amount") or 0),
                            "status": b.get("status", ""),
                            "payment_status": b.get("paymentStatus", ""),
                            "items": b.get("items") or b.get("order") or [],
                            "date": b.get("date", ""),
                        "org_name": data.get("org_name", "")
                    })

            if not all_bills:
                tx_docs = bill_txs_by_phone.get(phone, [])
                if not tx_docs and bill_customer_id:
                    tx_docs = bill_txs_by_id.get(str(bill_customer_id), [])
                for tx in tx_docs:
                    all_bills.append({
                        "transaction_id": tx.get("bill_id"),
                        "bill_no": tx.get("bill_no"),
                        "amount": tx.get("amount", 0),
                        "status": tx.get("status", ""),
                        "payment_status": tx.get("payment_status", ""),
                        "items": [],
                        "date": tx.get("date", ""),
                        "org_name": tx.get("org_name", ""),
                        "address": tx.get("address", "")
                    })
                    if tx.get("status", "").lower() in PAID_STATUSES:
                        total_spent += float(tx.get("amount", 0) or 0)
                if not tx_docs and bill_total_from_api:
                    total_spent = bill_total_from_api

            customer_id = f"CUST{phone}"

            dates = [
                parse_date(o.get("date")) for o in all_orders if o.get("date")
            ] + [
                parse_date(b.get("date")) for b in all_bills if b.get("date")
            ]
            dates = [d for d in dates if d is not None]
            last_activity = max(dates) if dates else now

            await conn.execute("""
                INSERT INTO customers (
                    customer_id, phone, name, email, username,
                    total_orders, total_bills, total_spent,
                    orders, bills, sources, last_activity, updated_at, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, $11, $12, $13, $14::jsonb)
                ON CONFLICT (customer_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    username = EXCLUDED.username,
                    total_orders = EXCLUDED.total_orders,
                    total_bills = EXCLUDED.total_bills,
                    total_spent = EXCLUDED.total_spent,
                    orders = EXCLUDED.orders,
                    bills = EXCLUDED.bills,
                    sources = EXCLUDED.sources,
                    last_activity = EXCLUDED.last_activity,
                    updated_at = EXCLUDED.updated_at,
                    metadata = EXCLUDED.metadata
            """,
                customer_id, phone, name, email, username,
                len(all_orders), len(all_bills), round(total_spent, 2),
                json_dumps(all_orders), json_dumps(all_bills),
                list(set(group["sources"])),
                last_activity, now, json_dumps(metadata)
            )

        total = await conn.fetchval("SELECT COUNT(*) FROM customers")

    return {"profiles_created": total, "total_groups": len(groups)}


async def get_all_customers():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                customer_id, phone, name, email, username,
                total_orders, total_bills, total_spent,
                sources, comment_count, last_activity, updated_at, metadata
            FROM customers
            ORDER BY last_activity DESC NULLS LAST
        """)
        return [dict(r) for r in rows]


async def get_customer_by_id(customer_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT customer_id, phone, name, email, username, total_orders, total_bills, total_spent, orders, bills, sources, comment_count, last_activity, created_at, updated_at, metadata FROM customers WHERE customer_id = $1 OR phone = $1",
                customer_id
            )
            if row:
                result = dict(row)
                result["_id"] = result.pop("customer_id", "")
                for col in ("orders", "bills", "metadata"):
                    if isinstance(result.get(col), str):
                        result[col] = json.loads(result[col])
                return result
            return None


async def get_alerts():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100
        """)
        result = []
        for r in rows:
            d = dict(r)
            d["_id"] = str(d.pop("id"))
            result.append(d)
        return result


def json_dumps(obj):
    return json.dumps(obj, default=str)


def parse_date(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
