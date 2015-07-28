import json

from halonlib.restparser import *
from halonrest.constants import *
from halonrest.utils import utils
import ovs.ovsuuid
import types

class Resource(object):
    def __init__(self, table, row=None, column=None, sub=None):
        self.table = table
        self.row = None
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
    def parse_url_path(path, schema, idl):

        path = Resource.split_path(path)
        if not path:
            return None

        # we only serve URIs that begin with 'system'
        if path[0] != OVSDB_SCHEMA_SYSTEM_URI:
            return None
        else:
            path[0] = OVSDB_SCHEMA_SYSTEM_TABLE

        return Resource.parse(path, schema, idl)

    # recursive routine that compares the URI path with the extended schema
    # and builds resource/subresource relationship. If the relationship
    # referenced by the URI doesn't match with the extended schema we return None
    @staticmethod
    def parse(path, schema, idl):

        if path is None:
            return None

        table_names = schema.ovs_tables.keys()
        reference_map = schema.reference_map
        ovs_tables = schema.ovs_tables

        # Linked List starting with Open_vSwitch
        if path[0] is OVSDB_SCHEMA_SYSTEM_TABLE:
            resource = Resource(path[0])
            resource.row = idl.tables[OVSDB_SCHEMA_SYSTEM_TABLE].rows.keys()[0]

        # Linked List starting with Bridge/Port etc tables
        elif path[0] in table_names:
            resource = Resource(path[0])

        # Linked List starting with bridges/ports etc reference names for tables
        elif path[0] in reference_map:
            resource = Resource(reference_map[path[0]])

        else:
            return None

        # URI: /system
        if len(path) == 1:
            return resource

        if resource.table is OVSDB_SCHEMA_SYSTEM_TABLE:
            system_table = ovs_tables[resource.table]

            if path[1] in system_table.columns:
                resource.column = path[1]

                # URI: /system/db_version
                if resource.column not in system_table.references:
                    if len(path) > 2:
                        return None
                    else:
                        return resource
                else:
                    if resource.column in system_table.children:
                        # URI: /system/bridges
                        resource.relation = OVSDB_SCHEMA_CHILD
                    else:
                        # URI: We don't have any here in current extschema
                        # TODO: Do we need this?
                        resource.relation = OVSDB_SCHEMA_REFERENCE

                    path[1] = reference_map[path[1]]
                    path = path[1:]

            # URI: /system/Port
            # Some tables are accessed directly. They do not have a parent
            elif path[1] in reference_map.values():
                if ovs_tables[path[1]].parent is None:
                    resource.relation = OVSDB_SCHEMA_TOP_LEVEL
                    resource.column = path[1]

                    if len(path) < 2:
                        resource.next = Resource(path[1])
                        return resource
                    else:
                        path = path[1:]

        else:
            # URI: /system/bridges/UUID types will enter this block in the second recursive call
            if ovs.ovsuuid.is_valid_string(path[1]):
                resource.row = ovs.ovsuuid.from_string(path[1])

                # there's more after UUID
                if len(path) > 2:
                    if path[2] in ovs_tables[resource.table].columns:
                        resource.column = path[2]

                        if resource.column not in ovs_tables[resource.table].references:
                            # the URI must end here
                            if len(path) > 3:
                                return None
                            else:
                                # we are done here
                                return resource
                        else:
                            if path[2] in ovs_tables[resource.table].children:
                                resource.relation = OVSDB_SCHEMA_CHILD
                            else:
                                resource.relation = OVSDB_SCHEMA_REFERENCE
                            path[2] = schema.reference_map[path[2]]
                            path = path[2:]
                    else:
                        # bail if its not a column
                        return None
                else:
                    # we are done here
                    return resource
            else:
                return None

        resource.next = Resource.parse(path, schema, idl)
        return resource

    @staticmethod
    def verify_table_entry(table, uuid, idl):
        if table not in idl.tables:
            return False

        if uuid in idl.tables[table].rows:
            return True
        return False

    @staticmethod
    def verify_reference_entry(table, row, column, ref_uuid, idl):
        if table not in idl.tables:
            return False

        idl.tables[table].rows[row].__getattr__(column)
        if row in idl.tables[table].rows:
            references = idl.tables[table].rows[row].__getattr__(column)
            for item in references:
                if item.uuid == ref_uuid:
                    return True
        return False

    # Verify if the resources referenced in the URI are valid DB entries.
    @staticmethod
    def verify_resource_path(resource, schema, idl):
        if resource is None:
            return True

        if resource.row is not None:
            if Resource.verify_table_entry(resource.table, resource.row, idl) is False:
                return False

        if resource.column is not None:
            if resource.column in schema.ovs_tables[resource.table].references:
                if resource.next is not None:
                    if resource.next.row is not None:
                        # check in resource.column if a reference to the next resource is mentioned
                        if Resource.verify_reference_entry(resource.table, resource.row, resource.column, resource.next.row, idl) is False:
                            return False
                    else:
                        # for POST, verification ends here.
                        return True

        return Resource.verify_resource_path(resource.next, schema, idl)

    @staticmethod
    def post_resource(idl, txn, resource, schema, data):

        if resource is None:
            return None

        # we don't allow this right now
        if resource.next is None:
            return None

        while True:
            if resource.next.next is None:
                break
            resource = resource.next

        if resource.relation == OVSDB_SCHEMA_REFERENCE:
            if 'referenced_by' not in data.keys():
                return False
            else:
                # confirm these resources exist
                reference_list = []
                for uri in data['referenced_by']:
                    resource_path = Resource.parse_url_path(uri, schema, idl)
                    if resource_path:
                        if Resource.verify_resource_path(idl, resource_path, schema):
                            reference_list.append(resource_path)
                        else:
                            return False
                    else:
                        return False

        # add new entry to the table
        table = idl.tables[resource.next.table]
        new_row = txn.insert(idl.tables[resource.next.table])

        # TODO: POST data validation
        for key, value in data.iteritems():
            new_row.__setattr__(key, value)

        # add the references
        if resource.relation == OVSDB_SCHEMA_CHILD:
            Resource.add_reference_to_table(idl, resource, new_row)
        elif resource.relation == OVSDB_SCHEMA_REFERENCE:
            for resource in reference_list:
                while True:
                    if resource.next.next is None:
                        break
                    resource = resource.next
                Resource.add_reference_to_table(idl, resource, new_row)

        return txn.commit()

    @staticmethod
    def add_reference_to_table(idl, resource, reference):

        row = idl.tables[resource.table].rows[resource.row]
        references = []
        for item in row.__getattr__(resource.column):
            references.append(item)
        references.append(reference)
        row.__setattr__(resource.column, references)

    @staticmethod
    def get_resource(idl, resource, schema, uri=None):

        if resource is None:
            return None

        # /system
        if resource.next is None:
            if resource.column is None:
                return Resource.get_row_item(idl, schema, resource.table, resource.row, uri)
            else:
                return Resource.get_column_item(idl, schema, resource.table, resource.row, resource.column, uri)

        while True:
            if resource.next.next is None:
                break
            resource = resource.next

        if resource.relation is OVSDB_SCHEMA_REFERENCE:
            uri = OVSDB_BASE_URI + resource.next.table

        if resource.next.row is None:
            if resource.relation is OVSDB_SCHEMA_TOP_LEVEL:
                return Resource.get_table_item(idl, resource.next.table, uri)
            else:
                return Resource.get_column_item(idl, schema, resource.table, resource.row, resource.column, uri)

        elif resource.next.column is None:
            return Resource.get_row_item(idl, schema, resource.next.table, resource.next.row, uri)

        else:
            return Resource.get_column_item(idl, resource.next.table, resource.next.row, resource.next.column, uri)

    @staticmethod
    def get_column_item(idl, schema, table, uuid, column, uri):

        data = utils.to_json(idl.tables[table].rows[uuid].__getattr__(column))

        # UUID to URI
        if column in schema.ovs_tables[table].references:
            data = utils.uuid_to_uri(data, uri)

        return data

    @staticmethod
    def get_row_item(idl, schema, table, uuid, uri):

        column_keys = idl.tables[table].columns.keys()
        row = idl.tables[table].rows[uuid]
        data = utils.row_to_json(row, column_keys)

        # UUID to URI
        table_schema = schema.ovs_tables[table]
        references = table_schema.references.keys()
        for key in references:
            if key in table_schema.children:
                if key in data:
                    data[key] = utils.uuid_to_uri(data[key], uri, key)
            else:
                uri  = OVSDB_BASE_URI + schema.reference_map[key]
                data[key] = utils.uuid_to_uri(data[key], uri)

        return data

    @staticmethod
    def get_table_item(idl, table, uri):

        table = idl.tables[table]
        data = []
        for row in table.rows.itervalues():
            data.append(str(row.uuid))

        return utils.uuid_to_uri(data, uri)

    @staticmethod
    def get_table_item_select(idl, resource, uri=None):

        # get list of references we want
        data = []
        references = idl.tables[resource.table].rows[resource.row].__getattr__(resource.column)
        for r in references:
            data.append(str(r.uuid))

        return data
