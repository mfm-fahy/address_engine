from fastapi import HTTPException, Request, status


_API_KEY: str = ""


def configure_api_key(key: str):
    global _API_KEY
    _API_KEY = key


async def verify_api_key(request: Request):
    if not _API_KEY:
        return
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not api_key:
        api_key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not api_key or api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
