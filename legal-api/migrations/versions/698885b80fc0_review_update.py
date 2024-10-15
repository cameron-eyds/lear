"""review-update

Revision ID: 698885b80fc0
Revises: 83a110e10979
Create Date: 2024-10-10 15:17:32.903859

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '698885b80fc0'
down_revision = '83a110e10979'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reviews', sa.Column('contact_email', sa.String(length=150), nullable=True))
    op.drop_column('reviews', 'completing_party')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reviews', sa.Column('completing_party', sa.VARCHAR(length=150), nullable=True))
    op.drop_column('reviews', 'contact_email')
    # ### end Alembic commands ###
