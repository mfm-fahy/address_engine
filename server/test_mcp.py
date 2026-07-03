import asyncio
import json
import sys

from c360_mcp.auth import validate_api_key, ALL_PERMISSIONS
from c360_mcp.handler import handle_list_resources, handle_list_tools


def test_auth():
    key = "c360_tr_a1ab8b0e961bdae2442ad4488fd45634564a8c8672c4a080472868efae5a0c4d"
    result = validate_api_key(key)
    assert result is not None, "Auth failed"
    assert "training:full" in result["permissions"], "Missing training:full"
    print(f"[PASS] Auth: {len(result['permissions'])} permissions")
    print(f"       Permissions: {', '.join(sorted(result['permissions']))}")


def test_bad_key():
    result = validate_api_key("bad-key")
    assert result is None, "Bad key should fail"
    print("[PASS] Bad key correctly rejected")


async def test_resources():
    resources = await handle_list_resources()
    uris = [str(r.uri) for r in resources]
    assert "customers://list" in uris
    assert "customers://training/export" in uris
    assert "customers://stats" in uris
    assert "alerts://list" in uris
    print(f"[PASS] Resources ({len(resources)}):")
    for r in resources:
        print(f"       - {r.uri}: {r.name}")


async def test_tools():
    tools = await handle_list_tools()
    names = [t.name for t in tools]
    assert "export_training_data" in names
    assert "get_customer_by_id" in names
    assert "search_customers" in names
    assert "get_customer_stats" in names
    assert "get_alerts" in names
    print(f"[PASS] Tools ({len(tools)}):")
    for t in tools:
        print(f"       - {t.name}")


async def main():
    print("=" * 50)
    print("  Customer360 MCP Server Tests")
    print("=" * 50)
    print()
    test_auth()
    test_bad_key()
    print()
    await test_resources()
    print()
    await test_tools()
    print()
    print("=" * 50)
    print("  ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
