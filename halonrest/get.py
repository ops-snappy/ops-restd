import json

from halonrest.constants import *
from halonrest.utils import utils
import types

def get_resource(idl, resource, schema, uri=None):

    # /system
    if resource.next is None:
        if resource.column is None:
            return get_row_item(idl, schema, resource.table, resource.row, uri)
        else:
            return get_column_item(idl, schema, resource.table, resource.row, resource.column, uri)

    # /system/*
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    if resource.relation is OVSDB_SCHEMA_BACK_REFERENCE:
        if type(resource.next.index) is types.ListType:
            return utils.index_to_uri(resource.next.index, uri)
        else:
            return get_row_item(idl, schema, resource.next.table, resource.next.row, uri)

    if resource.relation is OVSDB_SCHEMA_REFERENCE:
        uri = OVSDB_BASE_URI + resource.next.table

    if resource.next.row is None:
        if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
            return get_table_item(idl, schema, resource.next.table, uri)
        else:
            return get_column_item(idl, schema, resource.table, resource.row, resource.column, uri)

    elif resource.next.column is None:
        return get_row_item(idl, schema, resource.next.table, resource.next.row, uri)

    else:
        return get_column_item(idl, schema, resource.next.table, resource.next.row, resource.next.column, uri)

def get_column_item(idl, schema, table, uuid, column, uri):

    data = utils.to_json(idl.tables[table].rows[uuid].__getattr__(column))

    # convert references to URI
    if column in schema.ovs_tables[table].references:
        reference_table = schema.reference_map[column]
        reference_index_type = schema.ovs_tables[reference_table].index
        reference_index_list = utils.uuid_to_index(data, reference_index_type, idl.tables[reference_table])

        # TODO: Do we have to display the URI of the back reference parent? Name seems more appropriate
        # is this a child?
        if column in schema.ovs_tables[table].children:
            data = utils.index_to_uri(reference_index_list, uri)
        else:
            uri  = OVSDB_BASE_URI + schema.reference_map[column]
            data = utils.index_to_uri(reference_index_list, uri)

    return data

def get_row_item(idl, schema, table, uuid, uri):

    column_keys = idl.tables[table].columns.keys()
    data = {}

    for key in column_keys:
        _uri = uri + '/' + key
        data[key] = get_column_item(idl, schema, table, uuid, key, _uri)

    return data

def get_table_item(idl, schema, table, uri):

    data = []
    for row in idl.tables[table].rows.itervalues():
        data.append(str(row.uuid))

    reference_index_type = schema.ovs_tables[table].index
    reference_index_list = utils.uuid_to_index(data, reference_index_type, idl.tables[table])

    return utils.index_to_uri(reference_index_list, uri)
