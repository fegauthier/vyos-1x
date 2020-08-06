#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ipaddress
import netaddr
import netifaces
import os
import uuid

from sys import exit
from copy import deepcopy

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = r'/etc/miniupnpd/miniupnpd.conf'

default_config_data = {
    'secure_mode': False,
    'system_uptime': True,
    'notify_interval': 60,
    'clean_ruleset_interval': 600,
    'uuid': str(uuid.uuid4()),
    'outbound_interface': None,
    'listening_interfaces': [],
    'listening_interfaces_network': [],
}

def get_config():
    upnp = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'upnp']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    # Network interfaces to listen on
    if conf.exists(['outbound-interface']):
        upnp['outbound_interface'] = conf.return_value(['outbound-interface'])

    if conf.exists(['listen-on']):
        upnp['listening_interfaces'] = conf.return_values(['listen-on'])
        for listen_interface in upnp['listening_interfaces']:
            addresses = netifaces.ifaddresses(listen_interface)
            interfaceAddress = addresses[netifaces.AF_INET][0]
            cidr = netaddr.IPAddress(interfaceAddress['netmask']).netmask_bits()
            network = ipaddress.ip_interface(interfaceAddress['addr'] + '/' + str(cidr))
            upnp['listening_interfaces_network'].append(network)

    return upnp

def verify(upnp):
    if upnp is None:
        return None

    # at least one outbound-interface
    if upnp['outbound_interface'] is None:
        raise ConfigError('Must define the outbound-interface!')

    # check if the outbound-interface exist
    if upnp['outbound_interface'] not in netifaces.interfaces():
        raise ConfigError('Interface "{}" does not exist'.format(upnp['outbound-interface']))

    # at least one listen-on interface is needed
    if len(upnp['listening_interfaces']) < 1:
        raise ConfigError('Must define at least 1 listen-on interface!')

    # check is listen-on interfaces exists
    for interface in upnp['listening_interfaces']:
        if interface not in netifaces.interfaces():
            raise ConfigError('Interface "{}" does not exist'.format(interface))

    return None

def generate(upnp):
    # bail out early - looks like removal from running config
    if upnp is None:
        return None

    render(config_file, 'upnp/upnp.conf.tmpl', upnp)
    return None

def apply(upnp):
    if upnp is None:
         call('systemctl stop miniupnpd.service')
         if os.path.exists(config_file):
             os.unlink(config_file)
    else:
        call('systemctl restart miniupnpd.service')

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
