"""Initial schema with RLS policies.

Revision ID: 001
Create Date: 2025-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Tenants ──────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("subscription_tier", sa.String(50), server_default="free"),
        sa.Column("subscription_status", sa.String(50), server_default="active"),
        sa.Column("billing_email", sa.String(255), nullable=True),
        sa.Column("max_students", sa.Integer, server_default="25"),
        sa.Column("max_teachers", sa.Integer, server_default="3"),
        sa.Column("max_audio_storage_gb", sa.Integer, server_default="5"),
        sa.Column("max_monthly_recitations", sa.Integer, server_default="500"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("data_region", sa.String(20), server_default="us-east-1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # ── Users ────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_verified", sa.Boolean, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_role", "users", ["role"])

    # ── Teacher Profiles ─────────────────────────────────────────────
    op.create_table(
        "teacher_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("specialization", sa.String(100), nullable=True),
        sa.Column("ijazah_info", sa.Text, nullable=True),
        sa.Column("max_students", sa.Integer, server_default="30"),
        sa.Column("is_accepting_students", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Student Profiles ─────────────────────────────────────────────
    op.create_table(
        "student_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("date_of_birth", sa.String(10), nullable=True),
        sa.Column("enrollment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_surah", sa.Integer, server_default="1"),
        sa.Column("current_ayah", sa.Integer, server_default="1"),
        sa.Column("total_ayahs_memorized", sa.Integer, server_default="0"),
        sa.Column("total_juz_completed", sa.Integer, server_default="0"),
        sa.Column("average_retention_score", sa.Float, server_default="0"),
        sa.Column("average_accuracy_score", sa.Float, server_default="0"),
        sa.Column("streak_days", sa.Integer, server_default="0"),
        sa.Column("daily_revision_target_minutes", sa.Integer, server_default="30"),
        sa.Column("preferred_revision_time", sa.String(5), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Recitations ──────────────────────────────────────────────────
    op.create_table(
        "recitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surah_number", sa.Integer, nullable=False),
        sa.Column("ayah_start", sa.Integer, nullable=False),
        sa.Column("ayah_end", sa.Integer, nullable=False),
        sa.Column("recitation_type", sa.String(20), server_default="new_lesson"),
        sa.Column("audio_file_key", sa.String(500), nullable=False),
        sa.Column("audio_duration_seconds", sa.Float, nullable=True),
        sa.Column("audio_format", sa.String(10), server_default="webm"),
        sa.Column("audio_size_bytes", sa.Integer, nullable=True),
        sa.Column("status", sa.String(30), server_default="uploaded"),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("overall_accuracy_score", sa.Float, nullable=True),
        sa.Column("overall_tajweed_score", sa.Float, nullable=True),
        sa.Column("word_error_rate", sa.Float, nullable=True),
        sa.Column("total_words", sa.Integer, nullable=True),
        sa.Column("correct_words", sa.Integer, nullable=True),
        sa.Column("error_count", sa.Integer, nullable=True),
        sa.Column("teacher_reviewed", sa.Boolean, server_default="false"),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("teacher_override_score", sa.Float, nullable=True),
        sa.Column("teacher_notes", sa.Text, nullable=True),
        sa.Column("teacher_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("whisper_output", postgresql.JSONB, nullable=True),
        sa.Column("alignment_output", postgresql.JSONB, nullable=True),
        sa.Column("tajweed_output", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_recitations_student_id", "recitations", ["student_id"])
    op.create_index("ix_recitations_tenant_id", "recitations", ["tenant_id"])
    op.create_index("ix_recitations_status", "recitations", ["status"])

    # ── Ayah Scores ──────────────────────────────────────────────────
    op.create_table(
        "ayah_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recitation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recitations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surah_number", sa.Integer, nullable=False),
        sa.Column("ayah_number", sa.Integer, nullable=False),
        sa.Column("accuracy_score", sa.Float, server_default="0"),
        sa.Column("tajweed_score", sa.Float, server_default="0"),
        sa.Column("combined_score", sa.Float, server_default="0"),
        sa.Column("total_words", sa.Integer, server_default="0"),
        sa.Column("correct_words", sa.Integer, server_default="0"),
        sa.Column("missing_words", sa.Integer, server_default="0"),
        sa.Column("added_words", sa.Integer, server_default="0"),
        sa.Column("substituted_words", sa.Integer, server_default="0"),
        sa.Column("teacher_override_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ayah_scores_recitation_id", "ayah_scores", ["recitation_id"])

    # ── Word Analyses ────────────────────────────────────────────────
    op.create_table(
        "word_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recitation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recitations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surah_number", sa.Integer, nullable=False),
        sa.Column("ayah_number", sa.Integer, nullable=False),
        sa.Column("word_position", sa.Integer, nullable=False),
        sa.Column("reference_word", sa.String(200), nullable=False),
        sa.Column("recited_word", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_time", sa.Float, nullable=True),
        sa.Column("end_time", sa.Float, nullable=True),
        sa.Column("duration", sa.Float, nullable=True),
        sa.Column("expected_tajweed_rule", sa.String(50), nullable=True),
        sa.Column("tajweed_duration_expected", sa.Float, nullable=True),
        sa.Column("tajweed_duration_actual", sa.Float, nullable=True),
        sa.Column("tajweed_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_word_analyses_recitation_id", "word_analyses", ["recitation_id"])

    # ── Retention Records ────────────────────────────────────────────
    op.create_table(
        "retention_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surah_number", sa.Integer, nullable=False),
        sa.Column("ayah_number", sa.Integer, nullable=False),
        sa.Column("stability", sa.Float, server_default="1.0"),
        sa.Column("difficulty", sa.Float, server_default="0.3"),
        sa.Column("last_retention", sa.Float, server_default="1.0"),
        sa.Column("review_count", sa.Integer, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_score", sa.Float, server_default="0"),
        sa.Column("current_retention", sa.Float, server_default="1.0"),
        sa.Column("days_until_threshold", sa.Float, server_default="0"),
        sa.Column("consecutive_correct", sa.Integer, server_default="0"),
        sa.Column("mastery_level", sa.String(20), server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_retention_student_id", "retention_records", ["student_id"])
    op.create_index("ix_retention_next_review", "retention_records", ["next_review_at"])
    op.create_unique_constraint(
        "uq_retention_student_ayah",
        "retention_records",
        ["student_id", "surah_number", "ayah_number"],
    )

    # ── Revision Schedules ───────────────────────────────────────────
    op.create_table(
        "revision_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items", postgresql.JSONB, server_default="[]"),
        sa.Column("total_items", sa.Integer, server_default="0"),
        sa.Column("estimated_minutes", sa.Integer, server_default="0"),
        sa.Column("completed_items", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_schedules_student_date", "revision_schedules", ["student_id", "schedule_date"])

    # ── Audit Logs ───────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    # ── Row-Level Security Policies ──────────────────────────────────
    # Enable RLS on all tenant-scoped tables
    tenant_tables = [
        "users", "teacher_profiles", "student_profiles", "recitations",
        "ayah_scores", "word_analyses", "retention_records",
        "revision_schedules", "audit_logs",
    ]

    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING (tenant_id::text = current_setting('app.current_tenant', true))"
        )
        # Allow superuser to bypass RLS
        op.execute(
            f"CREATE POLICY {table}_superuser ON {table} "
            f"FOR ALL TO postgres USING (true)"
        )


def downgrade() -> None:
    tables = [
        "audit_logs", "revision_schedules", "retention_records",
        "word_analyses", "ayah_scores", "recitations",
        "student_profiles", "teacher_profiles", "users", "tenants",
    ]
    for table in tables:
        op.drop_table(table)
