# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import audit

aufd = None

class RequiredParameter(Exception): pass

def audit_log_user_msg(op, cfgdata, user, hostname, addr, result):
    """
    Simple wrapper function for audit_log_user_message() from the
    audit library to insure a consistent audit event message.

    : param op: Text indicating the configuration operation that was
        performed.  Spaces are not allowed (replace with '-').
        No other special characters should be used.
    : param cfgdata: The configuration data that was changed or "None".
    : param user: The name of the user associated with the REST request.
    : param hostname: The hostname of local system, None if unknown.
    : param addr: The network address of the user, None if unknown.
    : param result: Result of the configuration operation.
        1 is "success", 0 is "failed"
    : return: -1 on failure, otherwise the event number.
    """
    global aufd

    if (aufd == None):
        aufd = audit.audit_open()

    cfg = ""
    if (cfgdata != None):
        cfg = audit.audit_encode_nv_string("data", str(cfgdata), 0)
        if (cfg == None):
            cfg = "out-of-memory!"

    if (op == None):
        raise RequiredParameter("Missing operation text!")

    if (user == None):
        raise RequiredParameter("Missing user name!")

    msg = str("op=RESTD:%s %s  user=%s" % (op, cfg, user))
    res = audit.audit_log_user_message(aufd, audit.AUDIT_USYS_CONFIG,
                                       msg, hostname, addr, None, result)
    return res
