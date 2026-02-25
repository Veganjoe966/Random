# Hifdh Coach — API Reference

Base URL: `https://api.hifdah.com/api/v1`

All endpoints require `Authorization: Bearer <jwt>` unless noted otherwise.

---

## Authentication

### POST /auth/login
Authenticate and receive JWT tokens.

**Request:**
```json
{ "email": "user@example.com", "password": "securepass" }
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "Ahmad",
    "last_name": "Ali",
    "role": "student",
    "tenant_id": "uuid"
  }
}
```

### POST /auth/register
Register a new student or parent account.

**Request:**
```json
{
  "email": "student@example.com",
  "password": "securepass",
  "first_name": "Ahmad",
  "last_name": "Ali",
  "role": "student",
  "tenant_slug": "masjid-al-noor"
}
```

### POST /auth/refresh
Exchange refresh token for new access token.

### POST /auth/change-password
Change authenticated user's password.

### GET /auth/me
Get authenticated user profile.

---

## Recitations

### POST /recitations/upload
Upload recitation audio for AI analysis.

**Permission**: `upload_recitation` (students)

**Request**: `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| audio | File | Yes | Audio file (webm, wav, mp3, m4a, ogg). Max 50MB. |
| surah_number | int | Yes | 1-114 |
| ayah_start | int | Yes | Starting ayah number |
| ayah_end | int | Yes | Ending ayah number (inclusive) |
| recitation_type | string | No | `new_lesson`, `revision`, or `test` |

**Response (201):** Recitation object with status `processing`.

### GET /recitations/{id}
Get detailed recitation results with per-word analysis.

**Response includes:**
- Overall accuracy and tajweed scores
- Per-ayah breakdown
- Word-level analysis (correct/substituted/missing/added)
- Teacher review status and notes

### GET /recitations/
List recitations with pagination and filters.

**Query params:** `student_id`, `surah_number`, `status`, `page`, `page_size`

### POST /recitations/{id}/review
Teacher reviews and optionally overrides AI scores.

**Permission**: `override_scores` (teachers, admins)

**Request:**
```json
{
  "override_score": 0.92,
  "notes": "Student self-corrected, good effort",
  "ayah_overrides": [
    { "ayah_score_id": "uuid", "override_score": 0.85 }
  ]
}
```

---

## Students

### GET /students/me/profile
Get authenticated student's profile.

### GET /students/me/schedule
Get today's AI-generated revision schedule.

**Response:**
```json
{
  "schedule_date": "2025-01-15T00:00:00Z",
  "items": [
    {
      "surah_number": 2,
      "ayah_start": 255,
      "ayah_end": 257,
      "predicted_retention": 0.72,
      "priority": "high",
      "reason": "retention_below_threshold",
      "estimated_seconds": 135,
      "mastery_level": "reviewing"
    }
  ],
  "total_items": 8,
  "total_ayahs": 15,
  "estimated_minutes": 12,
  "critical_count": 2,
  "high_count": 3
}
```

### GET /students/{id}/profile
Get a specific student's profile (teacher/admin).

### GET /students/
List students with optional teacher filter.

---

## Analytics

### GET /analytics/masjid
Masjid-level analytics dashboard data.

**Permission**: `masjid_admin` or higher

### GET /analytics/teacher/summary
Teacher's student summary (pending reviews, at-risk students).

**Permission**: `teacher` or higher

---

## Tenants

### POST /tenants/
Create a new masjid. **Super admin only.**

### GET /tenants/me
Get current user's masjid info.

### PATCH /tenants/{id}
Update masjid settings.

### GET /tenants/
List all tenants. **Super admin only.**

---

## Billing

### GET /billing/tiers?country=US
Get subscription tiers with regional pricing.

### POST /billing/subscribe
Create or upgrade subscription.

### POST /billing/cancel
Cancel subscription at period end.

### POST /billing/webhook
Stripe webhook receiver (no auth, signature verified).

### GET /billing/usage
Get current period usage metrics.

---

## Health

### GET /health
Basic health check. No auth required.

### GET /ready
Kubernetes readiness probe. Checks DB + Redis. No auth required.
