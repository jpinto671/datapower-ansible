#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018, [David Grau Merconchini <david@gallorojo.com.mx>]
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: idg_domain_chkpoint
short_description: Manages IBM DataPower Gateway(IDG) domains configuration checkpoints.
description:
  - Manages IBM DataPower Gateway(IDG) domains configuration checkpoints.
version_added: "2.7"
options:

notes:
  - This documentation was developed mostly from the content
    provided by IBM in its web administration interface.
  - For more information consult the official documentation.
    U(https://www.ibm.com/support/knowledgecenter/SS9H2Y_7.7.0/com.ibm.dp.doc/welcome.html)

author:
  - David Grau Merconchini (@dgraum)
'''

EXAMPLES = '''

'''

RETURN = '''

'''

import json
# import pdb

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native

# Common package of our implementation for IDG
try:
    from ansible.module_utils.appliance.ibm.idg_common import result, idg_endpoint_spec, IDG_Utils
    from ansible.module_utils.appliance.ibm.idg_rest_mgmt import IDG_API
    HAS_IDG_DEPS = True
except ImportError:
    HAS_IDG_DEPS = False

def main():

    # Arguments/parameters that a user can pass to the module
    module_args = dict(
        state = dict(type = 'str', choices = ['present', 'absent', 'restored'], default = 'present'), # Checkpoint state
        idg_connection = dict(type = 'dict', options = idg_endpoint_spec, required = True), # IDG connection
        domain = dict(type = 'str', required = True), # Domain
        name = dict(type = 'str', required = True) # Checkpoint
    )

    # AnsibleModule instantiation
    module = AnsibleModule(
        argument_spec = module_args,
        supports_check_mode = True
    )

    # Validates the dependence of the utility module
    if not HAS_IDG_DEPS:
        module.fail_json(msg="The IDG utils modules is required")

    # Parse arguments to dict
    idg_data_spec = IDG_Utils.parse_to_dict(module.params['idg_connection'], 'IDGConnection', IDG_Utils.ANSIBLE_VERSION)

    # Status & domain
    state = module.params['state']
    domain_name = module.params['domain']
    chkpoint_name = module.params['name']

    # Result
    result.update({"domain": domain_name}) # Add domain to result
    result['name'] = chkpoint_name

    # Init IDG API connect
    idg_mgmt = IDG_API(ansible_module = module,
                       idg_host = "https://{0}:{1}".format(idg_data_spec['server'], idg_data_spec['server_port']),
                       headers = IDG_Utils.BASIC_HEADERS,
                       http_agent = IDG_Utils.HTTP_AGENT_SPEC,
                       use_proxy = idg_data_spec['use_proxy'],
                       timeout = idg_data_spec['timeout'],
                       validate_certs = idg_data_spec['validate_certs'],
                       user = idg_data_spec['user'],
                       password = idg_data_spec['password'],
                       force_basic_auth = IDG_Utils.BASIC_AUTH_SPEC)

    # Variable to store the status of the action
    action_result = ''

    # Action messages:

    # Save checkpoint
    save_act_msg = { "SaveCheckpoint": {  "ChkName": chkpoint_name }}

    # Rollback checkpoint
    rollback_act_msg = { "RollbackCheckpoint": {  "ChkName": chkpoint_name }}

    # Remove checkpoint
    remove_act_msg = { "RemoveCheckpoint": {  "ChkName": chkpoint_name }}

    ###
    ### Here the action begins
    ###

    # List of configured domains
    chk_code, chk_msg, chk_data = idg_mgmt.api_call(uri = IDG_Utils.URI_DOMAIN_LIST, method = 'GET', data = None)

    if chk_code == 200 and chk_msg == 'OK': # If the answer is correct

        if isinstance(chk_data['domain'], dict): # if has only default domain
            configured_domains = [chk_data['domain']['name']]
        else:
            configured_domains = [d['name'] for d in chk_data['domain']]

        if domain_name in configured_domains: # Domain EXIST.

            # pdb.set_trace()
            if state == 'present':

                # If the user is working in only check mode we do not want to make any changes
                if module.check_mode:
                    result['msg'] = IDG_Utils.CHECK_MODE_MESSAGE
                    module.exit_json(**result)

                # pdb.set_trace()
                create_code, create_msg, create_data = idg_mgmt.api_call(uri = IDG_Utils.URI_ACTION.format(domain_name), method = 'POST',
                                                                         data = json.dumps(save_act_msg))

                if create_code == 202 and create_msg == 'Accepted':
                    # Asynchronous actions save accepted. Wait for complete
                    action_result = idg_mgmt.wait_for_action_end(uri = IDG_Utils.URI_ACTION.format(domain_name), href = create_data['_links']['location']['href'],
                                                                 state = state, domain = domain_name)

                    # Create checkpoint completed. Get result
                    dcr_code, dcr_msg, dcr_data = idg_mgmt.api_call(uri = create_data['_links']['location']['href'], method = 'GET',
                                                                    data = None)

                    if dcr_code == 200 and dcr_msg == 'OK':

                        if dcr_data['status'] == 'error':
                            # pdb.set_trace()
                            result['changed'] = False
                            if 'already exists' in str(dcr_data['error']):
                                result['msg'] = IDG_Utils.IMMUTABLE_MESSAGE
                            else:
                                result['msg'] = str(dcr_data['error'])
                                result['failed'] = True
                        else:
                            result['msg'] = dcr_data['status'].capitalize()
                            result['changed'] = True
                    else:
                        # Can't retrieve the create checkpoint result
                        module.fail_json(msg = to_native(idg_mgmt.ERROR_RETRIEVING_RESULT % (state, domain_name)))

                elif create_code == 200 and create_msg == 'OK':
                    # Successfully processed synchronized action
                    result['msg'] = idg_mgmt.status_text(create_data['SaveCheckpoint'])
                    result['changed'] = True

                else:
                    # Create checkpoint not accepted
                    module.fail_json(msg = to_native(idg_mgmt.ERROR_ACCEPTING_ACTION % (state, domain_name)))

            elif state == 'absent':

                # If the user is working in only check mode we do not want to make any changes
                if module.check_mode:
                    result['msg'] = IDG_Utils.CHECK_MODE_MESSAGE
                    module.exit_json(**result)

                # pdb.set_trace()
                rm_code, rm_msg, rm_data = idg_mgmt.api_call(uri = IDG_Utils.URI_ACTION.format(domain_name), method = 'POST',
                                                             data = json.dumps(remove_act_msg))

                if rm_code == 202 and rm_msg == 'Accepted':
                    # Asynchronous actions remove accepted. Wait for complete
                    action_result = idg_mgmt.wait_for_action_end(uri = IDG_Utils.URI_ACTION.format(domain_name), href = rm_data['_links']['location']['href'],
                                                                 state = state, domain = domain_name)

                    # Remove checkpoint completed. Get result
                    drm_code, drm_msg, drm_data = idg_mgmt.api_call(uri = rm_data['_links']['location']['href'], method = 'GET',
                                                                    data = None)

                    if drm_code == 200 and drm_msg == 'OK':

                        if drm_data['status'] == 'error':
                            # pdb.set_trace()
                            result['msg'] = str(drm_data['error'])
                            result['changed'] = False
                            result['failed'] = True
                        else:
                            result['msg'] = drm_data['status'].capitalize()
                            result['changed'] = True
                    else:
                        # Can't retrieve the create checkpoint result
                        module.fail_json(msg = to_native(idg_mgmt.ERROR_RETRIEVING_RESULT % (state, domain_name)))

                elif rm_code == 200 and rm_msg == 'OK':
                    # Successfully processed synchronized action
                    result['msg'] = idg_mgmt.status_text(rm_data['RemoveCheckpoint'])
                    result['changed'] = True

                elif rm_code == 400 and rm_msg == 'Bad Request':
                    # Wrong request, maybe there simply is no checkpoint
                    if 'Cannot find Configuration Checkpoint' in str(rm_data['error']):
                        result['msg'] = IDG_Utils.IMMUTABLE_MESSAGE
                    else:
                        result['msg'] = str(rm_data['error'])
                        result['failed'] = True

                else:
                    # Create checkpoint not accepted
                    module.fail_json(msg = to_native(idg_mgmt.ERROR_ACCEPTING_ACTION % (state, domain_name)))

            elif state == 'restored':

                # If the user is working in only check mode we do not want to make any changes
                if module.check_mode:
                    result['msg'] = IDG_Utils.CHECK_MODE_MESSAGE
                    module.exit_json(**result)

                # pdb.set_trace()
                bak_code, bak_msg, bak_data = idg_mgmt.api_call(uri = IDG_Utils.URI_ACTION.format(domain_name), method = 'POST',
                                                                data = json.dumps(rollback_act_msg))

                if bak_code == 202 and bak_msg == 'Accepted':
                    # Asynchronous actions remove accepted. Wait for complete
                    action_result = idg_mgmt.wait_for_action_end(uri = IDG_Utils.URI_ACTION.format(domain_name), href = bak_data['_links']['location']['href'],
                                                                 state = state, domain = domain_name)

                    # Remove checkpoint completed. Get result
                    dbak_code, dbak_msg, dbak_data = idg_mgmt.api_call(uri = bak_data['_links']['location']['href'], method = 'GET',
                                                                       data = None)

                    if dbak_code == 200 and dbak_msg == 'OK':

                        if dbak_data['status'] == 'error':
                            # pdb.set_trace()
                            result['msg'] = str(dbak_data['error'])
                            result['changed'] = False
                            result['failed'] = True
                        else:
                            result['msg'] = dbak_data['status'].capitalize()
                            result['changed'] = True
                    else:
                        # Can't retrieve the create checkpoint result
                        module.fail_json(msg = to_native(idg_mgmt.ERROR_RETRIEVING_RESULT % (state, domain_name)))

                elif bak_code == 200 and bak_msg == 'OK':
                    # Successfully processed synchronized action
                    result['msg'] = idg_mgmt.status_text(bak_data['RollbackCheckpoint'])
                    result['changed'] = True

                else:
                    # Create checkpoint not accepted
                    module.fail_json(msg = to_native(idg_mgmt.ERROR_ACCEPTING_ACTION % (state, domain_name)))

        else: # Domain NOT EXIST.
            # Can't work the configuration of non-existent domain
            module.fail_json(msg = idg_mgmt.ERROR_REACH_STATE + ' Domain not exist!' % (state, domain_name))

        # That's all folks!
        module.exit_json(**result)

    else: # The DP domains could not be extracted
        module.fail_json(msg = idg_mgmt.ERROR_GET_DOMAIN_LIST)

if __name__ == '__main__':
    main()