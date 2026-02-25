# Hifdh Coach — Security Model & Compliance

## Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L1: EDGE SECURITY                                      │ │
│  │ • Cloudflare WAF + DDoS protection                     │ │
│  │ • TLS 1.3 termination                                  │ │
│  │ • Bot detection & rate limiting                        │ │
│  │ • Geographic access policies                           │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L2: API GATEWAY                                        │ │
│  │ • JWT validation (every request)                       │ │
│  │ • Per-tenant rate limiting                             │ │
│  │ • Request size limits (50MB max for audio)             │ │
│  │ • API versioning                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L3: APPLICATION SECURITY                               │ │
│  │ • RBAC enforcement (5 roles, permission matrix)        │ │
│  │ • Multi-tenant isolation (RLS + middleware)             │ │
│  │ • Input validation (Pydantic schemas)                  │ │
│  │ • CORS policy enforcement                              │ │
│  │ • Audit logging (immutable)                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L4: DATA SECURITY                                      │ │
│  │ • Encryption at rest (AES-256 / S3 SSE)                │ │
│  │ • Field-level encryption (Fernet for PII)              │ │
│  │ • PostgreSQL RLS policies                              │ │
│  │ • Encrypted backups                                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L5: INFRASTRUCTURE SECURITY                            │ │
│  │ • K8s RBAC + network policies                          │ │
│  │ • Non-root containers                                  │ │
│  │ • Secrets via external-secrets-operator                 │ │
│  │ • Private VPC for DB + Redis                           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Authentication

### JWT Token Flow

1. **Login**: User submits email + password → server verifies bcrypt hash → issues JWT pair
2. **Access Token**: Short-lived (30 min), contains: `sub` (user_id), `tid` (tenant_id), `role`
3. **Refresh Token**: Long-lived (30 days), used to obtain new access tokens
4. **Token Rotation**: Each refresh issues a new refresh token (old one invalidated)

### Token Claims

```json
{
  "sub": "uuid-user-id",
  "tid": "uuid-tenant-id",
  "role": "teacher",
  "type": "access",
  "iat": 1700000000,
  "exp": 1700001800
}
```

### Password Security

- Hashing: bcrypt with auto-salt (cost factor 12)
- Minimum length: 8 characters
- No password stored in plaintext anywhere (logs, errors, API responses)

## Authorization (RBAC)

### Role Hierarchy

```
Super Admin (4)
    └── Masjid Admin (3)
        └── Teacher (2)
            └── Parent (1)
                └── Student (0)
```

### Permission Matrix

| Permission              | Super Admin | Masjid Admin | Teacher | Student | Parent |
|------------------------|:-----------:|:------------:|:-------:|:-------:|:------:|
| manage_tenants         |      X      |              |         |         |        |
| manage_billing         |      X      |      X       |         |         |        |
| view_global_analytics  |      X      |              |         |         |        |
| manage_users           |      X      |      X       |         |         |        |
| manage_teachers        |      X      |      X       |         |         |        |
| manage_students        |      X      |      X       |    X    |         |        |
| view_recitations       |      X      |      X       |    X    |         |        |
| override_scores        |      X      |      X       |    X    |         |        |
| manage_settings        |      X      |      X       |         |         |        |
| view_analytics         |      X      |      X       |    X    |         |        |
| export_data            |      X      |      X       |         |         |        |
| view_audit_logs        |      X      |      X       |         |         |        |
| upload_recitation      |             |              |         |    X    |        |
| view_own_progress      |             |              |         |    X    |        |
| view_own_schedule      |             |              |         |    X    |        |
| view_child_progress    |             |              |         |         |   X    |

### Enforcement Points

1. **API Layer**: `require_role()` and `require_permission()` FastAPI dependencies
2. **Database Layer**: RLS policies filter by `tenant_id`
3. **Object Storage**: Per-tenant key prefixes, presigned URLs only

## Multi-Tenant Isolation

### Database Isolation (PostgreSQL RLS)

Every tenant-scoped table has:
```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
    USING (tenant_id::text = current_setting('app.current_tenant', true));
```

Middleware sets the context on every request:
```sql
SET LOCAL app.current_tenant = '{tenant_uuid}';
```

### Object Storage Isolation

- Audio files stored under: `{tenant_id}/{student_id}/{YYYY-MM}/{uuid}.{ext}`
- Presigned URLs scoped to tenant prefix
- S3 bucket policies restrict cross-tenant access

### Cache Isolation

- Redis keys prefixed: `tenant:{tenant_id}:*`
- TTL-based expiration prevents stale cross-tenant data

## Data Encryption

### At Rest

| Data Type          | Encryption Method          | Key Management    |
|-------------------|---------------------------|-------------------|
| PostgreSQL data   | Transparent Data Encryption| Managed by cloud  |
| Audio files (S3)  | AES-256 SSE              | AWS/MinIO managed |
| Sensitive PII     | Fernet (AES-128-CBC)     | App-managed key   |
| Backups           | AES-256                  | Offline key       |

### In Transit

- All client ↔ API: TLS 1.3
- API ↔ Database: TLS (enforced via connection string)
- API ↔ Redis: TLS in production
- API ↔ S3: HTTPS

### Field-Level Encryption

Sensitive fields encrypted before storage:
- Student date of birth
- Phone numbers
- Audio metadata containing personal info

```python
from app.core.encryption import encrypt_field, decrypt_field

encrypted = encrypt_field("sensitive-data")  # stored in DB
decrypted = decrypt_field(encrypted)          # used in app
```

## Audit Logging

All significant actions are logged to the `audit_logs` table:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "action": "teacher_review",
  "resource_type": "recitation",
  "resource_id": "uuid",
  "details": {
    "old_score": 0.85,
    "override_score": 0.90,
    "notes": "Student corrected during review"
  },
  "ip_address": "192.168.1.1",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Logged Actions

- User login/logout
- Score overrides (teacher)
- User creation/modification
- Role changes
- Subscription changes
- Data exports
- Settings changes

Audit logs are **append-only** — no updates or deletes allowed.

## GDPR Compliance Architecture

### Data Subject Rights

| Right                    | Implementation                                    |
|-------------------------|--------------------------------------------------|
| Right to Access         | Export endpoint returns all user data as JSON     |
| Right to Rectification  | Standard update endpoints                        |
| Right to Erasure        | Soft delete + scheduled hard purge after 30 days |
| Right to Portability    | JSON/CSV export of all student data              |
| Right to Restrict       | Account deactivation flag                        |

### Data Region Strategy

- `data_region` field on each tenant (e.g., `eu-west-1`, `me-south-1`)
- In production: deploy region-specific database replicas
- Audio storage routed to region-local S3 buckets
- Processing tasks routed to regional workers

### Data Retention

| Data Type          | Retention Period | After Expiry      |
|-------------------|-----------------|-------------------|
| Audio files       | 1 year          | Auto-deleted      |
| Recitation scores | Indefinite      | Available export  |
| Audit logs        | 7 years         | Archived to cold  |
| User PII          | Until deletion  | Hard purge + 30d  |
| Analytics         | 2 years         | Aggregated        |

## API Security

### Rate Limiting

| Endpoint Type      | Limit              |
|-------------------|-------------------|
| General API       | 60 req/min         |
| Audio upload      | 20 req/hour        |
| Auth endpoints    | 10 req/min         |
| Webhook receiver  | 100 req/min        |

### Input Validation

All inputs validated via Pydantic schemas:
- String length limits
- Enum value enforcement
- File type/size validation (audio uploads)
- SQL injection prevention (parameterized queries via SQLAlchemy)
- XSS prevention (no HTML rendering of user input)

### CORS Policy

Production:
```python
ALLOWED_ORIGINS = [
    "https://app.hifdah.com",
    "https://admin.hifdah.com",
]
```

## Teacher Override System

**Critical design principle**: AI is a supervised assistant. Teachers always have final authority.

1. AI generates scores automatically after processing
2. Teacher dashboard shows AI scores with confidence indicators
3. Teacher can:
   - Override any per-ayah score
   - Override the overall score
   - Add notes explaining the override
4. All overrides are audit-logged with before/after values
5. Override scores take precedence in retention calculations
6. Students see the final (potentially overridden) score

## Infrastructure Security

### Kubernetes

- Network policies restrict pod-to-pod communication
- Service accounts with minimal RBAC
- Secrets via external-secrets-operator (not in manifests)
- Pod security standards: restricted profile
- Non-root containers throughout

### Container Security

- Multi-stage builds (minimal runtime images)
- No root processes
- Read-only filesystem where possible
- Health checks on all services
- Resource limits preventing DoS

### Secrets Management

- Environment variables from Kubernetes secrets
- Secrets rotated quarterly
- No secrets in Docker images, git, or logs
- Stripe keys never exposed to client
