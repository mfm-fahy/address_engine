# System Architecture

## Overview

Customer360 is a multi-source customer data aggregation and intelligence platform. It ingests order data from multiple e-commerce channels, builds unified customer profiles, computes behavioral features, generates rule-based and AI-powered recommendations, and exposes the data via REST API, MCP server, and dashboard.

## High-Level Architecture

```
┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐
│  Gowhats    │  │  Instaxbot   │  │  F3Engine │  │  Billzzy │
│  API        │  │  API         │  │  API      │  │  API     │
└──────┬──────┘  └──────┬───────┘  └─────┬─────┘  └────┬─────┘
       │                │                │              │
       └────────────────┴────────────────┴──────────────┘
                              │
                     ┌────────▼────────┐
                     │  Fetch Pipeline │
                     │  (pipeline/)    │
                     │  - Connectors   │
                     │  - Validators   │
                     │  - Normalizers  │
                     │  - Dedup        │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │   PostgreSQL    │◄────┐
                     │  (Source of     │     │
                     │   Truth)        │     │
                     └────────┬────────┘     │
                              │              │
              ┌───────────────┼──────────────┼──────┐
              │               │              │      │
     ┌────────▼──────┐ ┌─────▼─────┐ ┌──────▼──┐ ┌──▼───┐
      │  Customer     │ │  Feature  │ │  Rule   │
      │  Profile      │ │  Engine   │ │  Engine │
      │  Service      │ │           │ │         │
      └───────────────┘ └───────────┘ └─────────┘
                              │
       ┌──────────────────────┼──────────────────────────┐
       │                      │                          │
┌──────▼──────┐      ┌───────▼────────┐      ┌──────────▼───┐
│  FastAPI    │      │   MCP Server   │      │   Scheduler  │
│  REST API   │      │   (stdio/SSE)  │      │   Background │
│  /api/*     │      │   c360_mcp/    │      │   Worker     │
└──────┬──────┘      └───────┬────────┘      └──────────────┘
       │                     │
       │            ┌────────▼────────┐
       │            │   LLM / AI      │
       │            │   Assistant     │
       │            └─────────────────┘
       │
┌──────▼──────┐
│  Frontend   │
│  React+Vite │
│  Nginx      │
└─────────────┘
```

## Layer Responsibilities

### Pipeline Layer (`server/pipeline/`)
- Fetches data from external APIs (gowhats, instaxbot, f3, billzzy)
- Validates and normalizes incoming data
- Deduplicates orders and transactions
- Detects profile changes via event detector

### Repository Layer (`server/repositories/`)
- Direct PostgreSQL access via asyncpg
- BaseRepository for common query patterns
- One repository per entity (customer, order, alert, etc.)

### Service Layer (`server/services/`)
- Business logic orchestration
- Redis caching via CacheManager
- Customer profile assembly from multiple sources
- Feature computation and recommendation generation

### AI Layer (`server/ai/`)
- MCP client for tool discovery and execution
- Agent orchestration for multi-turn conversations

### MCP Server (`server/c360_mcp/`)
- Model Context Protocol implementation
- Resource and tool definitions
- API key authentication
- SSE and stdio transports

### Auth Layer (`server/auth/`)
- JWT-based authentication (configurable)
- Role-based access control (7 roles)
- Rate limiting for login endpoints
- Audit trail logging

### API Layer (`server/main.py`)
- FastAPI application with lifespan management
- REST endpoints for customers, alerts, recommendations, dashboard
- Health check endpoints (`/health`, `/health/live`, `/health/ready`)
- Prometheus-compatible metrics at `/metrics`
- CORS and security headers

### Data Flow

1. **Ingestion**: External APIs → Pipeline → PostgreSQL (raw_orders, bill_transactions)
2. **Profiling**: Raw data → customer_profiles table (merged by phone)
3. **Features**: Customer data → Feature Engine → customer_features table
4. **Recommendations**: Features → Rule Engine + AI Engine → recommendations table
5. **Serving**: REST API / MCP → Dashboard / AI Assistant

### Key Design Decisions

- **PostgreSQL** is the single source of truth
- **Redis** is used only for caching (TTL-based)
- **MCP** is the only interface for LLM tool access
- **Background scheduler** runs data fetch, profile building, and recommendation processing on cycles
