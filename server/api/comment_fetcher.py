from services.comment_service import CommentService

_service = CommentService()

analyze_and_store_comments = _service.analyze_and_store
get_tenant_ids = _service.get_tenant_ids

__all__ = ["analyze_and_store_comments", "get_tenant_ids"]
