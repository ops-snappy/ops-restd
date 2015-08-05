import json

from halonlib.restparser import *
from halonrest.constants import *
import ovs.ovsuuid
import types

class Resource(object):
    def __init__(self, table, row=None, column=None, index=None, relation=None):
        self.table = table
        self.row = None
        self.index = None
        self.column = None
        self.relation = None
        self.next = None

    # URI to a list
    @staticmethod
    def split_path(path):
        path = path.split('/')
        path = [i for i in path if i!= '']
        return path

    # parse the URI into a linked list of Resource structures
    @staticmethod
    def parse_url_path(path, schema, idl, http_method):

        path = Resource.split_path(path)
        if not path:
            return None

        # we only serve URIs that begin with 'system'
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
            Resource.parse(path, resource, schema, idl, http_method)
            return resource
        except Exception as e:
            # TODO: Log the exception value
            return None

        return None


    # recursive routine that compares the URI path with the extended schema
    # and builds resource/subresource relationship. If the relationship
    # referenced by the URI doesn't match with the extended schema we return None
    @staticmethod
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
            # check the parent name
            if ovs_tables[path[0]].parent is None:
                if resource.table == OVSDB_SCHEMA_SYSTEM_TABLE:
                    resource.relation = OVSDB_SCHEMA_TOP_LEVEL
                else:
                    _fail = True
            else:
                _fail = True
        else:
            _fail = True

        if _fail:
            raise Exception("Resource not found")

        new_resource = Resource(path[0])
        resource.next = new_resource
        path = path[1:]

        index = None
        if path:
            index = path[0]

        # verify back reference existence
        if resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
            if Resource.verify_back_reference(resource, new_resource, schema, idl, index) is None:
                raise Exception("Back reference not found")

        # return if we are done processing the URI
        if index is None:
            return

        # restrictions for chained references.
        if http_method == 'GET' or http_method == 'POST':
            if resource.relation == OVSDB_SCHEMA_REFERENCE:
                raise Exception("Not allowed")

        # verify non-backreference resource existence
        row = Resource.verify_index(new_resource, index, schema, idl)
        if row is None:
            raise Exception("Resource not found")
        else:
            new_resource.row = row
            new_resource.index = index

        # we now have a complete new_resource
        # continue processing the path further
        path=path[1:]
        Resource.parse(path, new_resource, schema, idl, http_method)

    # one or more entries in a table can share the same back reference.
    # e.g. BGP_Router can have more than one entry that share the same VRF.
    @staticmethod
    def verify_back_reference(resource, new_resource, schema, idl, index=None):

        # does the table exist
        if new_resource.table not in idl.tables:
            return None

        # TODO: temp hack
        index_type = schema.index_map[new_resource.table]

        # is resource.table a reference in new_resource.table?
        # column_keys = idl.tables[new_resource.table].columns.keys()
        column_keys = schema.ovs_tables[new_resource.table].references

        _refCol = None
        for key,value in column_keys.iteritems():
            if value.relation == OVSDB_SCHEMA_PARENT:
                _refCol = key
                break

        if _refCol is None:
            return None

        # verify using the index if the parent is back referenced
        if index is not None:
            if Resource.verify_index(new_resource, index, schema, idl) is None:
                return None
        else:
            # search iteratively in entire table and get list of all entries with same back reference
            row = None
            row_list = []
            index_list = []
            for item in idl.tables[new_resource.table].rows.itervalues():
                reference = item.__getattr__(_refCol)

                if reference.uuid == resource.row:
                    row_list.append(item.uuid)
                    index_list.append(str(item.__getattr__(index_type)))

            # no back reference found. URI is incorrect
            if not row_list:
                return None

            new_resource.row = row_list
            new_resource.index = index_list

        return new_resource

    # verifies if resource exist using resource/new_resource relationship
    @staticmethod
    def verify_index(resource, index, schema, idl):

        # does the table exist
        table = resource.table
        if table not in idl.tables:
            return None


        # TODO: temp hack
        # index_type = schema.ovs_tables[table].index
        index_type = schema.index_map[table]

        # index is a non-UUID column item
        if index_type in schema.ovs_tables[table].columns:
            # get the row that matches the index
            for row in idl.tables[table].rows.itervalues():
                if str(row.__getattr__(index_type)) == index:
                    resource.index == index
                    resource.row = row.uuid
                    return row.uuid
            return None

        # index can also be UUID in some cases
        elif ovs.ovsuuid.is_valid_string(index):
            uuid = ovs.ovsuuid.from_string(path[1])
            if uuid in idl.tables[table].rows:
                resource.index = index
                resource.row = uuid
                return uuid

        return None
