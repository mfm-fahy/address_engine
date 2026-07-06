# Phase 3 — Repository Layer Implementation

## Deliverables Report

### 1. Repository Architecture Diagram

```
                     ┌────────────────────────────────────────┐
                     │           Controllers / API             │
                     │  (main.py routes, MCP handlers,         │
                     │   scheduler background tasks)           │
                     └──────────┬─────────────────────────────┘
                                │ calls repository methods
                                ▼
                     ┌────────────────────────────────────────┐
                     │            Repository Layer             │
                     │                                         │
                     │  ┌─────────────────────────────────┐    │
                     │  │         BaseRepository          │    │
                     │  │  execute / fetch / fetchrow /   │    │
                     │  │  fetchval                       │    │
                     │  └────────────┬────────────────────┘    │
                     │               │                          │
                     │    ┌──────────┼──────────┐              │
                     │    ▼          ▼          ▼              │
                     │  ┌──────┐ ┌────────┐ ┌──────────┐     │
                     │  │Customer│RawOrder│BillTrans. │     │
                     │  │ Repo  │ Repo   │  Repo     │     │
                     │  ├──────┤ ├────────┤ ├──────────┤     │
                     │  │Comment│ Alert  │Dashboard │     │
                     │  │ Repo  │ Repo   │  Repo    │     │
                     │  └──────┘ └────────┘ └──────────┘     │
                     └──────────────────┬──────────────────────┘
                                        │ pool.acquire()
                                        ▼
                     ┌────────────────────────────────────────┐
                     │         asyncpg.Pool (singleton)        │
                     │         config/postgres.py              │
                     └────────────────────────────────────────┘
                                        │
                                        ▼
                     ┌────────────────────────────────────────┐
                     │              PostgreSQL                 │
                     └────────────────────────────────────────┘

Dual pool mode (MCP):
  Embedded → repositories use the shared app pool
  Standalone → repositories use MCP's own fallback pool
```

### 2. Repository Folder Structure

```
server/repositories/
    __init__.py              # Re-exports all repository classes
    base.py                  # BaseRepository — common DB operations
    customer_repo.py         # CustomerRepository — customers table
    order_repo.py            # RawOrderRepository — raw_orders table
    bill_repo.py             # BillTransactionRepository — bill_transactions table
    comment_repo.py          # CommentRepository — comments table
    alert_repo.py            # AlertRepository — alerts table
    dashboard_repo.py        # DashboardRepository — stats + source breakdown
    README.md                # This documentation
```

### 3. BaseRepository Implementation

**File: `server/repositories/base.py`**

Provides four core async methods that all repositories inherit:

| Method | Returns | Description |
|--------|---------|-------------|
| `execute(query, *args)` | `str` | Execute INSERT/UPDATE/DELETE |
| `fetch(query, *args)` | `list[Record]` | Multi-row SELECT |
| `fetchrow(query, *args)` | `Optional[Record]` | Single-row SELECT |
| `fetchval(query, *args)` | `Any` | Single-value SELECT |

**Pool resolution** (two modes):
1. **Injected pool**: Pool passed via constructor — used when pool is known at construction time (MCP handler)
2. **Lazy pool**: If no pool provided, `_get_pool()` falls back to `config.postgres.get_pool()` on first use (API modules)

### 4. Individual Repositories

#### CustomerRepository (`customer_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `count_all()` | `SELECT COUNT(*) FROM customers` | `customer_matching.py` |
| `get_all()` | All customers with JSON parsing | `customer_matching.get_all_customers()` |
| `get_by_id(customer_id)` | Single customer with `_id` + JSON parsing | `customer_matching.get_customer_by_id()` |
| `get_by_id_raw(customer_id)` | Single customer as raw dict | `handler.py get_customer_by_id` |
| `search(query)` | ILIKE search on name/email/phone/username | `handler.py search_customers` |
| `upsert(data)` | INSERT...ON CONFLICT DO UPDATE | `customer_matching.build_customer_profiles()` |
| `get_all_training()` | `SELECT *` for training export | `handler.py export_training_data` |

#### RawOrderRepository (`order_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `count_all()` | `SELECT COUNT(*) FROM raw_orders` | `main.py health` |
| `delete_by_source(source)` | `DELETE FROM raw_orders WHERE source = $1` | `data_fetcher.py` |
| `upsert_bill_customer(doc)` | INSERT for Billzzy customer records | `data_fetcher.py` |
| `upsert_generic_order(...)` | INSERT for GoWhats/Instaxbot/F3 orders | `data_fetcher.py` |
| `get_bill_customer_mapping()` | Get Billzzy customer_id→phone mapping | `customer_matching.py` |
| `get_grouped_by_phone()` | GROUP BY phone with jsonb_agg | `customer_matching.py` |
| `get_distinct_tenant_ids()` | DISTINCT tenant IDs | `comment_fetcher.py` |

#### BillTransactionRepository (`bill_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `delete_all()` | Clear table before re-fetch | `data_fetcher.py` |
| `upsert(doc)` | INSERT...ON CONFLICT DO UPDATE | `data_fetcher.py` |
| `get_all()` | SELECT * for profile builder | `customer_matching.py` |

#### CommentRepository (`comment_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `insert(...)` | INSERT INTO comments | `comment_fetcher.py` |

#### AlertRepository (`alert_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `get_all(limit)` | SELECT alerts with LIMIT | `handler.py`, `customer_matching.get_alerts()` |
| `exists_by_message_pattern(pattern)` | Check duplicate negative-comment alert | `comment_fetcher.py` |
| `insert(...)` | INSERT INTO alerts | `comment_fetcher.py` |

#### DashboardRepository (`dashboard_repo.py`)
| Method | Description | Replaces (was in) |
|--------|-------------|------------------|
| `get_stats()` | Aggregate stats (COUNT, SUM, AVG) | `handler.py` stats endpoints |
| `get_source_breakdown()` | unnest(sources) GROUP BY | `handler.py` stats endpoints |

### 5. Dependency Injection Configuration

**Two injection patterns:**

**Pattern A — Pool Injection (MCP handler):**
```python
# c360_mcp/handler.py
pool = await get_pool()
_customer_repo = CustomerRepository(pool=pool)
_alert_repo = AlertRepository(pool=pool)
_dashboard_repo = DashboardRepository(pool=pool)
```

**Pattern B — Lazy Pool Resolution (API modules):**
```python
# api/customer_matching.py
customer_repo = CustomerRepository()  # no pool arg — lazy fallback to get_pool()
await customer_repo.upsert(data)
```

This ensures:
- MCP standalone mode: repos use MCP's own asyncpg pool
- MCP embedded mode: repos use shared app pool
- API modules: repos use shared app pool (always available)

### 6. Async Repository Implementation

All repositories use `asyncpg` natively with `async/await`. Every database operation:
- Acquires a connection from the pool via `async with p.acquire() as conn:`
- Releases the connection back to the pool automatically
- Never blocks the event loop

No SQLAlchemy was introduced — all queries remain raw asyncpg for full backward compatibility.

### 7. Scheduler Integration

The scheduler (`background_fetch_loop` in `main.py`) calls the same three functions:

| Function | Before | After |
|----------|--------|-------|
| `fetch_and_store_all()` | Direct pool + raw SQL | `RawOrderRepository` + `BillTransactionRepository` |
| `build_customer_profiles()` | Direct pool + raw SQL | `RawOrderRepository` + `BillTransactionRepository` + `CustomerRepository` |
| `analyze_and_store_comments()` | Direct pool + raw SQL | `CommentRepository` + `AlertRepository` + `RawOrderRepository` |
| `get_tenant_ids()` | Direct pool + raw SQL | `RawOrderRepository` |

All function signatures, return types, and scheduler behavior are identical.

### 8. MCP Integration

MCP (`c360_mcp/handler.py`) previously had 10 raw SQL queries. Now uses:

| Tool / Resource | Repository Used |
|----------------|-----------------|
| `customers://list` | `CustomerRepository.get_all()` |
| `customers://training/export` | `CustomerRepository.get_all_training()` |
| `customers://stats` | `DashboardRepository.get_stats()` + `.get_source_breakdown()` |
| `alerts://list` | `AlertRepository.get_all(100)` |
| `export_training_data` | `CustomerRepository.get_all_training()` |
| `get_customer_by_id` | `CustomerRepository.get_by_id_raw()` |
| `search_customers` | `CustomerRepository.search()` |
| `get_customer_stats` | `DashboardRepository.get_stats()` + `.get_source_breakdown()` |
| `get_alerts` | `AlertRepository.get_all(limit)` |

Pool management (`get_pool()`, `close_pool()`) is preserved for dual-mode support.

### 9. Module-to-Repository Mapping

| Module | Previously Used | Now Uses |
|--------|-----------------|----------|
| `main.py` | `get_pool()` + raw SQL | `RawOrderRepository`, `CustomerRepository` |
| `api/data_fetcher.py` | `get_pool()` + raw SQL | `RawOrderRepository`, `BillTransactionRepository` |
| `api/customer_matching.py` | `get_pool()` + raw SQL | `RawOrderRepository`, `BillTransactionRepository`, `CustomerRepository`, `AlertRepository` |
| `api/comment_fetcher.py` | `get_pool()` + raw SQL | `CommentRepository`, `AlertRepository`, `RawOrderRepository` |
| `c360_mcp/handler.py` | `get_pool()` + raw SQL | `CustomerRepository`, `AlertRepository`, `DashboardRepository` |
| `config/postgres.py` | Schema init (DDL only) | Unchanged — schema init stays |

### 10. Migration Plan (Direct SQL → Repositories)

**Completed migration:**

1. Created `server/repositories/` package with 8 files
2. `BaseRepository` with 4 core async methods
3. 6 specialized repositories covering all 10 tables
4. Each existing module updated to use repositories
5. All public function signatures preserved
6. All return types preserved
7. MCP tests pass (no regressions)

**The only remaining SQL outside repositories:**
- `config/postgres.py` lines 34-269: DDL statements (schema initialization) — this is the correct place for DDL

### 11. Rollback Plan

All changes are additive. No existing functions were removed. Rollback options:

| Change | Rollback Action | Risk |
|--------|----------------|------|
| New `repositories/` package | `rm -rf server/repositories/` | No data loss. But API modules and MCP will fail to import. |
| Modified modules | `git checkout -- server/api/data_fetcher.py server/api/customer_matching.py server/api/comment_fetcher.py server/c360_mcp/handler.py server/main.py` | Restores all original direct SQL |

**Full rollback:** `git checkout -- server/ && rm -rf server/repositories/`

**Partial rollback (repositories stay, modules revert):**
1. `git checkout -- server/api/*.py server/c360_mcp/handler.py server/main.py`
2. Update imports to remove repository references
3. Functionally identical to pre-Phase 3 state

### Verification Summary

| Check | Status |
|-------|--------|
| All 22 Python files parse (AST) | ✅ PASS |
| All 18 import chains resolve | ✅ PASS |
| MCP tests (auth, resources, tools) | ✅ PASS (all 4 tests) |
| No raw SQL in api/ modules | ✅ PASS |
| No raw SQL in c360_mcp/handler.py | ✅ PASS |
| No raw SQL in main.py (except health) | ✅ PASS |
| Repositories use shared pool in embedded mode | ✅ DESIGN |
| Repositories use fallback pool in standalone mode | ✅ DESIGN |
