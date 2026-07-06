# Code Quality Review

## Overview

Comprehensive review of the entire `server/` Python codebase (60+ source files) covering dead code, duplication, naming consistency, type hints, error handling, and code organization.

## Observations

### Positive Findings
1. **Consistent repository pattern**: All DB access flows through `BaseRepository` with `execute`, `fetch`, `fetchrow`, `fetchval`
2. **Good separation of concerns**: Clear layers (pipeline → repos → services → API)
3. **Service-level caching**: Most services use `CacheManager` with `get_or_compute` pattern
4. **Auth is well-structured**: JWT, RBAC, rate limiting, audit trail all in dedicated module
5. **Dependency injection-friendly**: Services accept repos in `__init__` (testable)
6. **Consistent response format**: All endpoints use `ok()`, `paginated()`, or `error()` helpers

### Issues Found

#### Dead Code
| File | Line(s) | Issue |
|------|---------|-------|
| `server/api/comment_fetcher.py` | All | Thin re-export file, adds no value |
| `server/api/customer_matching.py` | All | Thin re-export file, adds no value |
| `server/api/data_fetcher.py` | All | Thin re-export file, adds no value |
| `server/config/database.py` | All | Thin convenience wrapper around postgres.py |

**Recommendation**: The `server/api/` and `server/config/database.py` files are thin wrappers. They could be consolidated, but since they don't cause issues, remove only if API consumers aren't using them.

#### Duplicate Code
| File | Lines | Issue |
|------|-------|-------|
| `server/services/dashboard_service.py` | 15-110 | Cache patterns repeat in every method (get_or_compute pattern is duplicated 8x) |
| `server/services/customer_service.py` | 15-80 | Same cache pattern duplication |
| `server/services/alert_service.py` | 10-35 | Same cache pattern |

**Recommendation**: These are acceptable — each method has unique cache key and compute logic. A decorator-based approach could reduce boilerplate but adds complexity.

#### Large Functions
| File | Function | Lines | Issue |
|------|----------|-------|-------|
| `server/c360_mcp/handler.py` | `handle_call_tool` | ~120 | Large if/elif chain per tool |
| `server/services/customer_profile_service.py` | `build_profiles` | ~200 | Complex profile assembly logic |
| `server/services/feature_engine.py` | `compute_features` | ~130 | Many sequential computations |

**Recommendation**: The large functions handle inherently complex business logic. Breaking them up could reduce readability. Flag for future refactoring only.

#### Naming Inconsistencies
| File | Issue |
|------|-------|
| `server/services/openrouter_client.py` | Module uses snake_case but `OpenRouter` has mixed case in name |
| `server/services/*.py` | Mix of `service` suffix (order_service) and no suffix (feature_engine, rule_engine) |
| `server/repositories/*.py` | Mix of `_repo`, `_repository` suffixes |

**Recommendation**: Low priority. Naming is internally consistent within each layer.

#### Missing Type Hints
| File | Lines | Issue |
|------|-------|-------|
| `server/services/customer_profile_service.py` | `build_profiles` return type | Returns `dict` but annotated as `Any` |
| `server/pipeline/normalizers.py` | `normalize_date` return type | Returns `Optional[datetime]` but not annotated |
| `server/pipeline/event_detector.py` | `detect_profile_changes` | No return type annotation |

**Recommendation**: Medium priority. Add type hints to pipeline functions for better IDE support.

#### Error Handling Patterns
| File | Issue |
|------|-------|
| `server/services/comment_service.py:45` | HTTP client errors caught generically |
| `server/services/order_service.py:80` | Similar pattern |

**Recommendation**: The generic exception handling is acceptable for a pipeline that should never crash — it logs the error and continues with the next source. However, specific exception types would be better.

## Overall Assessment

The codebase is well-structured for a production application. The issues found are minor and typical of an actively developed project. No critical bugs, security issues, or architectural problems were found.

### Priority Recommendations

1. **High**: Review and remove `server/api/` wrapper files if not externally used
2. **Medium**: Add type hints to pipeline functions (`normalizers.py`, `event_detector.py`)
3. **Low**: Consider decorator-based caching to reduce boilerplate in services
4. **Low**: Monitor large functions for future refactoring opportunities

### Unused Dependencies

- `textblob` in requirements.txt — sentiment analysis currently uses `vaderSentiment`. TextBlob may be used in a comment analysis fallback path. Keep unless confirmed unused.

### Code Formatting

The codebase would benefit from:
- `black` for consistent formatting
- `isort` for import ordering
- `flake8` or `ruff` for linting

These are optional and recommended for new contributions only.
