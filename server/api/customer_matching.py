from services.customer_service import CustomerService
from services.customer_profile_service import CustomerProfileService
from services.alert_service import AlertService

_customer_service = CustomerService()
_profile_service = CustomerProfileService()
_alert_service = AlertService()

build_customer_profiles = _profile_service.build_profiles
get_all_customers = _customer_service.get_all
get_customer_by_id = _customer_service.get_by_id
get_alerts = _alert_service.get_all

__all__ = [
    "build_customer_profiles",
    "get_all_customers",
    "get_customer_by_id",
    "get_alerts",
]
