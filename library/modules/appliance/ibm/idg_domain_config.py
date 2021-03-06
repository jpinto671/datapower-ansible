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
module: idg_domain_config
short_description: Manages IBM DataPower Gateway(IDG) domains configurations actions.
description:
  - Manages IBM DataPower Gateway(IDG) domains configurations actions.
version_added: "2.7"
options:
  name:
    description:
      - Domain identifier.
    required: True

  state:
    description:
      - Specifies the current state of the domain.
        C(reseted) will delete all configured services within the domain.
        C(exported), C(imported), C(saved) domain settings
      - Be particularly careful about changing the status C(reseted).
        These will deletes all configuration data in the domain.
    default: saved
    required: True
    choices:
      - reseted
      - imported
      - exported
      - saved

  user_summary:
    description:
      - A descriptive summary for the export.

  all_files:
    description:
      - Include all files in the local directory for the domain?
      - Only be taken into account during the export
    default: False
    type: bool

  persisted:
    description:
      - Export from persisted or running configuration?
      - Only be taken into account during the export
    default: False
    type: bool

  internal_files:
    description:
      - Export internal configuration files?
      - Only be taken into account during the export
    default: True
    type: bool

  input_file:
    description:
      - The base64-encoded BLOB to import
      - Only be taken into account during the import

  overwrite_files:
    description:
      - Overwrite local files
      - Only be taken into account during the import
    default: False
    type: bool

  overwrite_objects:
    description:
      - Overwrite objects that exist
      - Only be taken into account during the import
    default: False
    type: bool

  dry_run:
    description:
      - Import package (on) or validate the import operation without importing (off).
      - Only be taken into account during the import
    default: False
    type: bool

  rewrite_local_ip:
    description:
      - The local address bindings of services in the import package are rewritten on import to their equivalent interfaces
      - Only be taken into account during the import
    default: False
    type: bool

# extends_documentation_fragment: idg

author:
  - David Grau Merconchini (@dgraum)
'''

EXAMPLES = '''
- name: Test DataPower domain configuration module
  connection: local
  hosts: localhost
  vars:
    source_domain: test1
    target_domain: test2
    remote_idg:
        server: idghosts
        server_port: 5554
        user: admin
        password: admin
        validate_certs: false
        timeout: 15

  tasks:

    - name: Export domain
      idg_domain_config:
        name: "{{ source_domain }}"
        idg_connection: "{{ remote_idg }}"
        state: exported
        all_files: True
        user_summary: Midnight backup
      register: export_out

    - name: Import domain
      idg_domain_config:
        name: "{{ target_domain }}"
        idg_connection: "{{ remote_idg }}"
        state: imported
        overwrite_files: True
        overwrite_objects: True
        input_file: "{{ export_out['file'] }}"

    - name: Save domain
      idg_domain_config:
        name: "{{ target_domain }}"
        idg_connection: "{{ remote_idg }}"
        state: saved
      register: save_out
'''

RETURN = '''
name:
  description:
    - The name of the domain that is being worked on.
  returned: changed and success
  type: string
  sample:
    - core-security-wrap
    - DevWSOrchestration
msg:
  description:
    - Message returned by the device API.
  returned: always
  type: string
  sample:
    - Configuration was created.
    - Unknown error for (https://idg-host1:5554/mgmt/domains/config/). <open_url error timed out>
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
        state=dict(type='str', choices=['exported', 'imported', 'reseted', 'saved'], default='saved'),  # Domain's operational state
        idg_connection=dict(type='dict', options=idg_endpoint_spec, required=True),  # IDG connection
        name=dict(type='str', required=True),  # Domain to work
        # for Export
        user_summary=dict(type='str'),  # Backup comment
        all_files=dict(type='bool', default=False),  # Include all files in the local: directory for the domain
        persisted=dict(type='bool', default=False),  # Export from persisted or running configuration
        internal_files=dict(type='bool', default=True),  # Export internal configuration file
        # for Import
        input_file=dict(type='str', required=False, no_log=True),  # The base64-encoded BLOB to import
        overwrite_files=dict(type='bool', default=False),  # Overwrite files that exist
        overwrite_objects=dict(type='bool', default=False),  # Overwrite objects that exist
        dry_run=dict(type='bool', default=False),  # Import package (on) or validate the import operation without importing (off).
        rewrite_local_ip=dict(type='bool', default=False)  # The local address binding to their equivalent interfaces in appliance
        # TODO !!!
        # DeploymentPolicy
    )

    # AnsibleModule instantiation
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        # Interaction between parameters
        required_if=[['state', 'imported', ['input_file']]]
    )

    # Validates the dependence of the utility module
    if not HAS_IDG_DEPS:
        module.fail_json(msg="The IDG utils module is required")

    try:

        # Parse arguments to dict
        idg_data_spec = IDG_Utils.parse_to_dict(module, module.params['idg_connection'], 'IDGConnection', IDG_Utils.ANSIBLE_VERSION)

        # Status & domain
        state = module.params['state']
        domain_name = module.params['name']

        # Result
        result['name'] = domain_name

        # Init IDG API connect
        idg_mgmt = IDG_API(ansible_module=module,
                           idg_host="https://{0}:{1}".format(idg_data_spec['server'], idg_data_spec['server_port']),
                           headers=IDG_Utils.BASIC_HEADERS,
                           http_agent=IDG_Utils.HTTP_AGENT_SPEC,
                           use_proxy=idg_data_spec['use_proxy'],
                           timeout=idg_data_spec['timeout'],
                           validate_certs=idg_data_spec['validate_certs'],
                           user=idg_data_spec['user'],
                           password=idg_data_spec['password'],
                           force_basic_auth=IDG_Utils.BASIC_AUTH_SPEC)

        # Variable to store the status of the action
        action_result = ''

        # Configuration template for the domain
        export_action_msg = {"Export": {
            "Format": "ZIP",
            "UserComment": module.params['user_summary'],
            "AllFiles": IDG_Utils.on_off(module.params['all_files']),
            "Persisted": IDG_Utils.on_off(module.params['persisted']),
            "IncludeInternalFiles": IDG_Utils.on_off(module.params['internal_files'])
            # TODO
            # "DeploymentPolicy":""
        }}

        import_action_msg = {"Import": {
            "Format": "ZIP",
            "InputFile": module.params['input_file'],
            "OverwriteFiles": IDG_Utils.on_off(module.params['overwrite_files']),
            "OverwriteObjects": IDG_Utils.on_off(module.params['overwrite_objects']),
            "DryRun": IDG_Utils.on_off(module.params['dry_run']),
            "RewriteLocalIP": IDG_Utils.on_off(module.params['rewrite_local_ip'])
            # TODO
            # "DeploymentPolicy": "name",
            # "DeploymentPolicyParams": "name",
        }}

        # Action messages
        # Reset
        reset_act_msg = {"ResetThisDomain": {}}

        # Save
        save_act_msg = {"SaveConfig": {}}

        #
        # Here the action begins
        #

        # List of configured domains
        chk_code, chk_msg, chk_data = idg_mgmt.api_call(IDG_API.URI_DOMAIN_LIST, method='GET')

        if chk_code == 200 and chk_msg == 'OK':  # If the answer is correct

            if isinstance(chk_data['domain'], dict):  # if has only default domain
                configured_domains = [chk_data['domain']['name']]
            else:
                configured_domains = [d['name'] for d in chk_data['domain']]

            if domain_name in configured_domains:  # Domain EXIST.

                # pdb.set_trace()
                if state == 'exported':

                    # If the user is working in only check mode we do not want to make any changes
                    IDG_Utils.implement_check_mode(module, result)

                    # export and finish
                    # pdb.set_trace()
                    exp_code, exp_msg, exp_data = idg_mgmt.api_call(IDG_API.URI_ACTION.format(domain_name), method='POST',
                                                                    data=json.dumps(export_action_msg))

                    if exp_code == 202 and exp_msg == 'Accepted':
                        # Asynchronous actions export accepted. Wait for complete
                        action_result = idg_mgmt.wait_for_action_end(IDG_API.URI_ACTION.format(domain_name), href=exp_data['_links']['location']['href'],
                                                                     state=state)

                        # Export completed. Get result
                        doex_code, doex_msg, doex_data = idg_mgmt.api_call(exp_data['_links']['location']['href'], method='GET')

                        if doex_code == 200 and doex_msg == 'OK':
                            # Export ok
                            result['file'] = doex_data['result']['file']
                            result['msg'] = action_result
                            result['changed'] = True
                        else:
                            # Can't retrieve the export
                            module.fail_json(msg=to_native(IDG_API.ERROR_RETRIEVING_RESULT.format(state, domain_name)))

                    elif exp_code == 200 and exp_msg == 'OK':
                        # Successfully processed synchronized action
                        result['msg'] = idg_mgmt.status_text(exp_data['Export'])
                        result['changed'] = True

                    else:
                        # Export not accepted
                        module.fail_json(msg=to_native(IDG_API.ERROR_ACCEPTING_ACTION.format(state, domain_name)))

                elif state == 'reseted':

                    # If the user is working in only check mode we do not want to make any changes
                    IDG_Utils.implement_check_mode(module, result)

                    # Reseted domain
                    reset_code, reset_msg, reset_data = idg_mgmt.api_call(IDG_API.URI_ACTION.format(domain_name), method='POST',
                                                                          data=json.dumps(reset_act_msg))

                    # pdb.set_trace()
                    if reset_code == 202 and reset_msg == 'Accepted':
                        # Asynchronous actions reset accepted. Wait for complete
                        action_result = idg_mgmt.wait_for_action_end(IDG_API.URI_ACTION.format(domain_name), href=reset_data['_links']['location']['href'],
                                                                     state=state)

                        # Reseted completed
                        dore_code, dore_msg, dore_data = idg_mgmt.api_call(reset_data['_links']['location']['href'], method='GET')

                        if dore_code == 200 and dore_msg == 'OK':
                            # Reseted successfully
                            result['msg'] = dore_data['status'].capitalize()
                            result['changed'] = True
                        else:
                            # Can't retrieve the reset result
                            module.fail_json(msg=to_native(IDG_API.ERROR_RETRIEVING_RESULT.format(state, domain_name)))

                    elif reset_code == 200 and reset_msg == 'OK':
                        # Successfully processed synchronized action
                        result['msg'] = idg_mgmt.status_text(reset_data['ResetThisDomain'])
                        result['changed'] = True

                    else:
                        # Reseted not accepted
                        module.fail_json(msg=to_native(IDG_API.ERROR_ACCEPTING_ACTION.format(state, domain_name)))

                elif state == 'saved':

                    qds_code, qds_msg, qds_data = idg_mgmt.api_call(IDG_API.URI_DOMAIN_STATUS, method='GET')

                    # pdb.set_trace()
                    if qds_code == 200 and qds_msg == 'OK':

                        if isinstance(qds_data['DomainStatus'], dict):
                            domain_save_needed = qds_data['DomainStatus']['SaveNeeded']
                        else:
                            domain_save_needed = [d['SaveNeeded'] for d in qds_data['DomainStatus'] if d['Domain'] == domain_name][0]

                        # Saved domain
                        if domain_save_needed != 'off':

                            # If the user is working in only check mode we do not want to make any changes
                            IDG_Utils.implement_check_mode(module, result)

                            save_code, save_msg, save_data = idg_mgmt.api_call(IDG_API.URI_ACTION.format(domain_name), method='POST',
                                                                               data=json.dumps(save_act_msg))

                            # pdb.set_trace()
                            if save_code == 202 and save_msg == 'Accepted':
                                # Asynchronous actions save accepted. Wait for complete
                                action_result = idg_mgmt.wait_for_action_end(IDG_API.URI_ACTION.format(domain_name),
                                                                             href=save_data['_links']['location']['href'], state=state)

                                # Save ready
                                dosv_code, dosv_msg, dosv_data = idg_mgmt.api_call(save_data['_links']['location']['href'], method='GET')

                                if dosv_code == 200 and dosv_msg == 'OK':
                                    # Save completed
                                    result['msg'] = action_result
                                    result['changed'] = True
                                else:
                                    # Can't retrieve the save result
                                    module.fail_json(msg=to_native(IDG_API.ERROR_RETRIEVING_RESULT.format(state, domain_name)))

                            elif save_code == 200 and save_msg == 'OK':
                                # Successfully processed synchronized action save
                                result['msg'] = idg_mgmt.status_text(save_data['SaveConfig'])
                                result['changed'] = True
                            else:
                                # Can't saved
                                module.fail_json(msg=to_native(IDG_API.ERROR_RETRIEVING_RESULT.format(state, domain_name)))
                        else:
                            # Domain is save
                            result['msg'] = IDG_Utils.IMMUTABLE_MESSAGE

                elif state == 'imported':

                    # If the user is working in only check mode we do not want to make any changes
                    IDG_Utils.implement_check_mode(module, result)

                    # Import
                    # pdb.set_trace()
                    imp_code, imp_msg, imp_data = idg_mgmt.api_call(IDG_API.URI_ACTION.format(domain_name), method='POST',
                                                                    data=json.dumps(import_action_msg))

                    # pdb.set_trace()
                    if imp_code == 202 and imp_msg == 'Accepted':
                        # Asynchronous actions import accepted. Wait for complete
                        action_result = idg_mgmt.wait_for_action_end(IDG_API.URI_ACTION.format(domain_name), href=imp_data['_links']['location']['href'],
                                                                     state=state)

                        # Import ready
                        doim_code, doim_msg, doim_data = idg_mgmt.api_call(imp_data['_links']['location']['href'], method='GET')

                        if doim_code == 200 and doim_msg == 'OK':
                            # Export completed
                            if doim_data['result']['Import']['import-results']['detected-errors'] == 'true':
                                # pdb.set_trace()
                                result['msg'] = 'Error code:' + doim_data['result']['Import']['import-results']['detected-errors']['error']
                                result['changed'] = False
                                result['failed'] = True
                            else:
                                result['msg'] = doim_data['status'].capitalize()
                                result['changed'] = True
                        else:
                            # Can't retrieve the import result
                            module.fail_json(msg=to_native(IDG_API.ERROR_RETRIEVING_RESULT.format(state, domain_name)))

                    elif imp_code == 200 and imp_msg == 'OK':
                        # Successfully processed synchronized action
                        result['msg'] = idg_mgmt.status_text(imp_data['Import'])
                        result['changed'] = True

                    else:
                        # Imported not accepted
                        module.fail_json(msg=to_native(IDG_API.ERROR_ACCEPTING_ACTION.format(state, domain_name)))

            else:  # Domain NOT EXIST.
                # pdb.set_trace()
                # Opps can't work the configuration of non-existent domain
                module.fail_json(msg=(IDG_API.ERROR_REACH_STATE + ' Domain not exist!').format(state, domain_name))

        else:  # Can't read domain's lists
            module.fail_json(msg=IDG_API.ERROR_GET_DOMAIN_LIST)

    except Exception as e:
        # Uncontrolled exception
        module.fail_json(msg=(IDG_Utils.UNCONTROLLED_EXCEPTION + '. {0}').format(to_native(e)))
    else:
        # That's all folks!
        module.exit_json(**result)


if __name__ == '__main__':
    main()
