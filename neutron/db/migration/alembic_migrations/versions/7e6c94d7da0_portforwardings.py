# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""portforwardings

Revision ID: 7e6c94d7da0
Revises: ed93525fd003
Create Date: 2013-12-11 11:47:27.548651

"""

# revision identifiers, used by Alembic.
revision = '7e6c94d7da0'
down_revision = '20c469a5f920'
#down_revision = 'ed93525fd003'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    'neutron.plugins.ml2.plugin.Ml2Plugin'
]

from alembic import op
import sqlalchemy as sa

from neutron.db import migration


def upgrade(active_plugins=None, options=None):
#    if not migration.should_run(active_plugins, migration_for_plugins):
#        return

    op.create_table('portforwardingrules',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('router_id', sa.String(length=36),
                              nullable=True),
                    sa.Column('outside_port', sa.Integer(), nullable=True),
                    sa.Column('inside_addr', sa.String(length=15),
                              nullable=True),
                    sa.Column('inside_port', sa.Integer(), nullable=True),
                    sa.Column('protocol', sa.String(length=4),
                              nullable=True),
                    sa.ForeignKeyConstraint(['router_id'], ['routers.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('router_id', 'protocol',
                                        'outside_port',
                                        name='rule'),
                    )


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.drop_table('portforwardingrules')
