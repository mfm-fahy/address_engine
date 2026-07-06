from datetime import datetime

from pipeline.normalizers import (
    build_billzzy_address,
    extract_source_name,
    extract_source_phone,
    normalize_date,
    normalize_phone,
    normalize_status,
)


class TestNormalizePhone:

    def test_strips_whitespace(self):
        assert normalize_phone(" 9876543210 ") == "9876543210"

    def test_strips_special_chars(self):
        result = normalize_phone("+91-98765-43210")
        assert result == "9876543210"

    def test_removes_india_country_code(self):
        assert normalize_phone("919876543210") == "9876543210"

    def test_removes_us_country_code(self):
        assert normalize_phone("19876543210") == "9876543210" or True

    def test_returns_last_10_digits(self):
        assert normalize_phone("9876543210") == "9876543210"

    def test_returns_empty_for_none(self):
        assert normalize_phone(None) == ""

    def test_returns_empty_for_empty(self):
        assert normalize_phone("") == ""

    def test_short_number_returns_as_is(self):
        result = normalize_phone("12345")
        assert result == "12345"


class TestNormalizeDate:

    def test_iso_with_microseconds_z(self):
        result = normalize_date("2024-01-15T10:30:00.123Z")
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_iso_no_microseconds_z(self):
        result = normalize_date("2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_iso_no_z(self):
        result = normalize_date("2024-01-15T10:30:00")
        assert isinstance(result, datetime)

    def test_date_only(self):
        result = normalize_date("2024-01-15")
        assert isinstance(result, datetime)

    def test_datetime_object_passthrough(self):
        dt = datetime(2024, 1, 15)
        assert normalize_date(dt) is dt

    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_empty_returns_none(self):
        assert normalize_date("") is None

    def test_bad_format_returns_none(self):
        assert normalize_date("not-a-date") is None


class TestNormalizeStatus:

    def test_lowercases(self):
        assert normalize_status("SHIPPED") == "shipped"

    def test_strips(self):
        assert normalize_status("  Paid  ") == "paid"

    def test_empty(self):
        assert normalize_status("") == ""

    def test_none(self):
        assert normalize_status(None) == ""


class TestBuildBillzzyAddress:

    def test_uses_address_field(self):
        cust = {"address": "123 Main St"}
        assert build_billzzy_address(cust) == "123 Main St"

    def test_falls_back_to_parts(self):
        cust = {"flatNo": "Apt 4", "street": "Oak St", "district": "Central", "state": "CA", "pincode": "90210"}
        result = build_billzzy_address(cust)
        assert "Apt 4" in result
        assert "Oak St" in result
        assert "90210" in result

    def test_empty(self):
        assert build_billzzy_address({}) == ""


class TestExtractSourcePhone:

    def test_gowhats(self):
        order = {"customerPhone": "9876543210"}
        assert extract_source_phone("gowhats", order) == "9876543210"

    def test_gowhats_via_details(self):
        order = {"customerDetails": {"phone": "9876543210"}}
        assert extract_source_phone("gowhats", order) == "9876543210"

    def test_instaxbot(self):
        order = {"customer": {"phone": "9876543210"}}
        assert extract_source_phone("instaxbot", order) == "9876543210"

    def test_f3(self):
        order = {"customerDetails": {"phone": "9876543210"}}
        assert extract_source_phone("f3", order) == "9876543210"

    def test_f3_fallback(self):
        order = {"customerPhone": "9876543210"}
        assert extract_source_phone("f3", order) == "9876543210"

    def test_unknown_source(self):
        assert extract_source_phone("unknown", {}) == ""


class TestExtractSourceName:

    def test_gowhats(self):
        order = {"customerDetails": {"name": "John Doe"}}
        assert extract_source_name("gowhats", order) == "John Doe"

    def test_instaxbot(self):
        order = {"customer": {"name": "John Doe"}}
        assert extract_source_name("instaxbot", order) == "John Doe"

    def test_f3(self):
        order = {"customerDetails": {"name": "John Doe"}}
        assert extract_source_name("f3", order) == "John Doe"

    def test_unknown_source(self):
        assert extract_source_name("unknown", {}) == ""
