# Hifdh Coach — System Architecture

## Overview

Hifdh Coach is a multi-tenant SaaS platform that supports supervised Qur'an memorization
programs at masjids worldwide. AI acts as an **assistant** to human teachers — never a replacement.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │ Flutter App   │  │ Next.js Dashboard │  │ Public Marketing Site│ │
│  │ (iOS/Android) │  │ (Teachers/Admin)  │  │ (Next.js SSG)        │ │
│  └──────┬───────┘  └────────┬─────────┘  └───────────────────────┘ │
│         │                   │                                       │
└─────────┼───────────────────┼───────────────────────────────────────┘
          │                   │
          ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     EDGE / CDN LAYER                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Cloudflare (CDN + WAF + DDoS)                     │ │
│  │  • Static asset caching    • Rate limiting                     │ │
│  │  • Geographic routing      • Bot protection                    │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API GATEWAY LAYER                               │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Kong / Traefik Ingress                             │ │
│  │  • JWT validation          • Rate limiting per tenant          │ │
│  │  • Request routing         • SSL termination                   │ │
│  │  • API versioning          • Request/response logging          │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                               │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  FastAPI          │  │  Celery Workers   │  │  Celery Beat     │ │
│  │  (REST API)       │  │  (Async Tasks)    │  │  (Scheduler)     │ │
│  │                   │  │                   │  │                   │ │
│  │  • Auth           │  │  • Audio process  │  │  • Daily review  │ │
│  │  • CRUD           │  │  • AI inference   │  │    schedule gen  │ │
│  │  • Upload         │  │  • Email/notify   │  │  • Analytics     │ │
│  │  • Webhooks       │  │  • Report gen     │  │    aggregation   │ │
│  │  • Multi-tenant   │  │  • Billing meter  │  │  • Retention     │ │
│  │    middleware      │  │                   │  │    decay calc    │ │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────────┘ │
│           │                     │                                   │
└───────────┼─────────────────────┼───────────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AI INFERENCE LAYER                              │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  Whisper Large    │  │  Alignment Engine │  │  Tajweed         │ │
│  │  (GPU Node)       │  │  (Forced Align)   │  │  Analyzer        │ │
│  │                   │  │                   │  │                   │ │
│  │  • Transcription  │  │  • Word-level     │  │  • Madd duration │ │
│  │  • Word timestamps│  │    matching       │  │  • Ghunnah detect│ │
│  │  • Language detect│  │  • Levenshtein    │  │  • Timing scores │ │
│  │                   │  │    distance       │  │                   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │  Retention Model  │  │  Schedule Engine  │                       │
│  │  (Ebbinghaus)     │  │  (Spaced Rep.)    │                       │
│  │                   │  │                   │                        │
│  │  • Stability calc │  │  • Review queue   │                       │
│  │  • Decay predict  │  │  • Priority sort  │                       │
│  │  • Confidence     │  │  • Load balance   │                       │
│  └──────────────────┘  └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                      │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  PostgreSQL       │  │  Redis            │  │  S3 / MinIO      │ │
│  │  (Primary DB)     │  │  (Cache + Queue)  │  │  (Object Store)  │ │
│  │                   │  │                   │  │                   │ │
│  │  • Tenant data    │  │  • Session cache  │  │  • Audio files   │ │
│  │  • RLS policies   │  │  • Rate limits    │  │  • Encrypted     │ │
│  │  • Encrypted cols │  │  • Celery broker  │  │  • Per-tenant    │ │
│  │  • Audit logs     │  │  • Leaderboards   │  │    buckets       │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Multi-Tenant Isolation Strategy

We use **shared database, separate schemas** with PostgreSQL Row-Level Security (RLS):

1. Every table has a `tenant_id` column (UUID FK → `tenants`)
2. RLS policies enforce `tenant_id = current_setting('app.current_tenant')`
3. Application middleware sets tenant context on every request
4. Audio files stored in per-tenant prefixed paths in object storage
5. Redis keys prefixed with `tenant:{id}:`
6. Celery tasks carry tenant_id in metadata

This approach balances isolation with operational simplicity at scale.

## Data Flow: Student Recitation

```
Student records recitation (Flutter app)
    │
    ▼
Audio uploaded via REST API (multipart, encrypted in transit)
    │
    ▼
Audio stored in S3/MinIO (encrypted at rest, AES-256)
    │
    ▼
Celery task queued: `process_recitation`
    │
    ├─► Whisper Large transcription (GPU node)
    │   └─► Word-level timestamps + Arabic text
    │
    ├─► Forced alignment against reference Qur'an text
    │   └─► Per-word match/mismatch with positions
    │
    ├─► Levenshtein distance calculation
    │   └─► Error classification: missing / added / substituted
    │
    ├─► Tajweed timing analysis
    │   └─► Madd durations, ghunnah detection
    │
    ├─► Retention scoring (Ebbinghaus model)
    │   └─► Per-ayah stability + predicted recall probability
    │
    └─► Revision schedule update (spaced repetition)
        └─► Next review dates for each memorized section
    │
    ▼
Results stored in DB, teacher notified
Teacher reviews, can override any AI assessment
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Framework | FastAPI | Async Python, OpenAPI auto-docs, Pydantic validation |
| Database | PostgreSQL | RLS for multi-tenant, JSONB for flexible metadata |
| Task Queue | Celery + Redis | Battle-tested, GPU task routing, retry logic |
| AI Model | Whisper Large v3 | Best Arabic transcription accuracy available |
| Object Store | S3-compatible | Encryption at rest, lifecycle policies |
| Auth | JWT + Refresh tokens | Stateless, works with mobile + web |
| Billing | Stripe | Subscriptions, metered billing, global payments |
| Container | Docker + K8s | Horizontal scaling, GPU node pools |

## Service Communication

- **Synchronous**: REST API (client → FastAPI)
- **Asynchronous**: Celery tasks (FastAPI → Workers)
- **Real-time**: WebSocket (progress updates during processing)
- **Inter-service**: Redis pub/sub for cache invalidation
