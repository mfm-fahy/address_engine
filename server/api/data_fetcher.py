from services.order_service import OrderService, normalize_phone

_service = OrderService()

fetch_and_store_all = _service.fetch_and_store_all

__all__ = ["fetch_and_store_all", "normalize_phone"]
