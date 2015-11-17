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

from opsrest.resource import Resource
from opsrest.utils import utils
from opsrest.constants import *
import ovs.ovsuuid

import types
import json
import urllib

from tornado.log import app_log


def split_path(path):
    path = path.split('/')
    path = [urllib.unquote(i) for i in path if i != '']
    return path


def parse_url_path(path, schema, idl, http_method='GET'):

    if not path.startswith(REST_VERSION_PATH):
        return None

    # remove version and split path
    path = path[len(REST_VERSION_PATH):]
    path = split_path(path)
    if not path:
        return None

    # we only serve URIs that begin with '/system'
    if path[0] != OVSDB_SCHEMA_SYSTEM_URI:
        return None

    resource = Resource(OVSDB_SCHEMA_SYSTEM_TABLE)

    if resource.table not in idl.tables:
        return None

    if idl.tables[resource.table].rows.keys():
        resource.row = idl.tables[resource.table].rows.keys()[0]
    else:
        return None

    path = path[1:]
    if not path:
        return resource

    try:
        parse(path, resource, schema, idl, http_method)
        return resource
    except Exception as e:
        app_log.debug(e)
        app_log.debug('resource not found')
        return None

    return None


def parse(path, resource, schema, idl, http_method):
    '''
        recursive routine that compares the URI path with the extended schema
        and builds resource/subresource relationship. If the relationship
        referenced by the URI doesn't match with the extended schema we
        return None
    '''
    if not path:
        return None

    ovs_tables = schema.ovs_tables
    table_names = ovs_tables.keys()

    _fail = False

    # check if path[0] is a CHILD of resource.table
    if path[0] in ovs_tables[resource.table].children:

        resource.relation = OVSDB_SCHEMA_CHILD
        resource.column = path[0]
        app_log.debug("%s is a forward child in %s" % (path[0],
                      resource.table))
        path[0] = ovs_tables[resource.table].references[path[0]].ref_table

    elif path[0] in schema.plural_name_map:

        path[0] = schema.plural_name_map[path[0]]

        # check if path[0] is a back referenced CHILD of resource.table
        if path[0] in ovs_tables[resource.table].children:
            resource.relation = OVSDB_SCHEMA_BACK_REFERENCE
            app_log.debug("%s is a backward child in %s"
                          % (path[0], resource.table))
        else:
            if resource.table == OVSDB_SCHEMA_SYSTEM_TABLE and \
                    ovs_tables[path[0]].parent is None:
                resource.relation = OVSDB_SCHEMA_TOP_LEVEL
                app_log.debug("%s is a top level table" % (path[0]))

    if resource.relation is None:
        app_log.debug('URI not allowed: relationship does not exist')
        raise Exception

    # create the next resource
    new_resource = Resource(path[0])
    resource.next = new_resource
    path = path[1:]

    # update path list
    app_log.debug("table: %s, row: %s, column: %s, relation: %s"
                  % (resource.table, str(resource.row),
                      str(resource.column), str(resource.relation)))

    # this should be the start of the index
    index_list = None
    if path:
        table_indices = schema.ovs_tables[new_resource.table].indexes

        # len(path) must at least be equal to len(table_indices)
        # to uniquely identify a resource
        if len(path) < len(table_indices):
            return None

        index_list = path[0:len(table_indices)]

    # verify back reference existence
    if resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        if http_method == 'POST' and index_list is None:
            return

        if not verify_back_reference(resource, new_resource, schema,
                                     idl, index_list):
            app_log.debug('URI not allowed: resource verification failed')
            raise Exception

    # return if we are done processing the URI
    if index_list is None:
        return

    # verify non-backreference resource existence
    row = verify_index(new_resource, resource, index_list, schema, idl)
    if row is None:
        raise Exception
    else:
        new_resource.row = row.uuid
        new_resource.index = index_list

    # we now have a complete new_resource
    # continue processing the path further
    path = path[len(index_list):]
    parse(path, new_resource, schema, idl, http_method)


def verify_back_reference(resource, new_resource, schema,
                          idl, index_list=None):
    '''
        Some resources have the same parent. BGP_Routers can share the same
        VRF and hence will have the same reference pointer under the 'vrf'
        column. If bgp_routers for a a particular VRF is desired, we search
        in the entire BGP_Router table to find those BGP Routers that have
        the same VRF under the 'vrf' column and return a list of UUIDs
        of those BGP_Router entries.
    '''

    if new_resource.table not in idl.tables:
        return False

    reference_keys = schema.ovs_tables[new_resource.table].references

    _refCol = None
    for key, value in reference_keys.iteritems():
        if (value.relation == OVSDB_SCHEMA_PARENT and
                value.ref_table == resource.table):
            _refCol = key
            break

    if _refCol is None:
        return False

    # Look for back reference using the index
    if index_list is not None:
        row = verify_index(new_resource, None, index_list, schema, idl)
        if row.__getattr__(_refCol).uuid == resource.row:
            return True
        else:
            return False
    else:
        # Look for all resources that back reference the same parent
        row = None
        row_list = []
        index_list = []
        for item in idl.tables[new_resource.table].rows.itervalues():
            reference = item.__getattr__(_refCol)

            if reference.uuid == resource.row:
                row_list.append(item.uuid)

        if not row_list:
            return False

        new_resource.row = row_list
        return True


def verify_index(resource, parent, index_values, schema, idl):
    '''
        Verify if a resource exists in the DB Table using the index.
    '''

    if resource.table not in idl.tables:
        return None

    # check if we are dealing with key/value type of forward reference
    kv_type = False
    if parent is not None and parent.relation == OVSDB_SCHEMA_CHILD:
        if schema.ovs_tables[parent.table].references[parent.column].kv_type:
            kv_type = True

    if kv_type:
        # check in parent table that the index exists
        app_log.debug('verifying key/value type reference')
        row = utils.kv_index_to_row(index_values, parent, idl)
    else:
        dbtable = idl.tables[resource.table]
        table_schema = schema.ovs_tables[resource.table]

        row = utils.index_to_row(index_values, table_schema, dbtable)

    return row
