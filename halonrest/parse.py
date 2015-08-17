from halonrest.resource import Resource
from halonrest.utils import utils
from halonrest.constants import *
import ovs.ovsuuid

import types
import json

def split_path(path):
    path = path.split('/')
    path = [i for i in path if i!= '']
    return path

def parse_url_path(path, schema, idl, http_method):

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
        return None

    return None


# recursive routine that compares the URI path with the extended schema
# and builds resource/subresource relationship. If the relationship
# referenced by the URI doesn't match with the extended schema we return None
def parse(path, resource, schema, idl, http_method):

    if not path:
        return None

    ovs_tables = schema.ovs_tables
    table_names = ovs_tables.keys()
    reference_map = schema.reference_map

    _fail = False

    # is it a child or non-parent reference?
    if path[0] in ovs_tables[resource.table].columns and path[0] in ovs_tables[resource.table].references:
        resource.column = path[0]
        resource.relation = ovs_tables[resource.table].references[resource.column].relation

        if resource.relation == OVSDB_SCHEMA_PARENT:
            raise Exception("Invalid URI: Parent referenced from child")
        path[0] = reference_map[path[0]]

    # is it a back reference?
    elif path[0] in reference_map:
        path[0] = reference_map[path[0]]
        if path[0] in ovs_tables[resource.table].children and ovs_tables[path[0]].parent == resource.table:
            # back reference to a parent
            resource.relation = OVSDB_SCHEMA_BACK_REFERENCE
        else:
            raise Exception("Invalid URI")

    # is it a top level table?
    elif path[0] in table_names:
        if ovs_tables[path[0]].parent is None:
            if resource.table == OVSDB_SCHEMA_SYSTEM_TABLE:
                resource.relation = OVSDB_SCHEMA_TOP_LEVEL
            else:
                raise Exception("Invalid URI")

        elif ovs_tables[path[0]].parent == resource.table:
            resource.relation = OVSDB_SCHEMA_BACK_REFERENCE
        else:
            raise Exception("Invalid URI")

    else:
        raise Exception("Invalid URI")

    new_resource = Resource(path[0])
    resource.next = new_resource
    path = path[1:]

    # this should be the start of the index
    index_list = None
    if path:
        table_indices = schema.ovs_tables[new_resource.table].indexes

        # len(path) must at least be equal to len(table_indices) to uniquely identify a resource
        if len(path) < len(table_indices):
            return None

        index_list = path[0:len(table_indices)]

    # verify back reference existence
    if resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        if not verify_back_reference(resource, new_resource, schema, idl, index_list):
            raise Exception("Back reference not found")

    # return if we are done processing the URI
    if index_list is None:
        return

    # restrictions for chained references.
    if http_method == 'GET' or http_method == 'POST':
        if resource.relation == OVSDB_SCHEMA_REFERENCE:
            raise Exception("Not allowed")

    # verify non-backreference resource existence
    row = verify_index(new_resource, index_list, schema, idl)
    if row is None:
        raise Exception("Resource not found")
    else:
        new_resource.row = row.uuid
        new_resource.index = index_list

    # we now have a complete new_resource
    # continue processing the path further
    path=path[1:]
    parse(path, new_resource, schema, idl, http_method)

'''
    Some resources have the same parent. BGP_Routers can share the same VRF and hence
    will have the same reference pointer under the 'vrf' column. If bgp_routers for a
    a particular VRF is desired, we search in the entire BGP_Router table to find those
    BGP Routers that have the same VRF under the 'vrf' column and return a list of UUIDs
    of those BGP_Router entries.
'''
def verify_back_reference(resource, new_resource, schema, idl, index_list=None):

    if new_resource.table not in idl.tables:
        return False

    reference_keys = schema.ovs_tables[new_resource.table].references

    _refCol = None
    for key,value in reference_keys.iteritems():
        if value.relation == OVSDB_SCHEMA_PARENT and value.ref_table == resource.table:
            _refCol = key
            break

    if _refCol is None:
        return False

    # Look for back reference using the index
    if index_list is not None:
        row = verify_index(new_resource, index_list, schema, idl)
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

'''
    Verify if a resource exists in the DB Table using the index.
'''
def verify_index(resource, index_values, schema, idl):

    if resource.table not in idl.tables:
        return None

    dbtable = idl.tables[resource.table]
    table_schema = schema.ovs_tables[resource.table]

    row = utils.index_to_row(index_values, table_schema, dbtable)
    return row
