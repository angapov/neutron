# Copyright (c) 2015 OpenStack Foundation.
#
# All Rights Reserved.
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

import sys

from oslo_config import cfg

from neutron.agent.common import config
from neutron.agent.l3 import config as l3_config
from neutron.agent.l3 import ha
from neutron.agent.linux import external_process
from neutron.agent.linux import interface
from neutron.agent.metadata import config as metadata_config
from neutron.common import config as common_config
from neutron.common import topics
from neutron.openstack.common import service
from neutron import service as neutron_service
        self.portforwardings = []
        # Process Portforwarding rules before generic SNAT rule
        if ex_gw_port:
            self.process_router_portforwardings(ri, ex_gw_port)


    def _update_portforwardings(self, ri, operation, portfwd):
        """Configure the router's port forwarding rules."""
        chain_in, chain_out = "PREROUTING", "snat"
        rule_in = ("-p %(protocol)s"
                   " -d %(outside_addr)s --dport %(outside_port)s"
                   " -j DNAT --to %(inside_addr)s:%(inside_port)s"
                   % portfwd)
        rule_out = ("-p %(protocol)s"
                    " -s %(inside_addr)s --sport %(inside_port)s"
                    " -j SNAT --to %(outside_addr)s:%(outside_port)s"
                    % portfwd)
        if operation == 'create':
            LOG.debug(_("Added portforwarding rule_in is '%s'"), rule_in)
            ri.iptables_manager.ipv4['nat'].add_rule(chain_in, rule_in,
                                                     tag='portforwarding')
            LOG.debug(_("Added portforwarding rule_out is '%s'"), rule_out)
            ri.iptables_manager.ipv4['nat'].add_rule(chain_out, rule_out,
                                                     top=True,
                                                     tag='portforwarding')
        elif operation == 'delete':
            LOG.debug(_("Removed portforwarding rule_in is '%s'"), rule_in)
            ri.iptables_manager.ipv4['nat'].remove_rule(chain_in, rule_in)
            LOG.debug(_("Removed portforwarding rule_out is '%s'"), rule_out)
            ri.iptables_manager.ipv4['nat'].remove_rule(chain_out, rule_out)
        else:
            raise Exception('should never be here')

    def process_router_portforwardings(self, ri, ex_gw_port):
        if 'portforwardings' not in ri.router:
            # note(jianingy): return when portforwarding extension
            #                 is not enabled
            return
        new_portfwds = ri.router['portforwardings']
        for new_portfwd in new_portfwds:
            new_portfwd['outside_addr'] = (
                ex_gw_port.get('fixed_ips')[0].get('ip_address'))
        old_portfwds = ri.portforwardings
        adds, removes = common_utils.diff_list_of_dict(old_portfwds,
                                                       new_portfwds)
        for portfwd in adds:
            self._update_portforwardings(ri, 'create', portfwd)
        for portfwd in removes:
            self._update_portforwardings(ri, 'delete', portfwd)
        ri.portforwardings = new_portfwds


def register_opts(conf):
    conf.register_opts(l3_config.OPTS)
    conf.register_opts(metadata_config.DRIVER_OPTS)
    conf.register_opts(metadata_config.SHARED_OPTS)
    conf.register_opts(ha.OPTS)
    config.register_interface_driver_opts_helper(conf)
    config.register_use_namespaces_opts_helper(conf)
    config.register_agent_state_opts_helper(conf)
    conf.register_opts(interface.OPTS)
    conf.register_opts(external_process.OPTS)


def main(manager='neutron.agent.l3.agent.L3NATAgentWithStateReport'):
    register_opts(cfg.CONF)
    common_config.init(sys.argv[1:])
    config.setup_logging()
    server = neutron_service.Service.create(
        binary='neutron-l3-agent',
        topic=topics.L3_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager=manager)
    service.launch(server).wait()
