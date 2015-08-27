from halonrest import parse
from halonrest.constants import *
import types

def verify_data(data, resource, schema, idl, http_method):

    if http_method == 'POST':
        return verify_post_data(data, resource, schema, idl)
    elif http_method == 'PUT':
        return verify_put_data(data, resource, schema, idl)

def verify_post_data(data, resource, schema, idl):

    if OVSDB_SCHEMA_CONFIG not in data:
        return None

    _data = data[OVSDB_SCHEMA_CONFIG]

    if resource.relation == OVSDB_SCHEMA_CHILD:
        verified_data = {}

        verified_config_data = verify_config_data(_data, resource.next, schema)
        if verified_config_data is not None:
            verified_data.update(verified_config_data)

        # verify references

        return verified_data

    elif resource.relation == OVSDB_SCHEMA_REFERENCE:
        config_keys = schema.ovs_tables[resource.next.table].config
        verified_data = {}
        for key in config_keys:
            if key in _data:
                verified_data[key] = _data[key]

        # set up reference
        verified_data['reference'] = resource
        return verified_data

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        config_keys = schema.ovs_tables[resource.next.table].config
        verified_data = {}
        for key in config_keys:
            if key in data:
                verified_data[key] = data[key]

        # set up back reference
        reference_keys = schema.ovs_tables[resource.next.table].references
        for key, value in reference_keys.iteritems():
            if value.ref_table == resource.table:
                _refCol = key
                verified_data[_refCol] = resource
                break

        return verified_data

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        is_root = schema.ovs_tables[resource.next.table].is_root

        if not is_root:
            # does the data have 'belongs_to' key?
            if 'belongs_to' not in data:
                return None

        verified_data = {}
        verified_config_data = verify_config_data(data, resource.next, schema)
        if verified_config_data is not None:
            verified_data.update(verified_config_data)

        verified_reference_data = verify_reference_data(data, resource.next, schema, idl)
        if verified_reference_data is not None:
            verified_data.update(verified_reference_data)

        verified_belongs_to_data = verify_belongs_to_data(data, schema, idl)
        if verified_belongs_to_data is not None:
            verified_data.update(verified_belongs_to_data)

        return verified_data

def verify_config_data(data, resource, schema):
    config_keys = schema.ovs_tables[resource.table].config
    verified_config_data = {}
    for key in config_keys:
        if key in data:
            verified_config_data[key] = data[key]

    return verified_config_data

# convert reference POST/PUT data to resource
def verify_reference_data(data, resource, schema, idl):
    reference_keys = schema.ovs_tables[resource.table].references
    verified_references = {}

    for key in reference_keys:
        if key in data:
            if type(data[key]) is not types.ListType:
                data[key] = [data[key]]

            verified_references[key] = []
            for uri in data[key]:
                resource = parse.parse_url_path(uri, schema, idl, 'POST')
                if resource is not None:
                    # pick the resource
                    while resource.next is not None:
                        resource = resource.next
                    # add to the list
                    verified_references[key].append(resource)

    return verified_references

def verify_belongs_to_data(data, schema, idl):

    verified_belongs_to = {}
    verified_belongs_to['references'] = []
    for uri in data['belongs_to']:
        uri_resource = parse.parse_url_path(uri, schema, idl, 'PUT')
        if uri_resource is None:
            return None
        else:
            # put the verfied resource table info in the list
            while uri_resource.next.next is not None:
                uri_resource = uri_resource.next

            verified_belongs_to['references'].append(uri_resource)
            return verified_belongs_to
