# Hifdh Coach — 90-Day Implementation Roadmap

## Overview

This roadmap takes the platform from codebase scaffold to production-ready MVP.
Assumes a team of 4-6 engineers (2 backend, 1 AI/ML, 1 frontend, 1 mobile, 1 DevOps).

---

## Phase 1: Foundation (Days 1-30)

### Week 1-2: Infrastructure & Core Backend

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Set up AWS/GCP infrastructure (VPC, RDS, ElastiCache, S3) | DevOps | 3 | P0 |
| Deploy PostgreSQL with RLS policies enabled | DevOps | 2 | P0 |
| Configure CI/CD pipeline (GitHub Actions → K8s) | DevOps | 3 | P0 |
| Run Alembic migrations on staging | Backend | 1 | P0 |
| Implement auth endpoints (login, register, refresh, password) | Backend | 3 | P0 |
| Implement tenant CRUD + middleware | Backend | 2 | P0 |
| Set up Redis caching layer | Backend | 1 | P1 |
| Set up Sentry error monitoring | DevOps | 1 | P1 |
| Set up structured logging (structlog → CloudWatch) | Backend | 1 | P1 |

**Deliverable**: Auth working, multi-tenant DB live, CI/CD pipeline green.

### Week 3-4: AI Pipeline & Audio Processing

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Procure Qur'an reference data (Uthmani text, verified) | AI | 2 | P0 |
| Set up GPU node pool (1x A100 or T4 for dev) | DevOps | 2 | P0 |
| Implement audio upload endpoint + S3 storage | Backend | 2 | P0 |
| Implement Whisper transcription service | AI | 3 | P0 |
| Implement word-level alignment engine | AI | 4 | P0 |
| Implement Levenshtein error detection | AI | 2 | P0 |
| Implement Celery task pipeline (download → transcribe → align → score) | Backend | 3 | P0 |
| Benchmark Whisper accuracy on Arabic Qur'an audio samples | AI | 2 | P0 |
| Write integration tests for the full pipeline | Backend | 2 | P1 |

**Deliverable**: Upload audio → get word-level alignment results end-to-end.

---

## Phase 2: Core Features (Days 31-60)

### Week 5-6: Scoring, Retention & Scheduling

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Implement per-ayah scoring with accuracy + tajweed | AI | 3 | P0 |
| Implement tajweed timing analysis (madd duration detection) | AI | 4 | P0 |
| Implement Ebbinghaus retention model | AI | 3 | P0 |
| Implement spaced repetition scheduler | Backend | 3 | P0 |
| Build daily schedule generation Celery task | Backend | 2 | P0 |
| Build retention decay background task | Backend | 1 | P0 |
| Implement teacher review/override endpoint | Backend | 2 | P0 |
| Implement audit logging for all overrides | Backend | 1 | P0 |
| Write unit tests for retention model and scheduler | AI | 2 | P1 |
| Tune retention model parameters with sample data | AI | 2 | P1 |

**Deliverable**: Full AI scoring pipeline with spaced repetition scheduling.

### Week 7-8: Dashboard & Mobile Core

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Set up Next.js project with Tailwind, auth flow | Frontend | 2 | P0 |
| Build teacher login + role-based routing | Frontend | 2 | P0 |
| Build teacher dashboard (stats, pending reviews) | Frontend | 3 | P0 |
| Build recitation review page (word-level highlights) | Frontend | 4 | P0 |
| Build student list + individual student view | Frontend | 3 | P0 |
| Flutter: Implement auth flow (login, token storage) | Mobile | 2 | P0 |
| Flutter: Implement audio recording with `record` package | Mobile | 3 | P0 |
| Flutter: Implement recitation upload + status polling | Mobile | 2 | P0 |
| Flutter: Build home screen with today's schedule | Mobile | 2 | P0 |
| Flutter: Build progress screen with basic stats | Mobile | 2 | P1 |

**Deliverable**: Teachers can review recitations on web. Students can record + upload on mobile.

---

## Phase 3: Polish & Launch (Days 61-90)

### Week 9-10: Billing, Analytics & Parent Portal

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Integrate Stripe (customer creation, subscription lifecycle) | Backend | 3 | P0 |
| Build subscription management UI (tier selection, billing) | Frontend | 3 | P0 |
| Implement usage metering (recitation count per tenant) | Backend | 2 | P0 |
| Build masjid analytics dashboard | Frontend | 3 | P0 |
| Build parent view (child progress, read-only) | Frontend | 2 | P1 |
| Flutter: Build retention heatmap visualization | Mobile | 3 | P1 |
| Flutter: Build revision schedule with priority indicators | Mobile | 2 | P1 |
| Implement webhook processing for payment events | Backend | 2 | P0 |
| Regional pricing implementation | Backend | 1 | P1 |
| Build data export endpoint (GDPR compliance) | Backend | 2 | P1 |

**Deliverable**: Billing live, analytics available, parent access working.

### Week 11-12: Hardening, Testing & Launch

| Task | Owner | Days | Priority |
|------|-------|------|----------|
| Load testing (simulate 100 concurrent recitation uploads) | DevOps | 2 | P0 |
| Security audit (OWASP top 10, penetration testing) | All | 3 | P0 |
| Optimize Whisper inference latency (batching, caching) | AI | 2 | P0 |
| Set up production K8s cluster with auto-scaling | DevOps | 3 | P0 |
| Configure Cloudflare CDN + WAF for production | DevOps | 1 | P0 |
| Set up production database backups (daily, encrypted) | DevOps | 1 | P0 |
| End-to-end testing across all user flows | All | 3 | P0 |
| App Store / Play Store submission preparation | Mobile | 2 | P0 |
| Documentation: API docs, deployment guide, admin manual | All | 3 | P1 |
| Onboard 3 beta masjids for validation | All | 5 | P0 |

**Deliverable**: Production deployment, beta users onboarded, app submitted to stores.

---

## Key Milestones

| Day | Milestone |
|-----|-----------|
| 14  | Auth + multi-tenant DB live on staging |
| 28  | Full AI pipeline working end-to-end |
| 42  | Scoring + retention + scheduling complete |
| 56  | Web dashboard + mobile app core features done |
| 70  | Billing integrated, analytics dashboard live |
| 84  | Security audit passed, load testing complete |
| 90  | **Production launch with 3 beta masjids** |

## Post-MVP Roadmap (Days 91-180)

- **Qira'at support**: Multiple recitation styles detection
- **Advanced tajweed model**: ML-based acoustic analysis beyond timing
- **Offline mode**: Record offline, sync when connected
- **Push notifications**: Revision reminders at preferred times
- **Teacher mobile app**: Review recitations on mobile
- **Leaderboards**: Gamification within masjid (opt-in)
- **Bulk import**: CSV upload of existing student data
- **Advanced analytics**: Cohort analysis, completion predictions
- **Multi-language UI**: Arabic, Urdu, Malay, Turkish, French
- **SSO integration**: Google, Apple sign-in
- **WebSocket real-time**: Live processing status updates
- **Custom Whisper fine-tuning**: Train on Qur'an-specific audio corpus

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Whisper accuracy on Qur'an Arabic | Benchmark early (Week 3), fine-tune if <90% WER |
| GPU cost at scale | Start with spot instances, implement request queuing |
| Audio quality variance | Client-side audio quality checks, reject low-quality |
| GDPR compliance gaps | Engage legal counsel by Day 30, implement data export early |
| App store rejection | Submit early (Day 75), budget time for revision |
| Teacher adoption resistance | Emphasize "AI assists, teacher decides" in all UX |
