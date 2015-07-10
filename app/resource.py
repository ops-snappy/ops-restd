from restparser import *
import json
from utils import *
from constants import *

class Resource(object):
    def __init__(self, table, name=None, datatype=None, reference=None):
        self.table = table
        self.name = name
        self.datatype = datatype
        self.reference = None
        self.next = None
        self.uuid = None

    @staticmethod
    def parse_url_path(path, restschema):
        if not path:
            return None

        tables = restschema.ovs_tables

        # we support URLs of type /system/* only. Where 'system'
        # refers to 'Open_Vswitch' table in OVSDB
        key = path[0]
        if key == OVSDB_SCHEMA_TOP_LEVEL_URL_PATH:
            key = OVSDB_SCHEMA_TOP_LEVEL_TABLE

        # this refers to URLs such as
        # /system, /system/bridges
        # TODO: we do not support such URLs right now
        if len(path) == 1:
            # this could be a top level resource or a child
            resource = Resource(key)
            resource.datatype = key
            return resource

        # this refers to URLs such as
        # /system/bridges/br_id, /system/bridges/br_id/ports
        # (resource name followed by id/subresource/)
        if key in restschema.ovs_tables:
            resource = Resource(key)
            resource_table = restschema.ovs_tables[key]

        # is next key a subresource of resource?
        if path[1] in resource_table.references:
            reftable = resource_table.references[path[1]].table
            resource.name = None
            resource.datatype = None
            resource.reference = {'name': path[1], 'relation':
                    resource_table.references[path[1]].relation}
            path = path[1:]
            path[0] = reftable
            resource.next = Resource.parse_url_path(path, restschema)
        else:
            resource.name = path[1]

            # check if URL has 'config/status/status' after the resource name
            if len(path) > 2:
                # TODO: We support these keywords only at the end. Why don't we
                # just return an error if the url is of type
                # /system/bridges/br01/config/ports/br01 <-- This is wrong
                if path[2] in ['config', 'stats', 'status']:
                    # check if the URL has 'config/status/stats' after the resource
                    # name. If this is true then it is the last resource in the URL
                    resource.datatype = path[2]

                elif path[2] in resource_table.references:
                    # check if its a reference of the current resource.
                    # a reference can be one of {reference, child, parent}
                    resource.reference = {'name': path[2], 'relation':
                            resource_table.references[path[2]].relation}
                    path = path[2:]
                    path[0] = resource_table.references[path[0]].table

                    resource.next = Resource.parse_url_path(path, restschema)
        return resource

    @staticmethod
    def verify_table_entry(idl, table, name):
        if table not in idl.tables:
            return None

        if table == OVSDB_SCHEMA_TOP_LEVEL_TABLE:
            for row in idl.tables[table].rows.itervalues():
                return str(row.uuid)

        for row in idl.tables[table].rows.itervalues():
            if row.name == name:
                return str(row.uuid)
        return None

    @staticmethod
    def verify_reference_entry(idl, table, uuid, ref_key, ref_table, ref_name):
        ref_uuid = Resource.verify_table_entry(idl, ref_table, ref_name)
        if ref_uuid is not None:
            # iterate over the resource table and verify if ref_uuid is referenced
            for row in idl.tables[table].rows.itervalues():
                if str(row.uuid) == uuid:
                    references = row._data[ref_key].to_string()[1:-1].split(', ')
                    if ref_uuid in references:
                        return ref_uuid
        return None

    '''
    HTTP methods supported by autotranslator: GET, POST

    GET URL examples:
    /system/bridges/config
    /system/bridges/stats
    /system/bridges/status

    /system/bridges/id/config
    /system/bridges/id/vlans

    POST URL examples:
    /system/bridges
    /system/bridges/id/vlans

    config: read/write data
    status/stats: read only data

    '''
    @staticmethod
    def verify_resource_path(idl, resource):

        if resource is None:
            return None

        if resource.table is OVSDB_SCHEMA_TOP_LEVEL_TABLE:
            resource.uuid = Resource.verify_table_entry(idl,
                    resource.table, resource.table)
        elif resource.name is not None and resource.uuid is None:
            resource.uuid = Resource.verify_table_entry(idl, resource.table, resource.name)
        elif resource.name is None and resource.uuid is None and (resource.table
            is resource.datatype):
                resource.uuid = 'reference'

        if resource.uuid is None:
            raise Exception('resource verification failed')

        # the first resource may not have a 'name' but can have 'reference'
        if resource.reference is not None and resource.next is not None and resource.next.name is not None:
            if resource.reference['relation'] == 'parent':
                # we do not serve this reference relation
                raise Exception('URL not allowed')

            resource.next.uuid = Resource.verify_reference_entry(idl,
                    resource.table, resource.uuid, resource.reference['name'], resource.next.table, resource.next.name)
            if resource.next.uuid is None:
                raise Exception('resource verification failed')

        # we have so far verified either the first resource and/or its reference, continue further
        Resource.verify_resource_path(idl, resource.next)
