from datetime import datetime, timedelta


class RuleEngine:
    def evaluate(self, features: dict, customer: dict) -> list[dict]:
        recommendations = []

        f = features
        total_orders = f.get("total_orders", 0)
        total_spent = f.get("total_spent", 0)
        days_since = f.get("days_since_last_activity", 999)
        churn_prob = f.get("churn_probability", 0)
        loyalty = f.get("loyalty_score", 0)
        return_rate = f.get("return_rate", 0)
        payment_health = f.get("payment_health_score", 100)
        avg_order = f.get("average_order_value", 0)
        sources = f.get("sources", []) or []
        complaint_count = f.get("complaint_count", 0)
        source_count = f.get("source_count", 0)

        now = datetime.utcnow()

        # VIP Customer
        if total_spent >= 50000:
            recommendations.append(self._build(
                customer, "vip", "VIP Customer",
                f"High-value customer with ₹{total_spent:,.0f} lifetime spend",
                "high", 0.95,
                "Offer exclusive VIP benefits and personalized service",
                "Increased retention and higher lifetime value",
                60, f,
            ))

        # Churn Risk
        if churn_prob >= 0.5:
            recommendations.append(self._build(
                customer, "churn_risk", "Churn Risk",
                f"Customer has not been active in {days_since} days (churn probability: {churn_prob:.0%})",
                "high", min(churn_prob + 0.1, 0.99),
                "Send re-engagement offer via WhatsApp and email",
                "Prevent churn and recover revenue",
                30, f,
            ))

        # Dormant Customer
        if 30 <= days_since <= 90:
            recommendations.append(self._build(
                customer, "dormant", "Dormant Customer",
                f"Customer inactive for {days_since} days",
                "medium", 0.75,
                "Run a win-back campaign with a special discount",
                "Re-activate customer and generate repeat purchase",
                45, f,
            ))

        # High Return Risk
        if return_rate >= 0.3:
            recommendations.append(self._build(
                customer, "return_risk", "High Return Risk",
                f"Return rate is {return_rate:.0%}, above acceptable threshold",
                "high", min(return_rate + 0.1, 0.95),
                "Review order quality and consider return policy enforcement",
                "Reduce losses from excessive returns",
                30, f,
            ))

        # Payment Risk
        if payment_health < 40 and total_orders > 0:
            recommendations.append(self._build(
                customer, "payment_risk", "Payment Risk",
                f"Low payment health score ({payment_health}/100)",
                "high", 0.85,
                "Contact customer to resolve outstanding payments",
                "Improve cash flow and reduce outstanding",
                15, f,
            ))

        # Upsell Opportunity
        if avg_order < 5000 and total_orders >= 2:
            recommendations.append(self._build(
                customer, "upsell", "Upsell Opportunity",
                f"Average order value ₹{avg_order:,.0f} — room for growth",
                "medium", 0.70,
                "Recommend premium products or bundle deals",
                "Increase average order value",
                30, f,
            ))

        # Cross-Sell Opportunity
        if source_count <= 1 and total_orders >= 3:
            recommendations.append(self._build(
                customer, "cross_sell", "Cross-Sell Opportunity",
                f"Customer uses only {source_count} channel(s) — expand reach",
                "medium", 0.65,
                "Promote other sales channels and product categories",
                "Increase revenue per customer through multi-channel engagement",
                45, f,
            ))

        # Repeat Buyer
        if 3 <= total_orders <= 10:
            recommendations.append(self._build(
                customer, "repeat_buyer", "Repeat Buyer",
                f"Customer has placed {total_orders} orders",
                "low", 0.60,
                "Send loyalty program invitation and referral bonus",
                "Convert to regular customer",
                60, f,
            ))

        # Loyal Customer
        if loyalty >= 70:
            recommendations.append(self._build(
                customer, "loyal", "Loyal Customer",
                f"Loyalty score: {loyalty}/100",
                "medium", 0.90,
                "Reward with exclusive discounts and early access",
                "Strengthen brand loyalty and advocacy",
                90, f,
            ))

        # New Customer
        if total_orders <= 1 and total_spent > 0:
            recommendations.append(self._build(
                customer, "new_customer", "New Customer",
                "First-time buyer — nurture the relationship",
                "medium", 0.80,
                "Send onboarding sequence with product tips and support info",
                "Convert first-time buyer into repeat customer",
                30, f,
            ))

        # High Complaint Rate
        if complaint_count >= 2 and total_orders > 0:
            ratio = complaint_count / total_orders
            if ratio >= 0.3:
                recommendations.append(self._build(
                    customer, "complaint_risk", "High Complaint Rate",
                    f"{complaint_count} complaints out of {total_orders} orders ({ratio:.0%})",
                    "high", 0.80,
                    "Reach out personally to address concerns and improve experience",
                    "Reduce churn from dissatisfied customers",
                    30, f,
                ))

        # Seasonal / Inactive + History
        if days_since >= 90 and total_orders >= 2:
            recommendations.append(self._build(
                customer, "seasonal", "Seasonal Reactivation",
                f"Previously active customer, inactive for {days_since} days",
                "medium", 0.70,
                "Target with seasonal promotions and new arrivals",
                "Re-engage past customers with relevant offers",
                60, f,
            ))

        return recommendations

    def _build(self, customer: dict, rec_type: str, title: str, description: str,
               priority: str, confidence: float, action: str, impact: str,
               expires_days: int, features: dict) -> dict:
        now = datetime.utcnow()
        return {
            "customer_id": customer["customer_id"],
            "recommendation_type": rec_type,
            "title": title,
            "description": description,
            "priority": priority,
            "confidence": round(confidence, 4),
            "status": "active",
            "recommended_action": action,
            "expected_business_impact": impact,
            "feature_snapshot": features,
            "metadata": {"generated_by": "rule_engine", "rule_version": 1},
            "source_model": "rule_engine",
            "expires_at": now + timedelta(days=expires_days),
        }
