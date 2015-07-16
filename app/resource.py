from restparser import *
import json
from utils.utils import *
from constants import *

class Resource(object):
    def __init__(self, table, row=None, column=None, sub=None):
        self.table = table
        self.row = None
        self.column = None
        self.relation = None
        self.next = None

    @staticmethod
    def parse_url_path(path, restschema, idl):


        # capture the URI path in the form of a list
        path = path.split('/')
        path = [i for i in path if i != '']

        if not path:
            return None

        table_names = restschema.ovs_tables.keys()
        reference_map = restschema.reference_map
        ovs_tables = restschema.ovs_tables

        # we only serve URIs that begin with 'system'
        if path[0] != OVSDB_SCHEMA_SYSTEM_URI:
            return None

        path[0] = OVSDB_SCHEMA_SYSTEM_TABLE
        resource = Resource(path[0])
        for row in idl.tables[OVSDB_SCHEMA_SYSTEM_TABLE].rows.itervalues():
            resource.row = str(row.uuid)

        # /system
        if len(path) == 1:
            return resource

        if path[1] in ovs_tables[path[0]].columns:
            resource.column = path[1]

            # e.g. /system/status
            if path[1] not in ovs_tables[path[0]].references:
                if len(path) > 2:
                    return None
                else:
                    return resource
            else:
                if path[1] in ovs_tables[path[0]].children:
                    resource.relation = OVSDB_SCHEMA_CHILD
                else:
                    resource.relation = OVSDB_SCHEMA_REFERENCE
            # e.g. /system/bridges/*
            path = path[1:]
        elif path[1] in table_names:
            resource.column = path[1]
            # e.g. /system/ports/*
            # Table exists. Proceed only if 'Parent' is None
            if ovs_tables[path[1]].parent is not None:
                return None
            resource.relation = OVSDB_SCHEMA_TOP_LEVEL
            path = path[1:]
        elif path[1] in reference_map:
            resource.column = path[1]
            if ovs_tables[reference_map[path[1]]].parent is not None:
                return None
            resource.relation = OVSDB_SCHEMA_TOP_LEVEL
            path = path[1:]
        else:
            # all other cases do not proceed further
            return None

        # we now have the path after /system.
        try:
            resource.next = Resource.parse(path, restschema)
            return resource
        except:
            return None

    # recursive routine that compares the URI path with the extended schema
    # and builds resource/subresource relationship. If the relationship
    # referenced by the URI doesn't match with the extended schema and
    # exception is raised.
    @staticmethod
    def parse(path, restschema):

        if not path:
            return None

        table_names = restschema.ovs_tables.keys()
        reference_map = restschema.reference_map
        ovs_tables = restschema.ovs_tables

        # e.g. /system/bridges/*, /system/ports/*
        # it is possible to have either a table or a reference name here
        if path[0] in table_names:
            table = path[0]
        elif path[0] in reference_map:
            table = reference_map[path[0]]
        else:
            # if there is no such table we bail out
            raise Exception('Incorrect URL')

        resource = Resource(table)

        # e.g. URI: /system/bridges
        if len(path) == 1:
            return resource

        # we have the table name. Now we must have the ID
        # e.g. /system/bridges/UUID/*
        re_uuid = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', re.I)
        if re_uuid.match(path[1]):
            resource.row = path[1]

            # is there more after the UUID?
            if len(path) > 2:
                # is the next element a column of this table?
                # e.g. /system/bridges/UUID/ports, /system/bridges/UUID/name
                if path[2] in ovs_tables[resource.table].columns:
                    resource.column = path[2]

                    # e.g. /system/bridges/UUID/name
                    if resource.column not in ovs_tables[resource.table].references:
                        # the URI must end here as there is no further table
                        # referenced in case of a URI that ends with a non-table name
                        if len(path) > 3:
                            raise Exception('Incorrect URI')
                        else:
                            # we are done here
                            return resource
                    else:
                        if path[2] in ovs_tables[resource.table].children:
                            resource.relation = OVSDB_SCHEMA_CHILD
                        else:
                            resource.relation = OVSDB_SCHEMA_REFERENCE
                    path = path[2:]
                else:
                    # if the next element is not
                    raise Exception('Incorrect URI')
            else:
                # we are done here
                return resource
        else:
            raise Exception('Incorrect URI')

        resource.next = Resource.parse(path, restschema)
        return resource

    @staticmethod
    def verify_table_entry(idl, table, uuid):
        if table not in idl.tables:
            return False

        for item in idl.tables[table].rows.itervalues():
            if str(item.uuid) == uuid:
                return True
        return False

    @staticmethod
    def verify_reference_entry(idl, table, row, column, ref_uuid):
        if table not in idl.tables:
            return False

        for item in idl.tables[table].rows.itervalues():
            if str(item.uuid) == row:
                references = item._data[column].to_string()[1:-1].split(', ')
                if ref_uuid in references:
                    return True
        return False

    # Verify if the resources referenced in the URI are valid DB entries.
    # Upon error raise an exception
    @staticmethod
    def verify_resource_path(idl, resource, restschema):
        if resource is None:
            return None

        if resource.row is not None:
            if Resource.verify_table_entry(idl, resource.table, resource.row) is False:
                raise Exception('Resource verification failed')
        if resource.column is not None:
            # is this a reference?
            if resource.column in restschema.ovs_tables[resource.table].references:
                if resource.next is not None and resource.next.row is not None:
                    # check in resource.column if a reference to the next resource is mentioned
                    if Resource.verify_reference_entry(idl, resource.table, resource.row, resource.column, resource.next.row) is False:
                        raise Exception('Resource verification failed')
        return Resource.verify_resource_path(idl, resource.next, restschema)

    @staticmethod
    def get_resource(idl, resource, restschema, uri):

        if resource is None:
            return None

        # case 1: only one resource
        if resource.next is None:
            pass

        # case 2: more than one resource
        while True:
            if resource.next.next is None:
                break
            resource = resource.next

        # URI determination
        if resource.relation is not OVSDB_SCHEMA_CHILD:
            # TODO: this may be wrong in some cases. e.g. if reference of a table has more than one name
            uri = resource.column

        # check what part of table do we want
        if resource.next.row is None:
            # is this coming from a reference/child
            if resource.relation is not OVSDB_SCHEMA_TOP_LEVEL:
                # get only the references from the resource
                return Resource.get_table_item_select(idl, resource, uri)
            else:
                return Resource.get_table_item(idl, resource.table, uri)
                # get entire table

            return Resource.get_table_item(idl, resource.table, uri)
        elif resource.next.column is None:
            # we need a row
            return Resource.get_row_item(idl, resource.next.table, resource.next.row, uri)
        else:
            # we need a particular column entry
            return Resource.get_column_item(idl, resource.next.table, resource.next.row, resource.next.column, uri)

    @staticmethod
    def get_column_item(idl, table, row, column, uri):

        table = idl.tables[table]
        data = {}

        for item in table.rows.itervalues():
            if str(item.uuid) == row:
                data[column] = str(item.__getattr__(column))
                return data

    @staticmethod
    def get_row_item(idl, table, row, uri):
        data = {}
        table = idl.tables[table]
        column_keys = table.columns.keys()

        for item in table.rows.itervalues():
            if str(item.uuid) == row:
                for key in column_keys:
                    data[key] = '/' + uri.strip('/') + '/' + key
        return data

    @staticmethod
    def get_table_item(idl, table, uri):
        table = idl.tables[table]
        data = []
        for item in table.rows.itervalues():
            value = '/' + uri.strip('/') + '/' + str(item.uuid)
            data.append(value)
        return data

    @staticmethod
    def get_table_item_select(idl, resource, uri):
        # get list of references we want
        table = idl.tables[resource.table]
        for item in table.rows.itervalues():
            if str(item.uuid) == resource.row:
                refdata = item.__getattr__(resource.column)
                # this is a list of references
                reflist = []
                for i in range(0,len(refdata)):
                    reflist.append(str(refdata[i].uuid))
        # TODO: Do we really have to check? If its a reference it must be there
        # or else OVSDB's garbage collection will clean it up.
        data = []
        for item in reflist:
            value = '/' + uri.strip('/') + '/' + str(item)
            data.append(value)
        return data
