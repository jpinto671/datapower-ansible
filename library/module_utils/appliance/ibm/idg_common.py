# -*- coding: utf-8 -*-
#
# Copyright (c) 2017 Tecnologías Gallo Rojo.
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.urls import url_argument_spec

import json
# import pdb

# Seed the result
result = dict(
    changed=False,
    name='default',
    msg='the best is coming'
)

# Socket information
idg_endpoint_spec = url_argument_spec()
idg_endpoint_spec.update(
    timeout=dict(type='int', default=10),  # The socket level timeout in seconds
    server=dict(type='str', required=True),  # Remote IDG will be used.
    server_port=dict(type='int', default=5554),  # Remote IDG port be used.
    url_username=dict(required=False, aliases=['user']),
    url_password=dict(required=False, aliases=['password'], no_log=True),
)


class IDG_Utils(object):
    """ Class class with very useful things """

    #############################
    # Constants
    #############################

    IMMUTABLE_MESSAGE = 'The current state is consistent with the desired configuration'
    CHECK_MODE_MESSAGE = 'Change was only simulated, due to enabling verification mode'
    UNCONTROLLED_EXCEPTION = 'Unknown exception'

    # Connection agreements
    BASIC_HEADERS = {"Content-Type": "application/json"}
    ANSIBLE_VERSION = '2.7'
    BASIC_AUTH_SPEC = True
    HTTP_AGENT_SPEC = None

    @staticmethod
    def implement_check_mode(module, result):
        if module.check_mode:
            result['msg'] = IDG_Utils.CHECK_MODE_MESSAGE
            module.exit_json(**result)

    @staticmethod
    def parse_to_dict(module, data, desc, ver):
        # Interpret data as a dictionary
        if isinstance(data, dict):
            return data
        elif data:
            # data is NOT empty
            try:
                # Show warning
                module.deprecate('Supplying `{0}` as a string is deprecated. Please use dict/hash format.'.format(desc), version=ver)
                # Parse key:value,key:value,... string
                return dict(item.split(':', 1) for item in data.split(','))
            except Exception:
                # Can't parse
                module.fail_json(msg='The string representation for the `{0}` requires a key:value,key:value,... syntax to be properly parsed.'.format(desc))
        else:
            # data is empty
            return None

    @staticmethod
    def on_off(arg):
        # Translate boolean to: on, off
        return "on" if arg else "off"
