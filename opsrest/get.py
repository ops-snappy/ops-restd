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

import ovs.db.idl
from opsrest.constants import *
from opsrest.utils import utils

import types
import json
import urllib
from tornado.log import app_log


def get_resource(idl, resource, schema, uri=None, selector=None):

    if resource is None:
        return None

    # GET on System table
    if resource.next is None:
        return get_row_json(resource.row, resource.table, schema,
                            idl, uri, selector)

    # All other cases

    # get the last resource pair
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    return get_resource_from_db(resource, schema, idl, uri, selector)


# get resource from db using resource->next_resource pair
def get_resource_from_db(resource, schema, idl, uri=None, selector=None):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:

        uri = _get_uri(resource, schema, uri)
        if resource.next.row is None:
            return get_table_json(resource.next.table, schema, idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table,
                                schema, idl, uri, selector)

    elif resource.relation is OVSDB_SCHEMA_CHILD:

        if resource.next.row is None:
            return get_column_json(resource.column, resource.row,
                                   resource.table, schema, idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table,
                                schema, idl, uri, selector)

    elif resource.relation is OVSDB_SCHEMA_REFERENCE:
        uri = _get_uri(resource, schema, uri)
        return get_column_json(resource.column, resource.row, resource.table,
                               schema, idl, uri)

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        if type(resource.next.row) is types.ListType:
            return get_back_references_json(resource.row, resource.table,
                                            resource.next.table, schema,
                                            idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table,
                                schema, idl, uri, selector)

    else:
        return None


def get_row_json(row, table, schema, idl, uri, selector):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    schema_table = schema.ovs_tables[table]

    config_keys = schema_table.config
    stats_keys = schema_table.stats
    status_keys = schema_table.status
    references = schema_table.references
    reference_keys = references.keys()
    for key in reference_keys:
        if references[key].ref_table == schema_table.parent:
            reference_keys.remove(key)
            break

    config_data = utils.row_to_json(db_row, config_keys)
    stats_data = utils.row_to_json(db_row, stats_keys)
    status_data = utils.row_to_json(db_row, status_keys)

    reference_data = {}
    # get URIs of all references
    for key in reference_keys:
        reference_data[key] = get_column_json(key,
                                              row,
                                              table,
                                              schema, idl, uri)
        # depending upon the category of reference
        # pair them with the right data set
        category = references[key].category
        if category == OVSDB_SCHEMA_CONFIG:
            config_data.update({key:reference_data[key]})
        elif category == OVSDB_SCHEMA_STATUS:
            status_data.update({key:reference_data[key]})
        elif category == OVSDB_SCHEMA_STATS:
            stats_data.update({key:reference_data[key]})

    if selector == OVSDB_SCHEMA_CONFIG:
        data = {OVSDB_SCHEMA_CONFIG: config_data}
    elif selector == OVSDB_SCHEMA_STATS:
        data = {OVSDB_SCHEMA_STATS: stats_data}
    elif selector == OVSDB_SCHEMA_STATUS:
        data = {OVSDB_SCHEMA_STATUS: status_data}
    else:
        data = {OVSDB_SCHEMA_CONFIG: config_data, OVSDB_SCHEMA_STATS:
                stats_data, OVSDB_SCHEMA_STATUS: status_data}

    return data


# get list of all table row entries
def get_table_json(table, schema, idl, uri):

    db_table = idl.tables[table]
    schema_table = schema.ovs_tables[table]

    indexes = schema_table.indexes
    uri_list = []

    for row in db_table.rows.itervalues():
        tmp = utils.get_table_key(row, table, schema)
        _uri = _create_uri(uri, tmp)
        uri_list.append(_uri)

    return uri_list


def get_column_json(column, row, table, schema, idl, uri):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    db_col = db_row.__getattr__(column)

    current_table = schema.ovs_tables[table]

    # uri list of resources to return
    uri_list = []

    # case 1: reference is of dict type with index/uuid pairs
    if current_table.references[column].kv_type:
        # we already have the keys
        for key in db_col.keys():
            uri_list.append(uri + '/' + str(key))

    else:
        # case 2: regular reference to a resource
        col_table = current_table.references[column].ref_table
        column_table = schema.ovs_tables[col_table]

        # Is a top level table
        if column_table.parent is None:
            uri = OVSDB_BASE_URI + column_table.plural_name
        # Is a child table, is faster concatenate the uri instead searching
        elif column_table.parent == current_table.name:
            #If we are at a child reference URI we don't add the column path.
            if column_table.plural_name not in uri:
                uri = uri.rstrip('/')
                uri += '/' + column_table.plural_name

        for row in db_col:
            #Reference with different parent, search the parent
            if (column_table.parent is not None and
                    column_table.parent != current_table.name):
                uri = OVSDB_BASE_URI
                uri += utils.get_reference_parent_uri(col_table, row,
                                                      schema, idl)
                uri += column_table.plural_name
            tmp = utils.get_table_key(row, column_table.name, schema)
            _uri = _create_uri(uri, tmp)
            uri_list.append(_uri)

    return uri_list


def get_back_references_json(parent_row, parent_table, table,
                             schema, idl, uri):

    references = schema.ovs_tables[table].references
    _refCol = None
    for key, value in references.iteritems():
        if (value.relation == OVSDB_SCHEMA_PARENT and
                value.ref_table == parent_table):
            _refCol = key
            break

    if _refCol is None:
        return None

    uri_list = []
    indexes = schema.ovs_tables[table].indexes
    for row in idl.tables[table].rows.itervalues():
        ref = row.__getattr__(_refCol)
        if ref.uuid == parent_row:
            tmp = utils.get_table_key(row, table, schema)
            _uri = _create_uri(uri, tmp)
            uri_list.append(_uri)

    return uri_list

def _get_uri(resource, schema, uri=None):

    '''
    returns the right URI based on the category of the
    table.
    e.g. top-level table such as port have /system/ports as URI
    '''
    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            uri = OVSDB_BASE_URI + \
                schema.ovs_tables[resource.next.table].plural_name

    elif resource.relation is OVSDB_SCHEMA_REFERENCE:
            uri = OVSDB_BASE_URI + \
                schema.ovs_tables[resource.next.table].plural_name

    return uri


def _create_uri(uri, paths):
    '''
    uri.rstrip('/'): Removes trailing '/' characters,
    in order to not repeat it when joining it with
    other path.
    Example /system/ports/ -> /system/ports
    '''
    if not uri.endswith('/'):
        uri += '/'
    uri += '/'.join(paths)
    return uri
