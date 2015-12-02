# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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

# HTTP headers
HTTP_HEADER_CONTENT_TYPE = 'Content-Type'
HTTP_HEADER_CONTENT_LENGTH = 'Content-Length'
HTTP_HEADER_ALLOW = 'Allow'
HTTP_HEADER_ORIGIN = 'Origin'
HTTP_HEADER_ACCESS_CONTROL_ALLOW_METHODS = 'Access-Control-Allow-Methods'
HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS = 'Access-Control-Allow-Headers'
HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS = 'Access-Control-Request-Headers'

HTTP_HEADER_CONDITIONAL_IF_MATCH = 'If-Match'

# HTTP Content Types
HTTP_CONTENT_TYPE_JSON = 'application/json; charset=UTF-8'
