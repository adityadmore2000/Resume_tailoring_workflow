from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_resumes_add_slug"
down_revision = "0001_resume_tree_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("slug", sa.String(length=128), nullable=False, server_default=""))
    op.create_index("ux_resumes_slug", "resumes", ["slug"], unique=True)
    op.execute("UPDATE resumes SET slug = id::text WHERE slug = ''")
    op.alter_column("resumes", "slug", server_default=None)


def downgrade() -> None:
    op.drop_index("ux_resumes_slug", table_name="resumes")
    op.drop_column("resumes", "slug")

