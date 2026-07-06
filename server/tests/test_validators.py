from pipeline.validators import validate_bill_customer, validate_bill_tx, validate_order


class TestValidateOrder:

    def test_missing_order_id(self):
        errors = validate_order({"status": "paid"}, "gowhats")
        assert any("Missing order_id" in e for e in errors)

    def test_valid_order_passes(self):
        errors = validate_order(
            {"id": "ord1", "customerPhone": "9876543210", "totalAmount": 500, "status": "paid"},
            "gowhats",
        )
        assert errors == []

    def test_invalid_phone(self):
        errors = validate_order(
            {"id": "ord1", "customerPhone": "123", "totalAmount": 500, "status": "paid"},
            "gowhats",
        )
        assert any("Invalid phone" in e for e in errors)

    def test_missing_amount_non_gowhats(self):
        errors = validate_order({"id": "ord1", "status": "paid"}, "instaxbot")
        assert any("Missing amount" in e for e in errors)

    def test_missing_amount_gowhats_allowed(self):
        errors = validate_order({"id": "ord1", "status": "paid"}, "gowhats")
        assert not any("Missing amount" in e for e in errors)

    def test_missing_amount_pending_allowed(self):
        errors = validate_order({"id": "ord1", "status": "pending"}, "instaxbot")
        assert not any("Missing amount" in e for e in errors)

    def test_cancelled_no_amount_ok(self):
        errors = validate_order({"id": "ord1", "status": "cancelled"}, "instaxbot")
        assert not any("Missing amount" in e for e in errors)

    def test_instaxbot_phone_source(self):
        errors = validate_order(
            {"id": "ord1", "customer": {"phone": "9876543210"}, "totalAmount": 500, "status": "paid"},
            "instaxbot",
        )
        assert errors == []

    def test_f3_phone_source(self):
        errors = validate_order(
            {"id": "ord1", "customerDetails": {"phone": "9876543210"}, "totalAmount": 500, "status": "paid"},
            "f3",
        )
        assert errors == []


class TestValidateBillCustomer:

    def test_valid_customer(self):
        errors = validate_bill_customer({"id": "cust1", "phone": "9876543210"})
        assert errors == []

    def test_missing_id(self):
        errors = validate_bill_customer({"phone": "9876543210"})
        assert any("Missing customer id" in e for e in errors)

    def test_missing_phone(self):
        errors = validate_bill_customer({"id": "cust1"})
        assert any("Missing phone" in e for e in errors)

    def test_invalid_email(self):
        errors = validate_bill_customer({"id": "cust1", "phone": "9876543210", "email": "bademail"})
        assert any("Invalid email" in e for e in errors)

    def test_valid_email(self):
        errors = validate_bill_customer({"id": "cust1", "phone": "9876543210", "email": "a@b.com"})
        assert errors == []


class TestValidateBillTx:

    def test_valid_tx(self):
        errors = validate_bill_tx({"id": "tx1", "phone": "9876543210", "totalPrice": "500"})
        assert errors == []

    def test_missing_id(self):
        errors = validate_bill_tx({"phone": "9876543210"})
        assert any("Missing id" in e for e in errors)

    def test_missing_phone_with_customerid(self):
        errors = validate_bill_tx({"id": "tx1", "customerId": "c1"})
        assert errors == []

    def test_missing_phone_and_customerid(self):
        errors = validate_bill_tx({"id": "tx1"})
        assert any("Missing phone and customerId" in e for e in errors)

    def test_invalid_amount(self):
        errors = validate_bill_tx({"id": "tx1", "phone": "9876543210", "totalPrice": "abc"})
        assert any("Invalid amount" in e for e in errors)
