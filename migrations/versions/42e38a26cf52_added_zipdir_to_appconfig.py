"""Added zipDir to AppConfig

Revision ID: 42e38a26cf52
Revises: 390806ceaf3b
Create Date: 2023-08-11 17:08:18.438922

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42e38a26cf52'
down_revision = '390806ceaf3b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('packed_path', sa.String(length=128), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.drop_column('packed_path')

    # ### end Alembic commands ###