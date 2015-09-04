import ovs.db.idl
from halonrest.constants import *
from halonrest.utils import utils

import types
import json
from tornado.log import app_log

def get_resource(idl, resource, schema, uri=None):

    if resource is None:
        return None

    # GET Open_vSwitch table
    if resource.next is None:
        return get_row_json(resource.row, resource.table, schema, idl, uri)

    # Other tables
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    return get_resource_from_db(resource, schema, idl, uri)

# get resource from db using resource->next_resource pair
def get_resource_from_db(resource, schema, idl, uri=None):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:

        uri = get_uri(resource, schema, uri)
        if resource.next.row is None:
            return get_table_json(resource.next.table, schema, idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table, schema, idl, uri)

    elif resource.relation is OVSDB_SCHEMA_CHILD:

        if resource.next.row is None:
            return get_column_json(resource.column, resource.row, resource.table, schema, idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table, schema, idl, uri)

    elif resource.relation is OVSDB_SCHEMA_REFERENCE:
        uri = get_uri(resource, schema, uri)
        return get_column_json(resource.column, resource.row, resource.table, schema, idl, uri)

    elif resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        if type(resource.next.row) is types.ListType:
            return get_back_references_json(resource.row, resource.table, resource.next.table, schema, idl, uri)
        else:
            return get_row_json(resource.next.row, resource.next.table, schema, idl, uri)

    else:
        return None

def get_row_json(row, table, schema, idl, uri):

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
        reference_data[key] = get_column_json(key, row, table, schema, idl, uri)

    # references are part of configuration
    config_data.update(reference_data)

    data = {OVSDB_SCHEMA_CONFIG:config_data, OVSDB_SCHEMA_STATS:stats_data, OVSDB_SCHEMA_STATUS:status_data}
    return data

# get list of all table row entries
def get_table_json(table, schema, idl, uri):

    db_table = idl.tables[table]
    schema_table = schema.ovs_tables[table]

    indexes = schema_table.indexes
    uri_list = []

    for row in db_table.rows.itervalues():
        tmp = []
        for index in indexes:
            if index == 'uuid':
                tmp.append(str(row.uuid))
            else:
                tmp.append(str(row.__getattr__(index)))
        _uri = create_uri(uri, tmp)
        uri_list.append(_uri)

    return uri_list

def get_column_json(column, row, table, schema, idl, uri):

    db_table = idl.tables[table]
    db_row = db_table.rows[row]
    db_col = db_row.__getattr__(column)

    # column is a reference. Get the table name
    col_table = schema.ovs_tables[table].references[column].ref_table
    indexes = schema.ovs_tables[col_table].indexes

    if schema.ovs_tables[col_table].parent is None:
        uri = OVSDB_BASE_URI + schema.ovs_tables[col_table].plural_name

    uri_list = []
    for row in db_col:
        tmp = []
        for index in indexes:
            if index == 'uuid':
                tmp.append(str(row.uuid))
            else:
                tmp.append(str(row.__getattr__(index)))
        _uri = create_uri(uri, tmp)
        uri_list.append(_uri)

    return uri_list

def get_back_references_json(parent_row, parent_table, table, schema, idl, uri):

    references = schema.ovs_tables[table].references
    _refCol = None
    for key,value in references.iteritems():
        if value.relation == OVSDB_SCHEMA_PARENT and value.ref_table == parent_table:
            _refCol = key
            break

    if _refCol is None:
        return None

    uri_list = []
    indexes = schema.ovs_tables[table].indexes
    for row in idl.tables[table].rows.itervalues():
        ref = row.__getattr__(_refCol)
        if ref.uuid == parent_row:
            tmp = []
            for index in indexes:
                if index == 'uuid':
                    tmp.append(str(row.uuid))
                else:
                    tmp.append(str(row.__getattr__(index)))
            _uri = create_uri(uri, tmp)
            uri_list.append(_uri)

    return uri_list

def get_uri(resource, schema, uri=None):

    if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
        if resource.next.row is None:
            uri = OVSDB_BASE_URI + schema.ovs_tables[resource.next.table].plural_name

    elif resource.relation is OVSDB_SCHEMA_REFERENCE:
            uri = OVSDB_BASE_URI + schema.ovs_tables[resource.next.table].plural_name

    return uri

def create_uri(uri, paths):
    '''
    uri.rstrip('/'): Removes trailing '/' characters,
    in order to not repeat it when joining it with
    other path.
    Example /system/ports/ -> /system/ports
    '''
    uri = uri.rstrip('/')
    if len(paths) > 1:
        return uri + "/".join(paths)
    else:
        return uri + "/" + paths[0]
