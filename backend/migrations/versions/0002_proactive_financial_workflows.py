"""Durable proactive workflows, financial insights and planning goals.

Revision ID: 0002_proactive
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_proactive"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "savings_goals",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("target_paise", sa.BigInteger(), nullable=False),
        sa.Column("saved_paise", sa.BigInteger(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_paise > 0 AND saved_paise >= 0 AND saved_paise <= target_paise",
            name="valid_goal_amounts",
        ),
        sa.CheckConstraint(
            "status IN ('active','paused','completed')", name="valid_goal_status"
        ),
    )
    op.create_index("ix_savings_goals_user_id", "savings_goals", ["user_id"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("trigger", sa.String(40), nullable=False),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("manual_retries", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(32), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "dedup_key", name="unique_agent_run_event"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="valid_agent_run_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 5 AND manual_retries BETWEEN 0 AND 3",
            name="bounded_agent_retries",
        ),
    )
    for column in ("user_id", "status", "available_at"):
        op.create_index(f"ix_agent_runs_{column}", "agent_runs", [column])
    op.create_table(
        "financial_insights",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "run_id", sa.String(32), sa.ForeignKey("agent_runs.id"), nullable=False
        ),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("message", sa.String(750), nullable=False),
        sa.Column("action_label", sa.String(60), nullable=False),
        sa.Column("action_path", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "kind", "key", name="unique_customer_insight"),
        sa.CheckConstraint(
            "status IN ('active','dismissed','resolved')", name="valid_insight_status"
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','critical')", name="valid_insight_severity"
        ),
    )
    op.create_index("ix_financial_insights_user_id", "financial_insights", ["user_id"])


def downgrade():
    op.drop_index("ix_financial_insights_user_id", table_name="financial_insights")
    op.drop_table("financial_insights")
    for column in ("available_at", "status", "user_id"):
        op.drop_index(f"ix_agent_runs_{column}", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_savings_goals_user_id", table_name="savings_goals")
    op.drop_table("savings_goals")
