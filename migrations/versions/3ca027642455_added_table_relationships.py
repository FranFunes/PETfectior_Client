"""Added table relationships

Revision ID: 3ca027642455
Revises: ae821ec1d017
Create Date: 2023-08-17 10:20:54.809723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ca027642455'
down_revision = 'ae821ec1d017'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('instance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('PatientID', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('StudyInstanceUID', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('SeriesInstanceUID', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_instance_PatientID_patient'), 'patient', ['PatientID'], ['PatientID'])
        batch_op.create_foreign_key(batch_op.f('fk_instance_StudyInstanceUID_study'), 'study', ['StudyInstanceUID'], ['StudyInstanceUID'])
        batch_op.create_foreign_key(batch_op.f('fk_instance_SeriesInstanceUID_series'), 'series', ['SeriesInstanceUID'], ['SeriesInstanceUID'])

    with op.batch_alter_table('series', schema=None) as batch_op:
        batch_op.add_column(sa.Column('PatientID', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('StudyInstanceUID', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('originating_task', sa.String(length=18), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_series_originating_task_task'), 'task', ['originating_task'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_series_StudyInstanceUID_study'), 'study', ['StudyInstanceUID'], ['StudyInstanceUID'])
        batch_op.create_foreign_key(batch_op.f('fk_series_PatientID_patient'), 'patient', ['PatientID'], ['PatientID'])

    with op.batch_alter_table('study', schema=None) as batch_op:
        batch_op.add_column(sa.Column('PatientID', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_study_PatientID_patient'), 'patient', ['PatientID'], ['PatientID'])

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('series', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(length=96), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_task_series_series'), 'series', ['series'], ['SeriesInstanceUID'])
        batch_op.create_foreign_key(batch_op.f('fk_task_source_source'), 'source', ['source'], ['identifier'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_task_source_source'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_task_series_series'), type_='foreignkey')
        batch_op.drop_column('source')
        batch_op.drop_column('series')

    with op.batch_alter_table('study', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_study_PatientID_patient'), type_='foreignkey')
        batch_op.drop_column('PatientID')

    with op.batch_alter_table('series', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_series_PatientID_patient'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_series_StudyInstanceUID_study'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_series_originating_task_task'), type_='foreignkey')
        batch_op.drop_column('originating_task')
        batch_op.drop_column('StudyInstanceUID')
        batch_op.drop_column('PatientID')

    with op.batch_alter_table('instance', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_instance_SeriesInstanceUID_series'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_instance_StudyInstanceUID_study'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_instance_PatientID_patient'), type_='foreignkey')
        batch_op.drop_column('SeriesInstanceUID')
        batch_op.drop_column('StudyInstanceUID')
        batch_op.drop_column('PatientID')

    # ### end Alembic commands ###
