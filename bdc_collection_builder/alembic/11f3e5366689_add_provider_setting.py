"""add provider setting

Revision ID: 11f3e5366689
Revises: 64c2a4bb18e1
Create Date: 2022-09-29 10:40:41.552219

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '11f3e5366689'
down_revision = '64c2a4bb18e1'
branch_labels = ()
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('provider_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('driver_name', sa.String(length=64), nullable=True),
        sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['bdc.providers.id'], name=op.f('provider_settings_provider_id_providers_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('provider_settings_pkey')),
        schema='collection_builder'
    )
    op.create_index(op.f('idx_collection_builder_provider_settings_provider_id'), 'provider_settings', ['provider_id'], unique=False, schema='collection_builder')
    op.create_index(op.f('idx_collection_builder_provider_settings_provider_id_driver_name'), 'provider_settings', ['provider_id', 'driver_name'],
                    unique=True, schema='collection_builder')
    op.create_table('collections_providers_settings',
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.SmallInteger(), nullable=False),
        sa.Column('created', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['bdc.collections.id'], name=op.f('collections_providers_settings_collection_id_collections_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['collection_builder.provider_settings.id'], name=op.f('collections_providers_settings_provider_id_provider_settings_fkey'), onupdate='CASCADE', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('provider_id', 'collection_id', name=op.f('collections_providers_settings_pkey')),
        schema='collection_builder'
    )
    op.create_index(op.f('idx_collection_builder_collections_providers_settings_active'), 'collections_providers_settings', ['active'], unique=False, schema='collection_builder')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('idx_collection_builder_collections_providers_settings_active'), table_name='collections_providers_settings', schema='collection_builder')
    op.drop_table('collections_providers_settings', schema='collection_builder')
    op.drop_index(op.f('idx_collection_builder_provider_settings_provider_id_driver_name'),
                  table_name='provider_settings', schema='collection_builder')
    op.drop_index(op.f('idx_collection_builder_provider_settings_provider_id'), table_name='provider_settings', schema='collection_builder')
    op.drop_table('provider_settings', schema='collection_builder')
    # ### end Alembic commands ###
