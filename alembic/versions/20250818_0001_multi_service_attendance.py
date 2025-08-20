"""
multi-service attendance support

Revision ID: 20250818_0001
Revises: 
Create Date: 2025-08-18 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250818_0001'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create association table for many-to-many Attendance <-> Service
    op.create_table(
        'attendance_services',
        sa.Column('attendance_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendances.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
        sa.PrimaryKeyConstraint('attendance_id', 'service_id')
    )

    # Make attendances.service_id nullable (kept for compatibility)
    try:
        op.alter_column('attendances', 'service_id', existing_type=sa.Integer(), nullable=True)
    except Exception:
        # Some DBs may already have it nullable; ignore
        pass

    # Align default status to 'waiting'
    try:
        op.alter_column('attendances', 'status', server_default=sa.text("'waiting'"))
    except Exception:
        pass


def downgrade() -> None:
    # Revert default
    try:
        op.alter_column('attendances', 'status', server_default=None)
    except Exception:
        pass

    # Make column not null again (best effort)
    try:
        op.alter_column('attendances', 'service_id', existing_type=sa.Integer(), nullable=False)
    except Exception:
        pass

    op.drop_table('attendance_services')

