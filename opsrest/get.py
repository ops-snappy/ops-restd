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

from opsrest.constants import *
from opsrest.utils import utils
from opsrest.utils import getutils
from opsrest import verify
from opsrest.exceptions import NotFound

import httplib
import types

from tornado.log import app_log


def get_resource(idl, resource, schema, uri=None,
                 selector=None, query_arguments=None):

    depth = getutils.get_depth_param(query_arguments)

    if isinstance(depth, dict) and ERROR in depth:
        return depth

    if resource is None:
        return None

    # GET on System table
    if resource.next is None:

        if query_arguments is not None:
            validation_result = \
                getutils.validate_non_plural_query_args(query_arguments)

            if ERROR in validation_result:
                return validation_result

        return get_row_json(resource.row, resource.table, schema,
                            idl, uri, selector, depth)

    # All other cases

    # get the last resource pair
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    if verify.verify_http_method(resource, schema, "GET") is False:
        raise Exception({'status': httplib.METHOD_NOT_ALLOWED})

    return get_resource_from_db(resource, schema, idl, uri,
                                selector, query_arguments, depth)


# get resource from db using resource->next_resource pair
def get_resource_from_db(resource, schema, idl, uri=None,
                         selector=None, query_arguments=None,
                         depth=0):

    resource_result = None
    uri = _get_uri(resource, schema, uri)
    table = None

    # Determine if result will be a collection or a single
    # resource, plus the table to use in post processing
    is_collection = _is_result_a_collection(resource)
    table = resource.next.table

    sorting_args = []
    filter_args = {}
    pagination_args = {}
    offset = None
    limit = None

    validation_result = getutils.validate_query_args(sorting_args, filter_args,
                                                     pagination_args,
                                                     query_arguments,
                                                     schema, resource.next,
                                                     selector, depth,
                                                     is_collection)
    if ERROR in validation_result:
        return validation_result

    if REST_QUERY_PARAM_OFFSET in pagination_args:
        offset = pagination_args[REST_QUERY_PARAM_OFFSET]
    if REST_QUERY_PARAM_LIMIT in pagination_args:
        limit = pagination_args[REST_QUERY_PARAM_LIMIT]

    app_log.debug("Sorting args: %s" % sorting_args)
    app_log.debug("Filter args: %s" % filter_args)
    app_log.debug("Limit % s" % limit)
    app_log.debug("Offset % s" % offset)

    # Get the resource result according to result type
    if is_collection:
        resource_result = get_collection_json(resource, schema, idl, uri,
                                              selector, depth)
    else:
        resource_result = get_row_json(resource.next.row, resource.next.table,
                                       schema, idl, uri, selector, depth)

    # Post process data if it necessary
    if (resource_result and depth and isinstance(resource_result, list)):
        # Apply filters, sorting, and pagination
        resource_result = getutils.post_process_get_data(resource_result,
                                                         sorting_args,
                                                         filter_args, offset,
                                                         limit, schema, table,
                                                         selector,
                                                         categorize=True)

    return resource_result


def get_collection_json(resource, schema, idl, uri, selector, depth):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        resource_result = get_table_json(resource.next.table, schema, idl, uri,
                                         selector, depth)

    elif resource.relation is OVSDB_SCHEMA_CHILD:
        resource_result = get_column_json(resource.column, resource.row,
                                          resource.table, schema, idl, uri,
                                          selector, depth)

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        resource_result = get_back_references_json(resource.row,
                                                   resource.table,
                                                   resource.next.table, schema,
                                                   idl, uri, selector, depth)

    return resource_result


def get_row_json(row, table, schema, idl, uri, selector=None,
                 depth=0, depth_counter=0):

    depth_counter += 1
    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    schema_table = schema.ovs_tables[table]

    config_keys = {}
    config_data = {}
    if selector is None or selector == OVSDB_SCHEMA_CONFIG:
        config_keys = schema_table.config
        config_data = utils.row_to_json(db_row, config_keys)
    # To remove the unnecessary empty values from the config data
    config_data = {key:config_data[key] for key in config_keys
                   if not(config_data[key] == None or
                   config_data[key] == {} or config_data[key] == [])}

    stats_keys = {}
    stats_data = {}
    if selector is None or selector == OVSDB_SCHEMA_STATS:
        stats_keys = schema_table.stats
        stats_data = utils.row_to_json(db_row, stats_keys)
    # To remove all the empty columns from the satistics data
    stats_data = {key: stats_data[key] for key in stats_keys
                  if stats_data[key]}

    status_keys = {}
    status_data = {}
    if selector is None or selector == OVSDB_SCHEMA_STATUS:
        status_keys = schema_table.status
        status_data = utils.row_to_json(db_row, status_keys)
    # To remove all the empty columns from the status data
    status_data = {key: status_data[key] for key in status_keys
                   if status_data[key]}

    references = schema_table.references
    reference_data = []
    for key in references:
        # Don't consider back references
        if references[key].ref_table != schema_table.parent:
            if (depth_counter >= depth):
                depth = 0

        temp = get_column_json(key, row, table, schema,
               idl, uri, selector, depth,
               depth_counter)

        # The condition below is used to discard the empty list of references
        # in the data returned for get requests
        if not temp:
            continue

        reference_data = temp
   
        # depending upon the category of reference
        # pair them with the right data set
        category = references[key].category

        if config_keys and category == OVSDB_SCHEMA_CONFIG:
            config_data.update({key: reference_data})

        elif stats_keys and category == OVSDB_SCHEMA_STATS:
            stats_data.update({key: reference_data})

        elif (depth_counter >= depth):
            depth = 0

        elif status_keys and category == OVSDB_SCHEMA_STATUS:
            status_data.update({key: reference_data})

    # TODO Data categorization should be refactored as it
    # is also executed when sorting and filtering results

    data = getutils._categorize_by_selector(config_data, stats_data,
                                            status_data, selector)

    return data


# get list of all table row entries
def get_table_json(table, schema, idl, uri, selector=None, depth=0):

    db_table = idl.tables[table]

    resources_list = []

    if not depth:
        for row in db_table.rows.itervalues():
            tmp = utils.get_table_key(row, table, schema, idl)
            _uri = _create_uri(uri, tmp)
            resources_list.append(_uri)
    else:
        for row in db_table.rows.itervalues():
            json_row = get_row_json(row.uuid, table, schema, idl, uri,
                                    selector, depth)
            resources_list.append(json_row)

    return resources_list


def get_column_json(column, row, table, schema, idl, uri,
                    selector=None, depth=0, depth_counter=0):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    db_col = db_row.__getattr__(column)

    current_table = schema.ovs_tables[table]

    # list of resources to return
    resources_list = []

    # Reference Column
    col_table = current_table.references[column].ref_table
    column_table = schema.ovs_tables[col_table]

    # GET without depth
    if not depth:
        # Is a top level table
        if column_table.parent is None:
            uri = _get_base_uri() + column_table.plural_name
        # Is a child table, is faster concatenate the uri instead searching
        elif column_table.parent == current_table.name:
            # If this is a child reference URI don't add the column path.
            if column_table.plural_name not in uri:
                uri = uri.rstrip('/')
                uri += '/' + column_table.plural_name

        for value in db_col:

            ref_row = _get_referenced_row(schema, table, row,
                                          column, value, idl)

            # Reference with different parent, search the parent
            if column_table.parent is not None and \
                    column_table.parent != current_table.name:
                uri = _get_base_uri()
                uri += utils.get_reference_parent_uri(col_table, ref_row,
                                                      schema, idl)
                uri += column_table.plural_name

            # Set URI for key
            tmp = utils.get_table_key(ref_row, column_table.name, schema, idl)
            _uri = _create_uri(uri, tmp)

            resources_list.append(_uri)
    # GET with depth
    else:
        for value in db_col:

            ref_row = _get_referenced_row(schema, table, row,
                                          column, value, idl)
            json_row = get_row_json(ref_row.uuid, col_table, schema, idl, uri,
                                    selector, depth, depth_counter)
            resources_list.append(json_row)

    return resources_list


def _get_referenced_row(schema, table, row, column, column_row, idl):

    schema_table = schema.ovs_tables[table]

    # Set correct row for kv_type references
    if schema_table.references[column].kv_type:
        db_table = idl.tables[table]
        db_row = db_table.rows[row]
        db_col = db_row.__getattr__(column)
        return db_col[column_row]
    else:
        return column_row


def get_back_references_json(parent_row, parent_table, table,
                             schema, idl, uri, selector=None,
                             depth=0):

    references = schema.ovs_tables[table].references
    _refCol = None
    for key, value in references.iteritems():
        if (value.relation == OVSDB_SCHEMA_PARENT and
                value.ref_table == parent_table):
            _refCol = key
            break

    if _refCol is None:
        return None

    resources_list = []

    if not depth:
        for row in idl.tables[table].rows.itervalues():
            ref = row.__getattr__(_refCol)
            if ref.uuid == parent_row:
                tmp = utils.get_table_key(row, table, schema, idl)
                _uri = _create_uri(uri, tmp)
                resources_list.append(_uri)
    else:
        for row in idl.tables[table].rows.itervalues():
            ref = row.__getattr__(_refCol)
            if ref.uuid == parent_row:
                json_row = get_row_json(row.uuid, _refCol, schema, idl, uri,
                                        selector, depth)
                resources_list.append(json_row)

    return resources_list


def _get_base_uri():
    return OVSDB_BASE_URI


def _get_uri(resource, schema, uri=None):
    '''
    returns the right URI based on the category of the
    table.
    e.g. top-level table such as port have /system/ports as URI
    '''
    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            uri = _get_base_uri() + \
                schema.ovs_tables[resource.next.table].plural_name

    return uri


def _create_uri(uri, paths):
    '''
    Removes trailing '/' characters,
    in order to not repeat it when joining it with
    other path.
    Example /system/ports/ -> /system/ports
    '''
    if not uri.endswith('/'):
        uri += '/'
    uri += '/'.join(paths)
    return uri


def _is_result_a_collection(resource):

    is_collection = False

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            is_collection = True

    elif resource.relation is OVSDB_SCHEMA_CHILD:
        if resource.next.row is None:
            is_collection = True

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        if isinstance(resource.next.row, types.ListType):
            is_collection = True

    return is_collection
