from datetime import datetime, timedelta

from services.rule_engine import RuleEngine


def _customer(customer_id="c1"):
    return {"customer_id": customer_id, "name": "Test Customer"}


def _features(**overrides):
    base = {
        "total_orders": 5,
        "total_spent": 15000,
        "days_since_last_activity": 10,
        "churn_probability": 0.1,
        "loyalty_score": 60,
        "return_rate": 0.1,
        "payment_health_score": 80,
        "average_order_value": 3000,
        "sources": ["gowhats", "instaxbot"],
        "source_count": 2,
        "complaint_count": 0,
    }
    base.update(overrides)
    return base


class TestRuleEngine:

    def test_vip_customer(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_spent=60000), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "vip" in types

    def test_no_vip_for_low_spend(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_spent=1000), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "vip" not in types

    def test_churn_risk(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(churn_probability=0.7), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "churn_risk" in types

    def test_no_churn_risk_low_prob(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(churn_probability=0.2), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "churn_risk" not in types

    def test_dormant_customer(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(days_since_last_activity=60), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "dormant" in types

    def test_not_dormant_recent(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(days_since_last_activity=5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "dormant" not in types

    def test_not_dormant_too_long(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(days_since_last_activity=120), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "dormant" not in types

    def test_high_return_risk(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(return_rate=0.5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "return_risk" in types

    def test_no_return_risk(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(return_rate=0.1), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "return_risk" not in types

    def test_payment_risk(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(payment_health_score=20, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "payment_risk" in types

    def test_no_payment_risk_good_score(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(payment_health_score=80, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "payment_risk" not in types

    def test_upsell_opportunity(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(average_order_value=2000, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "upsell" in types

    def test_no_upsell_high_aov(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(average_order_value=10000, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "upsell" not in types

    def test_cross_sell(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(source_count=1, total_orders=5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "cross_sell" in types

    def test_no_cross_sell_multi_source(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(source_count=3, total_orders=5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "cross_sell" not in types

    def test_repeat_buyer(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_orders=5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "repeat_buyer" in types

    def test_loyal_customer(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(loyalty_score=85), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "loyal" in types

    def test_no_loyal_low_score(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(loyalty_score=30), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "loyal" not in types

    def test_new_customer(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_orders=1, total_spent=500), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "new_customer" in types

    def test_no_new_customer_multiple_orders(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_orders=5, total_spent=500), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "new_customer" not in types

    def test_complaint_risk(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(complaint_count=2, total_orders=4), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "complaint_risk" in types

    def test_no_complaint_risk_low_rate(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(complaint_count=1, total_orders=5), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "complaint_risk" not in types

    def test_seasonal_reactivation(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(days_since_last_activity=120, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "seasonal" in types

    def test_no_seasonal_active(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(days_since_last_activity=10, total_orders=3), _customer())
        types = [r["recommendation_type"] for r in recs]
        assert "seasonal" not in types

    def test_records_have_all_required_fields(self):
        engine = RuleEngine()
        recs = engine.evaluate(_features(total_spent=60000, churn_probability=0.8), _customer())
        for r in recs:
            assert "customer_id" in r
            assert "recommendation_type" in r
            assert "title" in r
            assert "description" in r
            assert "priority" in r
            assert "confidence" in r
            assert "status" in r
            assert "recommended_action" in r
            assert "expected_business_impact" in r
            assert "expires_at" in r
            assert r["status"] == "active"
            assert r["source_model"] == "rule_engine"
