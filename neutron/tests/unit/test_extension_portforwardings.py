# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 UnitedStack, Inc.
# All rights reserved.
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
# @author: Jianing Yang, UnitedStack, Inc
import copy
from oslo.config import cfg
from webob import exc

from neutron.common.test_lib import test_config
from neutron.db import portforwardings_db
from neutron.extensions import l3
from neutron.extensions import portforwardings
from neutron.openstack.common import log as logging
from neutron.openstack.common.notifier import api as notifier_api
from neutron.openstack.common.notifier import test_notifier
from neutron.openstack.common import uuidutils
from neutron.tests.unit import test_api_v2
from neutron.tests.unit import test_l3_plugin as test_l3


LOG = logging.getLogger(__name__)

_uuid = uuidutils.generate_uuid
_get_path = test_api_v2._get_path


class PortForwardingsTestExtensionManager(object):

    def get_resources(self):
        l3.RESOURCE_ATTRIBUTE_MAP['routers'].update(
            portforwardings.EXTENDED_ATTRIBUTES_2_0['routers'])
        return l3.L3.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class TestPortForwardingsIntPlugin(
        test_l3.TestL3NatIntPlugin,
        portforwardings_db.PortForwardingDbMixin):
    supported_extension_aliases = ["external-net", "router", "portforwarding"]


class TestPortForwardingsL3NatServicePlugin(
        test_l3.TestL3NatServicePlugin,
        portforwardings_db.PortForwardingDbMixin):
    supported_extension_aliases = ["router", "portforwarding"]


class PortForwardingsDBTestCaseBase(object):
    forwardings = [{'outside_port': 2222,
                    'inside_addr': '10.0.0.3',
                    'inside_port': 22,
                    'protocol': 'tcp'
                    },
                   {'outside_port': 2121,
                    'inside_addr': '10.0.0.3',
                    'inside_port': 21,
                    'protocol': 'tcp'}]

    def _pfwd_update_prepare(self, router_id, subnet_id,
                             port_id, pfwds, skip_add=False):
        if not skip_add:
            self._router_interface_action('add', router_id, subnet_id, port_id)
        self._update('routers', router_id,
                     {'router': {'portforwardings': pfwds}})
        return self._show('routers', router_id)

    def _pfwd_update_cleanup(self, port_id, subnet_id, router_id, pfwds):
        self._update('routers', router_id,
                     {'router': {'portforwardings': pfwds}})
        self._router_interface_action('remove', router_id, subnet_id, port_id)

    def test_pfwd_update_with_one_rule(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    body = self._pfwd_update_prepare(r['router']['id'],
                                                     None, p['port']['id'],
                                                     self.forwardings[0:1])
                    self.assertEqual(body['router']['portforwardings'],
                                     self.forwardings[0:1])
                    self._pfwd_update_cleanup(p['port']['id'],
                                              None, r['router']['id'], [])

    def test_pfwd_update_with_multiple_rules(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    body = self._pfwd_update_prepare(r['router']['id'],
                                                     None, p['port']['id'],
                                                     self.forwardings)
                    self.assertEqual(sorted(body['router']['portforwardings']),
                                     sorted(self.forwardings))
                    self._pfwd_update_cleanup(p['port']['id'],
                                              None, r['router']['id'], [])

    def test_pfwd_update_with_duplicate_rules(self):
        duplicated = [self.forwardings[0], self.forwardings[0]]
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings': duplicated}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_update_with_duplicate_outside_port(self):
        duplicated = copy.deepcopy(self.forwardings)
        duplicated[1]['outside_port'] = duplicated[0]['outside_port']

        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings': duplicated}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_delete_rules(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._pfwd_update_prepare(r['router']['id'],
                                              None, p['port']['id'],
                                              self.forwardings)
                    body = self._update('routers', r['router']['id'],
                                        {'router': {'portforwardings':
                                                    self.forwardings[0:1]}})
                    self.assertEqual(body['router']['portforwardings'],
                                     self.forwardings[0:1])
                    self._pfwd_update_cleanup(p['port']['id'],
                                              None, r['router']['id'], [])

    def test_pfwd_update_with_nonexist_subnet(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

                    forwardings = [{'outside_port': 2222,
                                    'inside_addr': '10.1.0.3',
                                    'inside_port': 22,
                                    'protocol': 'tcp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_update_with_invalid_protocol(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

                    forwardings = [{'outside_port': 2222,
                                    'inside_addr': '10.0.0.3',
                                    'inside_port': 22,
                                    'protocol': 'ppp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_update_with_invalid_ip_address(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])
                    forwardings = [{'outside_port': 2222,
                                    'inside_addr': '710.0.0.3',
                                    'inside_port': 22,
                                    'protocol': 'tcp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_update_with_invalid_port_number(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._router_interface_action('add',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

                    forwardings = [{'outside_port': -1,
                                    'inside_addr': '10.0.0.3',
                                    'inside_port': 22,
                                    'protocol': 'tcp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    forwardings = [{'outside_port': 65536,
                                    'inside_addr': '10.0.0.3',
                                    'inside_port': 22,
                                    'protocol': 'tcp'
                                    }]

                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    forwardings = [{'outside_port': 2222,
                                    'inside_addr': '10.0.0.3',
                                    'inside_port': -1,
                                    'protocol': 'tcp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    forwardings = [{'outside_port': 2222,
                                    'inside_addr': '10.0.0.3',
                                    'inside_port': 65536,
                                    'protocol': 'tcp'
                                    }]
                    self._update('routers', r['router']['id'],
                                 {'router': {'portforwardings':
                                             forwardings}},
                                 expected_code=exc.HTTPBadRequest.code)

                    # clean-up
                    self._router_interface_action('remove',
                                                  r['router']['id'],
                                                  None,
                                                  p['port']['id'])

    def test_pfwd_clear_rule_with_None(self):
        with self.router() as r:
            with self.subnet(cidr='10.0.0.0/24') as s:
                with self.port(subnet=s, no_delete=True) as p:
                    self._pfwd_update_prepare(r['router']['id'],
                                              None, p['port']['id'],
                                              self.forwardings)
                    body = self._update('routers', r['router']['id'],
                                        {'router': {'portforwardings': None}})
                    self.assertEqual(body['router']['portforwardings'], [])
                    self._pfwd_update_cleanup(p['port']['id'],
                                              None, r['router']['id'], [])


class PortForwardingsDBIntTestCase(test_l3.L3NatDBIntTestCase,
                                   PortForwardingsDBTestCaseBase):

    def setUp(self, plugin=None):
        if not plugin:
            plugin = ('neutron.tests.unit.test_extension_portforwardings.'
                      'TestPortForwardingsIntPlugin')
        test_config['plugin_name_v2'] = plugin
        # for these tests we need to enable overlapping ips
        cfg.CONF.set_default('allow_overlapping_ips', True)
        cfg.CONF.set_default('max_routes', 3)
        ext_mgr = PortForwardingsTestExtensionManager()
        test_config['extension_manager'] = ext_mgr
        # L3NatDBIntTestCase will overwrite plugin_name_v2,
        # so we don't need to setUp on the class here
        super(test_l3.L3BaseForIntTests, self).setUp()

        # Set to None to reload the drivers
        notifier_api._drivers = None
        cfg.CONF.set_override("notification_driver", [test_notifier.__name__])


class PortForwardingsDBIntTestCaseXML(PortForwardingsDBIntTestCase):
    fmt = 'xml'


class PortForwardingsDBSepTestCase(test_l3.L3NatDBSepTestCase,
                                   PortForwardingsDBTestCaseBase):
    def setUp(self):
        # the plugin without L3 support
        test_config['plugin_name_v2'] = (
            'neutron.tests.unit.test_l3_plugin.TestNoL3NatPlugin')
        # the L3 service plugin
        l3_plugin = ('neutron.tests.unit.test_extension_portforwardings.'
                     'TestPortForwardingsL3NatServicePlugin')
        service_plugins = {'l3_plugin_name': l3_plugin}

        # for these tests we need to enable overlapping ips
        cfg.CONF.set_default('allow_overlapping_ips', True)
        cfg.CONF.set_default('max_routes', 3)
        ext_mgr = PortForwardingsTestExtensionManager()
        test_config['extension_manager'] = ext_mgr
        # L3NatDBSepTestCase will overwrite plugin_name_v2,
        # so we don't need to setUp on the class here
        super(test_l3.L3BaseForSepTests, self).setUp(
            service_plugins=service_plugins)

        # Set to None to reload the drivers
        notifier_api._drivers = None
        cfg.CONF.set_override("notification_driver", [test_notifier.__name__])


class PortForwardingsDBSepTestCaseXML(PortForwardingsDBSepTestCase):
    fmt = 'xml'
