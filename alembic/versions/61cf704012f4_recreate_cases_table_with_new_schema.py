"""recreate cases table with new schema

Revision ID: 61cf704012f4
Revises: c7116fc806a6
Create Date: 2025-12-28 13:14:40.798611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '61cf704012f4'
down_revision: Union[str, None] = 'c7116fc806a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old table and recreate with new schema
    op.drop_table('cases')
    op.create_table(
        'cases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ecli', sa.String(), nullable=False),
        sa.Column('link', sa.String(), nullable=True),
        sa.Column('creator', sa.String(), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('issued', sa.Date(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('procedure', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('inhoudsindicatie', sa.Text(), nullable=True),
        sa.Column('uitspraak', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ecli'),
    )
    op.create_index('ix_cases_ecli', 'cases', ['ecli'], unique=False)
    op.create_index('ix_cases_date', 'cases', ['date'], unique=False)
    op.create_index('ix_cases_creator', 'cases', ['creator'], unique=False)


def downgrade() -> None:
    # Recreate old table structure
    op.drop_table('cases')
    op.create_table(
        'cases',
        sa.Column('ecli', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('ecli'),
    )
