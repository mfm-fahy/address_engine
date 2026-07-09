import hashlib
import json
from datetime import datetime

from repositories.order_repo import RawOrderRepository
from repositories.bill_repo import BillTransactionRepository
from repositories.customer_repo import CustomerRepository
from pipeline.event_detector import detect_profile_changes
from pipeline.normalizers import normalize_date
from services.cache_manager import cache_manager
from services.profile_summarizer import get_profile_summarizer

PAID_STATUSES = {
    "paid", "shipped", "delivered", "completed", "confirmed", "processing",
    "tracked", "shipping_selected", "printed", "packed",
    "created", "dispatched"
}


def _normalize_shipping_address(sa: dict) -> dict:
    if not sa:
        return {}
    if sa.get("addressLine1"):
        return {
            "name": sa.get("name", ""),
            "phone": sa.get("phone", ""),
            "addressLine1": sa.get("addressLine1", ""),
            "addressLine2": sa.get("addressLine2", ""),
            "city": sa.get("city", ""),
            "state": sa.get("state", ""),
            "pincode": sa.get("pincode", ""),
            "country": sa.get("country", ""),
        }
    if sa.get("street"):
        return {
            "name": sa.get("name", ""),
            "phone": sa.get("phone", ""),
            "addressLine1": sa.get("street", ""),
            "addressLine2": "",
            "city": sa.get("city", ""),
            "state": sa.get("state", ""),
            "pincode": sa.get("zipCode", ""),
            "country": sa.get("country", ""),
        }
    return {}


def _pick_customer_address(orders: list) -> dict:
    candidates = []
    for o in orders:
        raw = o.get("raw", {})
        sa = raw.get("shippingAddress") or {}
        norm = _normalize_shipping_address(sa)
        if norm.get("addressLine1"):
            candidates.append((o.get("date", ""), norm))
    if not candidates:
        return {}
    candidates.sort(key=lambda x: x[0] or "", reverse=True)
    return candidates[0][1]


class CustomerProfileService:
    def __init__(self, order_repo=None, bill_repo=None, customer_repo=None):
        self._order_repo = order_repo or RawOrderRepository()
        self._bill_repo = bill_repo or BillTransactionRepository()
        self._customer_repo = customer_repo or CustomerRepository()

    async def build_profiles(self) -> dict:
        bill_cust_id_to_phone = {}
        rows = await self._order_repo.get_bill_customer_mapping()
        for r in rows:
            cid = r["customer_id"]
            if cid:
                bill_cust_id_to_phone[str(cid)] = r["phone"]

        bill_txs_by_phone = {}
        bill_txs_by_id = {}
        tx_rows = await self._bill_repo.get_all()
        for tx in tx_rows:
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

        groups = await self._order_repo.get_grouped_by_phone()

        now = datetime.utcnow()
        total_events = 0
        total_analysis = 0

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
                    if data.get("customerEmail"):
                        email = data["customerEmail"]
                    elif data.get("customerDetails", {}).get("email"):
                        email = data["customerDetails"]["email"]
                    is_new_format = "customerName" in data and "customerDetails" not in data
                    if is_new_format:
                        order_id = data.get("orderId") or data.get("orderNumber") or data.get("_id", "")
                        if not order_id:
                            raw = f"{data.get('orderDate','')}_{data.get('orderValue','')}_{data.get('customerName','')}"
                            order_id = f"f3_{hashlib.md5(raw.encode()).hexdigest()[:12]}"
                        status = data.get("status", "")
                        all_orders.append({
                            "source": source,
                            "order_id": order_id,
                            "amount": data.get("orderValue", 0),
                            "status": status,
                            "items": data.get("products", []),
                            "date": data.get("orderDate", ""),
                            "raw": data
                        })
                        if not status or status.lower() in PAID_STATUSES:
                            total_spent += float(data.get("orderValue", 0) or 0)
                    else:
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

            store_map = {}
            for order in all_orders:
                order_store_ids = set()
                for item in order.get("items", []):
                    sid = item.get("retailerId") or item.get("sku")
                    if sid:
                        order_store_ids.add(sid)
                for sid in order_store_ids:
                    if sid not in store_map:
                        store_map[sid] = {"name": sid, "type": "retailer", "order_count": 0, "total_spent": 0.0, "sources": set()}
                    store_map[sid]["order_count"] += 1
                    store_map[sid]["sources"].add(order.get("source", ""))
                    for item in order.get("items", []):
                        if (item.get("retailerId") or item.get("sku")) == sid:
                            store_map[sid]["total_spent"] += float(item.get("totalPrice", 0) or 0)

            for bill in all_bills:
                org = bill.get("org_name", "")
                if org:
                    if org not in store_map:
                        store_map[org] = {"name": org, "type": "bill_org", "order_count": 0, "total_spent": 0.0, "sources": set()}
                    store_map[org]["order_count"] += 1
                    store_map[org]["total_spent"] += float(bill.get("amount", 0) or 0)
                    store_map[org]["sources"].add("bill")

            stores_list = []
            for entry in store_map.values():
                entry["sources"] = list(entry["sources"])
                stores_list.append(entry)

            dates = [
                normalize_date(o.get("date")) for o in all_orders if o.get("date")
            ] + [
                normalize_date(b.get("date")) for b in all_bills if b.get("date")
            ]
            dates = [d for d in dates if d is not None]
            last_activity = max(dates) if dates else now

            address = _pick_customer_address(all_orders)

            new_profile = {
                "customer_id": customer_id,
                "phone": phone,
                "name": name,
                "email": email,
                "username": username,
                "total_orders": len(all_orders),
                "total_bills": len(all_bills),
                "total_spent": round(total_spent, 2),
                "orders": all_orders,
                "bills": all_bills,
                "sources": list(set(group["sources"])),
                "last_activity": last_activity,
                "updated_at": now,
                "metadata": metadata,
                "stores": stores_list,
                "address": address,
            }

            old_raw = await self._customer_repo.get_by_id_raw(customer_id)
            detection = detect_profile_changes(old_raw, new_profile)
            if detection["needs_analysis"]:
                new_profile["needs_analysis"] = True
                total_analysis += 1
            total_events += len(detection["events"])

            await self._customer_repo.upsert(new_profile)
            await cache_manager.invalidate(f"cust:id:{customer_id}")

            if detection["needs_analysis"]:
                try:
                    summarizer = get_profile_summarizer()
                    await summarizer.regenerate_summary(new_profile, customer_id)
                except Exception as e:
                    print(f"[profile-builder] Summary generation failed for {customer_id}: {e}")

        await cache_manager.invalidate("cust:list")
        await cache_manager.invalidate("dash:stats")
        total = await self._customer_repo.count_all()
        return {
            "profiles_created": total,
            "total_groups": len(groups),
            "events_detected": total_events,
            "marked_for_analysis": total_analysis,
        }
