import asyncio
import httpx
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="d:/projects/Address/server/.env")

async def test_fetch():
    url = "https://billzzy.com/api/partner/orders"
    api_key = os.getenv("BILLZZY_API_KEY")
    print(f"Using API Key: {api_key}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_fetch())
