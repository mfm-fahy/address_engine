from typing import Optional


EVENT_TYPES = {
    "new_order": "New Order",
    "order_updated": "Order Updated",
    "order_cancelled": "Order Cancelled",
    "payment_received": "Payment Received",
    "payment_failed": "Payment Failed",
    "product_returned": "Product Returned",
    "profile_updated": "Customer Profile Updated",
    "new_lead": "New Lead",
    "new_source": "New Data Source",
    "comment_activity": "Comment Activity",
}


PAID_STATUSES_FOR_EVENTS = {
    "paid", "shipped", "delivered", "completed", "confirmed", "processing",
    "tracked", "shipping_selected", "printed", "packed",
    "created", "dispatched",
}


def detect_profile_changes(old_profile: Optional[dict], new_data: dict) -> dict:
    events = []
    needs_analysis = False

    if old_profile is None:
        events.append({"type": "new_lead", "detail": "New customer profile created"})
        needs_analysis = True
        return {"events": events, "needs_analysis": needs_analysis}

    old_orders = old_profile.get("total_orders", 0) or 0
    new_orders = new_data.get("total_orders", 0) or 0

    if new_orders > old_orders:
        events.append({"type": "new_order", "detail": f"Orders: {old_orders} -> {new_orders}"})
        needs_analysis = True
    elif new_orders < old_orders:
        events.append({"type": "order_updated", "detail": f"Orders: {old_orders} -> {new_orders}"})
        needs_analysis = True

    old_bills = old_profile.get("total_bills", 0) or 0
    new_bills = new_data.get("total_bills", 0) or 0
    if new_bills > old_bills:
        payment_event = next(
            (e for e in events if e["type"] in ("new_order", "payment_received")), None
        )
        if not payment_event:
            events.append({"type": "payment_received", "detail": f"Bills: {old_bills} -> {new_bills}"})
            needs_analysis = True

    old_spent = float(old_profile.get("total_spent", 0) or 0)
    new_spent = float(new_data.get("total_spent", 0) or 0)
    if new_spent > old_spent:
        spent_event = next(
            (e for e in events if e["type"] in ("new_order", "payment_received")), None
        )
        if not spent_event:
            events.append({"type": "payment_received", "detail": f"Spent: {old_spent} -> {new_spent}"})
            needs_analysis = True
    elif new_spent < old_spent:
        events.append({"type": "product_returned", "detail": f"Spent decreased: {old_spent} -> {new_spent}"})
        needs_analysis = True

    old_sources = set(old_profile.get("sources", []) or [])
    new_sources = set(new_data.get("sources", []) or [])
    added = new_sources - old_sources
    if added:
        events.append({"type": "new_source", "detail": f"New source(s): {', '.join(added)}"})
        needs_analysis = True

    old_name = old_profile.get("name", "") or ""
    new_name = new_data.get("name", "") or ""
    if new_name and new_name != old_name:
        events.append({"type": "profile_updated", "detail": f"Name changed"})
        needs_analysis = True

    return {"events": events, "needs_analysis": needs_analysis}
