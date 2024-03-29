"""Added ip_address to AppConfig

Revision ID: 8c0ca16f4985
Revises: 3ca027642455
Create Date: 2024-02-23 09:47:08.164983

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c0ca16f4985'
down_revision = '3ca027642455'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ip_address', sa.String(length=12), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app_config', schema=None) as batch_op:
        batch_op.drop_column('ip_address')

    # ### end Alembic commands ###
