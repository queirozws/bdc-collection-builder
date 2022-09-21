#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2022 INPE.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/gpl-3.0.html>.
#

"""activity_children.

Revision ID: 64c2a4bb18e1
Revises: 
Create Date: 2020-10-03 23:20:32.253182

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '64c2a4bb18e1'
down_revision = '06fab6583881'
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade alembic migration version."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('activity_src',
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('activity_src_id', sa.Integer(), nullable=False),
    sa.Column('created', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['collection_builder.activities.id'], name=op.f('activity_src_activity_id_activities_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['activity_src_id'], ['collection_builder.activities.id'], name=op.f('activity_src_activity_src_id_activities_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('activity_id', 'activity_src_id', name=op.f('activity_src_pkey')),
    schema='collection_builder'
    )
    op.create_unique_constraint(op.f('activities_collection_id_key'), 'activities',
                                ['collection_id', 'activity_type', 'sceneid'], schema='collection_builder')
    op.drop_constraint('activity_history_task_id_celery_taskmeta_fkey', 'activity_history', schema='collection_builder',
                       type_='foreignkey')
    op.create_foreign_key(op.f('activity_history_task_id_celery_taskmeta_fkey'), 'activity_history', 'celery_taskmeta',
                          ['task_id'], ['id'], source_schema='collection_builder', onupdate='CASCADE', referent_schema='collection_builder',
                          ondelete='CASCADE')
    op.drop_constraint('activity_history_activity_id_activities_fkey', 'activity_history', schema='collection_builder',
                       type_='foreignkey')
    op.create_foreign_key(op.f('activity_history_activity_id_activities_fkey'), 'activity_history', 'activities',
                          ['activity_id'], ['id'], source_schema='collection_builder', onupdate='CASCADE',
                          referent_schema='collection_builder',
                          ondelete='CASCADE')
    op.alter_column('activities', 'sceneid',
                    existing_type=sa.VARCHAR(length=200),
                    type_=sa.String(length=255),
                    existing_nullable=False,
                    schema='collection_builder')
    # ### end Alembic commands ###


def downgrade():
    """Downgrade alembic migration version."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('activities', 'sceneid',
                    existing_type=sa.String(length=255),
                    type_=sa.VARCHAR(length=200),
                    existing_nullable=False,
                    schema='collection_builder')
    op.drop_constraint(op.f('activity_history_activity_id_activities_fkey'), 'activity_history', schema='collection_builder', type_='foreignkey')
    op.create_foreign_key('activity_history_activity_id_activities_fkey', 'activity_history', 'activities', ['activity_id'], ['id'], source_schema='collection_builder', referent_schema='collection_builder')
    op.drop_constraint(op.f('activity_history_task_id_celery_taskmeta_fkey'), 'activity_history', schema='collection_builder', type_='foreignkey')
    op.create_foreign_key('activity_history_task_id_celery_taskmeta_fkey', 'activity_history', 'collection_builder.celery_taskmeta', ['task_id'], ['id'], source_schema='collection_builder', referent_schema='collection_builder')
    op.drop_constraint(op.f('activities_collection_id_key'), 'activities', schema='collection_builder', type_='unique')
    op.drop_table('activity_src', schema='collection_builder')
    # ### end Alembic commands ###
