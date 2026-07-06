# Phase 4 — Service Layer Implementation

## Deliverables Report

### 1. Service Layer Architecture Diagram

```
                        ┌──────────────────────────────────────┐
                        │         Controllers / API             │
                        │  (main.py routes, scheduler loop)     │
                        └──────────────┬───────────────────────┘
                                       │ calls services
                                       ▼
                        ┌──────────────────────────────────────┐
                        │           Service Layer               │
                        │                                       │
                        │  ┌────────────────────────────────┐   │
                        │  │  CustomerService                │   │
                        │  │  get_all / get_by_id / search   │   │
                        │  │  count_all / get_training_data  │   │
                        │  └──────────┬─────────────────────┘   │
                        │             │                          │
                        │  ┌──────────┴─────────────────────┐   │
                        │  │  CustomerProfileService         │   │
                        │  │  build_profiles() — complex     │   │
                        │  │  aggregation business logic     │   │
                        │  └──────────┬─────────────────────┘   │
                        │             │                          │
                        │  ┌──────────┴─────────────────────┐   │
                        │  │  OrderService                   │   │
                        │  │  fetch_and_store_all() —        │   │
                        │  │  external API + DB orchestration│   │
                        │  └──────────┬─────────────────────┘   │
                        │             │                          │
                        │  ┌──────────┴─────────────────────┐   │
                        │  │  CommentService                 │   │
                        │  │  analyze_and_store() /          │   │
                        │  │  get_tenant_ids()               │   │
                        │  └──────────┬─────────────────────┘   │
                        │             │                          │
                        │  ┌──────────┴─────────────────────┐   │
                        │  │  AlertService / DashboardService│   │
                        │  │  get_all / get_stats           │   │
                        │  └──────────┬─────────────────────┘   │
                        └─────────────┼─────────────────────────┘
                                      │ calls repos
                                      ▼
                        ┌──────────────────────────────────────┐
                        │         Repository Layer (Phase 3)    │
                        └──────────────────────────────────────┘
                                      │
                                      ▼
                        ┌──────────────────────────────────────┐
                        │           PostgreSQL (asyncpg)        │
                        └──────────────────────────────────────┘

MCP Handler:
  ┌─────────────────┐     ┌─────────────────┐
  │   MCP Tools     │ ──▶ │   Services      │ ──▶ Repos
  │   (handler.py)  │     │   (customer,    │
  │   read/call     │     │    alert, dash)  │
  └─────────────────┘     └─────────────────┘
```

### 2. Service Folder Structure

```
server/services/
    __init__.py                   # Re-exports all service classes
    customer_service.py           # Customer queries (get_all, get_by_id, search, count, training)
    customer_profile_service.py   # Profile building business logic
    order_service.py              # Data ingestion from external APIs
    comment_service.py            # Comment analysis + sentiment + alert creation
    alert_service.py              # Alert queries
    dashboard_service.py          # Stats aggregation
    README.md                     # This documentation
```

### 3. Service Implementations

#### CustomerService (`customer_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `get_all()` | All customers with stores parsing | `CustomerRepository.get_all()` |
| `get_by_id(id)` | Single customer with JSON parsing | `CustomerRepository.get_by_id()` |
| `search(query)` | ILIKE search across name/email/phone/username | `CustomerRepository.search()` |
| `count_all()` | Total customer count | `CustomerRepository.count_all()` |
| `get_training_data()` | Raw rows for ML training export | `CustomerRepository.get_all_training()` |

#### CustomerProfileService (`customer_profile_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `build_profiles()` | Full profile building pipeline | `RawOrderRepository`, `BillTransactionRepository`, `CustomerRepository` |

Contains the 200+ line profile building algorithm: bill customer mapping, transaction grouping, per-source extraction, store map building, date parsing, customer upsert.

**Business rules contained:**
- `PAID_STATUSES` set for revenue calculation
- Source-specific field extraction (gowhats/instaxbot/f3/bill)
- Name consensus via `max(set(names), key=names.count)`
- Store aggregation from order items + bill organizations
- `parse_date()` utility for multiple date formats

#### OrderService (`order_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `fetch_and_store_all()` | Full data ingestion pipeline | `RawOrderRepository`, `BillTransactionRepository` |

Contains the external API fetching logic:
- Billzzy paginated customer/transaction fetch
- GoWhats/Instaxbot/F3 paginated order fetch
- `normalize_phone()` utility
- `build_billzzy_address()` utility
- `extract_phone()` / `extract_name()` per-source extractors

#### CommentService (`comment_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `analyze_and_store(tenant_id)` | Comment rules fetch + sentiment + storage | `CommentRepository`, `AlertRepository` |
| `get_tenant_ids()` | Tenant ID discovery | `RawOrderRepository` |

Contains:
- VADER sentiment analysis
- Comment rule fetching from Instaxbot API
- Alert dedup via `exists_by_message_pattern()`

#### AlertService (`alert_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `get_all(limit=100)` | Alerts with limit | `AlertRepository.get_all()` |

#### DashboardService (`dashboard_service.py`)
| Method | Description | Calls |
|--------|-------------|-------|
| `get_stats()` | Aggregated stats + source breakdown combined | `DashboardRepository.get_stats()` + `.get_source_breakdown()` |

### 4. Updated Controllers

**Before (main.py):**
```python
from api.data_fetcher import fetch_and_store_all
from api.customer_matching import build_customer_profiles, ...
from api.comment_fetcher import analyze_and_store_comments, ...

async def trigger_fetch():
    results = await fetch_and_store_all()           # called api/ module directly
    ...
```

**After (main.py):**
```python
from services.order_service import OrderService
from services.customer_profile_service import CustomerProfileService
from services.comment_service import CommentService
from services.customer_service import CustomerService
from services.alert_service import AlertService

_order_service = OrderService()
_profile_service = CustomerProfileService()
_comment_service = CommentService()
_customer_service = CustomerService()
_alert_service = AlertService()

async def trigger_fetch():
    results = await _order_service.fetch_and_store_all()  # called service directly
    ...
```

Controllers now only:
- Receive request (`@app.get/post`)
- Call appropriate service method
- Return response

All HTTP/API concerns are separated from business logic.

### 5. Updated Scheduler Integration

**Scheduler (`background_fetch_loop` in main.py):**

Before: imported functions from `api/` modules  
After: uses module-level service instances (`_order_service`, `_profile_service`, `_comment_service`)

```
Cycle 1:  _order_service.fetch_and_store_all()
Cycle 2:  _order_service.fetch_and_store_all() + _profile_service.build_profiles()
Cycle 6:  above + _comment_service.analyze_and_store() for each tenant
```

Scheduler behavior, timing, and error handling are identical.

### 6. Updated MCP Integration

MCP handler (`c360_mcp/handler.py`) now communicates with Services instead of Repositories directly:

| Tool / Resource | Phase 3 (Repo) | Phase 4 (Service) |
|----------------|----------------|-------------------|
| `customers://list` | `_customer_repo.get_all()` | `_customer_svc.get_all()` |
| `customers://training/export` | `_customer_repo.get_all_training()` | `_customer_svc.get_training_data()` |
| `customers://stats` | `_dashboard_repo.get_stats()` + `_dashboard_repo.get_source_breakdown()` | `_dashboard_svc.get_stats()` |
| `alerts://list` | `_alert_repo.get_all(100)` | `_alert_svc.get_all(100)` |
| `export_training_data` | `_customer_repo.get_all_training()` | `_customer_svc.get_training_data()` |
| `search_customers` | `_customer_repo.search(q)` | `_customer_svc.search(q)` |
| `get_customer_stats` | `_dashboard_repo.get_stats()` + `_dashboard_repo.get_source_breakdown()` | `_dashboard_svc.get_stats()` |
| `get_alerts` | `_alert_repo.get_all(limit)` | `_alert_svc.get_all(limit)` |

Pool management (`get_pool()`, `close_pool()`) is preserved for dual-mode support. Services are initialized with injected pool-aware repositories to ensure correct behavior in standalone MCP mode.

**`get_customer_by_id`** still uses `CustomerRepository` directly (for raw row access + handler-specific formatting). This is the one presentation-layer formatting concern that belongs in the handler.

### 7. Dependency Injection Configuration

**Two patterns used:**

**Pattern A — Pool Injection (MCP handler):**
```python
pool = await get_pool()
from repositories.customer_repo import CustomerRepository
_customer_svc = CustomerService(CustomerRepository(pool=pool))
```
Repo injected into service → service uses correct pool for both embedded and standalone modes.

**Pattern B — Default Constructor (API controllers):**
```python
_order_service = OrderService()  # repos use lazy pool fallback
```
Services default to lazy `get_pool()` from `config.postgres` — works because main app pool is always available.

### 8. Transaction Management

Current transaction model (unchanged from pre-Phase 4):
- Profile building: each `customer_repo.upsert()` runs independently (no BEGIN/COMMIT wrapper)
- Data ingestion: each `order_repo.upsert_*()` runs independently  
- Comment analysis: each comment insert runs independently

If any single upsert fails, it does not rollback previous upserts within the same batch. This is existing behavior and is preserved. Multi-row transaction support will be added in a future phase when required.

### 9. Logging Strategy

Logging is unchanged from the existing pattern:
- `print()` statements for: fetch progress, error messages, profile counts, comment results
- No new logging framework was introduced
- Services follow the same `print()` conventions as the original `api/` modules

### 10. Service Responsibilities

| Service | Responsibility | Does NOT contain |
|---------|---------------|------------------|
| `CustomerService` | Customer query operations | SQL, HTTP, business rules |
| `CustomerProfileService` | Profile aggregation logic | SQL, HTTP, AI logic |
| `OrderService` | External API ingestion + storage orchestration | Business rules, AI logic |
| `CommentService` | Comment rules fetch + sentiment + alert creation | SQL, API response formatting |
| `AlertService` | Alert retrieval | Business rules, SQL |
| `DashboardService` | Stats aggregation | Business rules, SQL |

### 11. Rollback Plan

All changes are additive. Rollback options:

| Change | Rollback Action | Risk |
|--------|----------------|------|
| New `services/` package | `rm -rf server/services/` | Breaks main.py + handler.py imports |
| Modified `main.py` | `git checkout server/main.py` | Restores direct-import from api/ modules |
| Modified `api/` modules | `git checkout server/api/*.py` | Restores original business logic |
| Modified `handler.py` | `git checkout server/c360_mcp/handler.py` | Restores repo-direct usage |

**Full rollback:**
```bash
git checkout -- server/main.py server/api/ server/c360_mcp/handler.py
rm -rf server/services/
```

**Partial rollback (services stay, controllers revert to api/ shims):**
- api/ shims still work (they delegate to services)
- Just revert main.py to import from api/ instead of services

### Verification Summary

| Check | Status |
|-------|--------|
| All Python files parse (AST) | ✅ PASS |
| All services instantiate correctly | ✅ PASS |
| Service utility functions work (normalize_phone) | ✅ PASS |
| API shims re-export all function signatures | ✅ PASS |
| MCP handler imports and functions resolve | ✅ PASS |
| main.py module spec loads | ✅ PASS |
| MCP tests (auth, resources, tools) | ✅ PASS (4/4) |
| Controllers use services, not api/ modules | ✅ PASS |
| Scheduler uses services | ✅ PASS |
| MCP uses services instead of repos | ✅ PASS |
