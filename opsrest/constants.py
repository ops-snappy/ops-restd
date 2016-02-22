# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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

from ovs.db.idl import Transaction

# Ovsdb connection states and defaults
OVSDB_STATUS_DISCONNECTED = 1
OVSDB_STATUS_CONNECTED = 2
OVSDB_DEFAULT_CONNECTION_TIMEOUT = 1.0

# All IDL Transaction states
UNCOMMITTED = Transaction.UNCOMMITTED
UNCHANGED = Transaction.UNCHANGED
INCOMPLETE = Transaction.INCOMPLETE
ABORTED = Transaction.ABORTED
SUCCESS = Transaction.SUCCESS
TRY_AGAIN = Transaction.TRY_AGAIN
NOT_LOCKED = Transaction.NOT_LOCKED
ERROR = Transaction.ERROR

# REST URIs
REST_VERSION_PATH = '/rest/v1/'
REST_LOGIN_PATH = '/login'
REST_QUERY_PARAM_SELECTOR = 'selector'

REST_QUERY_PARAM_SORTING = 'sort'
REST_QUERY_PARAM_OFFSET = 'offset'
REST_QUERY_PARAM_LIMIT = 'limit'
REST_QUERY_PARAM_DEPTH = "depth"

# Ovsdb schema constants
OVSDB_SCHEMA_SYSTEM_TABLE = 'System'
OVSDB_SCHEMA_SYSTEM_URI = 'system'
OVSDB_SCHEMA_CONFIG = 'configuration'
OVSDB_SCHEMA_STATS = 'statistics'
OVSDB_SCHEMA_STATUS = 'status'
OVSDB_SCHEMA_CHILD = 'child'
OVSDB_SCHEMA_REFERENCE = 'reference'
OVSDB_SCHEMA_TOP_LEVEL = 'toplevel'
OVSDB_SCHEMA_PARENT = 'parent'
OVSDB_SCHEMA_BACK_REFERENCE = 'back'
OVSDB_BASE_URI = REST_VERSION_PATH + OVSDB_SCHEMA_SYSTEM_URI + '/'
OVSDB_SCHEMA_REFERENCED_BY = 'referenced_by'
# schema common columns which do not require keys to be validated
OVSDB_COMMON_COLUMNS = ['other_config', 'external_ids']

# HTTP headers
HTTP_HEADER_CONTENT_TYPE = 'Content-Type'
HTTP_HEADER_CONTENT_LENGTH = 'Content-Length'
HTTP_HEADER_ALLOW = 'Allow'
HTTP_HEADER_ORIGIN = 'Origin'
HTTP_HEADER_ACCESS_CONTROL_ALLOW_METHODS = 'Access-Control-Allow-Methods'
HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS = 'Access-Control-Request-Headers'

HTTP_HEADER_CONDITIONAL_IF_MATCH = 'If-Match'
HTTP_HEADER_ETAG = 'Etag'

# HTTP Content Types
HTTP_CONTENT_TYPE_JSON = 'application/json; charset=UTF-8'

# User Management
DEFAULT_USER_GRP = "ops_netop"
USERNAME_KEY = 'username'
OLD_PASSWORD_KEY = 'password'
NEW_PASSWORD_KEY = 'new_password'
USER_ROLE_KEY = "role"
USER_PERMISSIONS_KEY = "permissions"

# HTTP Request Types
REQUEST_TYPE_CREATE = 'POST'
REQUEST_TYPE_READ = 'GET'
REQUEST_TYPE_UPDATE = 'PUT'
REQUEST_TYPE_DELETE = 'DELETE'
REQUEST_TYPE_OPTIONS = 'OPTIONS'
REQUEST_TYPE_PATCH = 'PATCH'

# Audit Log for Configuration changes only
AUDIT_LOG_ACCEPTED_REQUESTS = {REQUEST_TYPE_CREATE, REQUEST_TYPE_UPDATE,
                               REQUEST_TYPE_DELETE, REQUEST_TYPE_PATCH}

OPSPLUGIN_DIR = '/usr/share/opsplugins'

# PATCH operation's keys according to RFC 6902
PATCH_KEY_OP = 'op'
PATCH_KEY_PATH = 'path'
PATCH_KEY_VALUE = 'value'
PATCH_KEY_FROM = 'from'

# PATCH operations according to RFC 6902
PATCH_OP_TEST = 'test'
PATCH_OP_REMOVE = 'remove'
PATCH_OP_ADD = 'add'
PATCH_OP_REPLACE = 'replace'
PATCH_OP_MOVE = 'move'
PATCH_OP_COPY = 'copy'
