"""removing party tax_id

Revision ID: 2e29ebe9a830
Revises: 2afccb4603ec
Create Date: 2023-01-30 13:26:33.708772

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2e29ebe9a830'
down_revision = '2afccb4603ec'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('parties', 'tax_id')
    op.drop_column('parties_version', 'tax_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('parties_version', sa.Column('tax_id', sa.VARCHAR(length=15), autoincrement=False, nullable=True))
    op.add_column('parties', sa.Column('tax_id', sa.VARCHAR(length=15), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
