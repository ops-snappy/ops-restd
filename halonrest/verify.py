from halonrest import parse
from halonrest.utils import utils
from halonrest.constants import *
import types

from tornado.log import app_log

def verify_data(data, resource, schema, idl, http_method):

    if http_method == 'POST':
        return verify_post_data(data, resource, schema, idl)

    elif http_method == 'PUT':
        return verify_put_data(data, resource, schema, idl)

def verify_post_data(data, resource, schema, idl):

    # all POST data should be enclosed in { 'configuration' : { DATA } } JSON
    if OVSDB_SCHEMA_CONFIG not in data:
        app_log.info("JSON is missing configuration data")
        return None

    _data = data[OVSDB_SCHEMA_CONFIG]

    # verify config and reference columns data
    verified_data = {}
    verified_config_data = verify_config_data(_data, resource.next, schema)
    if verified_config_data is not None:
        verified_data.update(verified_config_data)

    verified_reference_data = verify_forward_reference(_data, resource.next, schema, idl)
    if verified_reference_data is not None:
        verified_data.update(verified_reference_data)

    # a non-root top-level table must be referenced by another resource
    # or ovsdb-server will garbage-collect it
    is_root = schema.ovs_tables[resource.next.table].is_root
    if resource.relation == OVSDB_SCHEMA_TOP_LEVEL and not is_root:
        if OVSDB_SCHEMA_REFERENCED_BY not in data:
            return None

        _data = data[OVSDB_SCHEMA_REFERENCED_BY]
        try:
            verified_referenced_by_data = verify_referenced_by(_data, resource.next, schema, idl)
            verified_data.update(verified_referenced_by_data)
        except Exception as e:
            app_log.debug(e)
            app_log.info('referenced_by uri verification failed')
            return None

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        for key,value in schema.ovs_tables[resource.next.table].references.iteritems():
            if value.relation == 'parent':
                verified_data.update({key : resource})

    return verified_data

def verify_config_data(data, resource, schema):
    config_keys = schema.ovs_tables[resource.table].config
    verified_config_data = {}
    for key in config_keys:
        if key in data:
            verified_config_data[key] = data[key]

    return verified_config_data

def verify_forward_reference(data, resource, schema, idl):
    reference_keys = schema.ovs_tables[resource.table].references
    verified_references = {}

    for key in reference_keys:
        if reference_keys[key].relation == 'parent':
            continue
        else:
            ref_table = reference_keys[key].ref_table

        if key in data:
            app_log.info(key)
            index_list = data[key]
            reference_list = []
            for index in index_list:
                index_values = index.split('/')
                row = utils.index_to_row(index_values, schema.ovs_tables[ref_table], idl.tables[ref_table])
                reference_list.append(row)
            verified_references[key] = reference_list

    return verified_references

'''
subroutine to validate referenced_by uris/attribute JSON

{
    "referenced_by": [
        {
            "uri": "URI1",
            "attributes": [
                "a",
                "b"
            ]
        },
        {
            "uri": "URI2"
        },
        {
            "uri": "URI3",
            "attributes":[]
        }
    ]
}
'''
def verify_referenced_by(data, resource, schema, idl):

    table = resource.table

    verified_referenced_by = {OVSDB_SCHEMA_REFERENCED_BY : []}
    for item in data:
        uri = item['uri']
        attributes = None

        if 'attributes' in item:
            attributes = item['attributes']

        # verify URI
        uri_resource = parse.parse_url_path(uri, schema, idl, 'POST')

        if uri_resource is None:
            raise Exception('referenced_by resource not found')

        # go to the last resource
        while uri_resource.next is not None:
            uri_resource = uri_resource.next

        if uri_resource.row is None:
            app.debug('uri: ' + uri + ' not found')
            raise Exception('referenced_by resource not found')

        # attributes
        references = schema.ovs_tables[uri_resource.table].references
        reference_keys = references.keys()
        if attributes is not None and len(attributes) > 0:
            for attribute in attributes:
                if attribute not in reference_keys:
                    raise Exception('attribute not found')

                # check attribute is not a parent or child
                if references[attribute].relation is not 'reference':
                    raise Exception('attribute should be a reference')

            # if attribute list has only one element, make it a non-list
            # to keep it consistent with single attribute case (that need not be mentioned)
            if len(attributes) == 1:
                attributes = attributes[0]
        else:
            # find the lone attribute
            _found = False
            for key,value in references.iteritems():
                if value.ref_table == table:
                    if _found:
                        raise Exception('multiple attributes possible, specify one')
                    else:
                        _found = True
                        attributes = key

        # found the uri and attributes
        uri_resource.column = attributes
        verified_referenced_by[OVSDB_SCHEMA_REFERENCED_BY].append(uri_resource)

    return verified_referenced_by
