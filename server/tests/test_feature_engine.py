from datetime import datetime

from services.feature_engine import FeatureEngine, _days_ago, _parse_ts


class TestFeatureEngineHelpers:

    def test_days_ago_with_iso_string(self):
        d = datetime.utcnow()
        result = _days_ago(d.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
        assert 0 <= result <= 1

    def test_days_ago_with_date_string(self):
        result = _days_ago(datetime.utcnow().strftime("%Y-%m-%d"))
        assert 0 <= result <= 1

    def test_days_ago_empty(self):
        assert _days_ago(None) == 999
        assert _days_ago("") == 999

    def test_days_ago_bad_format(self):
        assert _days_ago("not-a-date") == 999

    def test_parse_ts_from_number(self):
        ts = 1234567890.0
        assert _parse_ts(ts) == ts

    def test_parse_ts_from_datetime(self):
        dt = datetime.utcnow()
        result = _parse_ts(dt)
        assert abs(result - dt.timestamp()) < 0.001

    def test_parse_ts_from_zero(self):
        assert _parse_ts(0) == 0.0


class TestFeatureEngineCompute:

    def test_empty_customer(self):
        engine = FeatureEngine()
        features = engine.compute_features({"customer_id": "c1"})
        assert features["total_orders"] == 0
        assert features["total_spent"] == 0
        assert features["lifetime_value"] == 0
        assert features["churn_probability"] > 0.5

    def test_basic_features(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 10,
            "total_spent": 50000,
            "sources": ["gowhats"],
            "orders": [
                {"amount": 5000, "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "status": "delivered"},
                {"amount": 5000, "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert features["total_orders"] == 10
        assert features["lifetime_value"] == 50000
        assert features["average_order_value"] == 5000
        assert features["source_count"] == 1

    def test_churn_probability_high(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 1,
            "total_spent": 100,
            "last_activity": "2020-01-01T00:00:00Z",
            "orders": [],
        }
        features = engine.compute_features(customer)
        assert features["days_since_last_activity"] > 100
        assert features["churn_probability"] > 0.5

    def test_loyalty_score_high(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 20,
            "total_spent": 50000,
            "sources": ["gowhats", "instaxbot"],
            "orders": [
                {"amount": 2500, "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert features["loyalty_score"] > 50

    def test_return_rate(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 10,
            "total_spent": 10000,
            "orders": [
                {"amount": 1000, "status": "returned"},
                {"amount": 1000, "status": "returned"},
                {"amount": 1000, "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert features["return_rate"] > 0

    def test_payment_health_score(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 5,
            "total_spent": 50000,
            "orders": [{"amount": 10000, "status": "paid"} for _ in range(5)],
        }
        features = engine.compute_features(customer)
        assert features["payment_health_score"] > 50
        assert features["payment_health_score"] <= 100

    def test_favorite_products(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 3,
            "total_spent": 3000,
            "orders": [
                {"items": [{"name": "Product A"}, {"name": "Product B"}], "status": "delivered"},
                {"items": [{"name": "Product A"}], "status": "delivered"},
                {"items": [{"name": "Product C"}], "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert "Product A" in features["favorite_products"]
        assert features["complaint_count"] == 0

    def test_complaint_count(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 5,
            "total_spent": 5000,
            "orders": [
                {"amount": 1000, "status": "cancelled"},
                {"amount": 1000, "status": "cancelled"},
                {"amount": 1000, "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert features["complaint_count"] == 2

    def test_30d_90d_aggregates(self):
        engine = FeatureEngine()
        customer = {
            "customer_id": "c1",
            "total_orders": 2,
            "total_spent": 2000,
            "orders": [
                {"amount": 1000, "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "status": "delivered"},
                {"amount": 1000, "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "status": "delivered"},
            ],
        }
        features = engine.compute_features(customer)
        assert features["total_orders_30d"] == 2
        assert features["total_spent_30d"] == 2000

    def test_feature_snapshot_present(self):
        engine = FeatureEngine()
        customer = {"customer_id": "c1", "total_orders": 0, "total_spent": 0}
        features = engine.compute_features(customer)
        assert "features_snapshot" in features
        assert features["features_snapshot"] == features
