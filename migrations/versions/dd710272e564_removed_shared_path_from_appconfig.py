"""Removed shared_path from AppConfig

Revision ID: dd710272e564
Revises: 417bd525279d
Create Date: 2024-09-03 16:13:29.716850

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd710272e564'
down_revision = '417bd525279d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.drop_column('shared_path')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shared_path', sa.VARCHAR(length=128), nullable=True))

    # ### end Alembic commands ###
