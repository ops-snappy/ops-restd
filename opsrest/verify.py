from opsrest import parse
from opsrest.utils import utils
from opsrest.constants import *
import types
import httplib

from tornado.log import app_log
from opsrest.utils.utils import to_json_error
from ovs.db import types as ovs_types

def verify_data(data, resource, schema, idl, http_method):

    if http_method == 'POST':
        return verify_post_data(data, resource, schema, idl)

    elif http_method == 'PUT':
        return verify_put_data(data, resource, schema, idl)

def verify_post_data(data, resource, schema, idl):

    _data = get_config_data(data)

    if ERROR in _data:
        return _data

    # verify config and reference columns data
    verified_data = {}
    verified_config_data = verify_config_data(_data, resource.next, schema, 'POST')
    if verified_config_data is not None:
        if ERROR in verified_config_data:
            return verified_config_data
        else:
            verified_data.update(verified_config_data)

    verified_reference_data = verify_forward_reference(_data, resource.next, schema, idl)
    if verified_reference_data is not None:
        if ERROR in verified_reference_data:
            return verified_reference_data
        else:
            verified_data.update(verified_reference_data)

    # a non-root top-level table must be referenced by another resource
    # or ovsdb-server will garbage-collect it
    is_root = schema.ovs_tables[resource.next.table].is_root
    if resource.relation == OVSDB_SCHEMA_TOP_LEVEL and not is_root:
        if OVSDB_SCHEMA_REFERENCED_BY not in data:
            error_json = to_json_error("Missing %s" % OVSDB_SCHEMA_REFERENCED_BY, None, OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

        _data = data[OVSDB_SCHEMA_REFERENCED_BY]
        try:
            verified_referenced_by_data = verify_referenced_by(_data, resource.next, schema, idl)
            if ERROR in verified_referenced_by_data:
                return verified_referenced_by_data
            else:
                verified_data.update(verified_referenced_by_data)

        except Exception as e:
            app_log.debug('referenced_by uri verification failed')
            app_log.debug("Reason: %s" % e)
            error_json = to_json_error(str(e), None, OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        for key,value in schema.ovs_tables[resource.next.table].references.iteritems():
            if value.relation == 'parent':
                verified_data.update({key : resource})

    return verified_data

def verify_put_data(data, resource, schema, idl):

    _data = get_config_data(data)

    if ERROR in _data:
        return _data

    # We neet to verify System table
    if resource.next is None:
        resource_verify = resource
    else:
        resource_verify = resource.next

    # verify config and reference columns data
    verified_data = {}
    verified_config_data = verify_config_data(_data, resource_verify, schema, 'PUT')

    if verified_config_data is not None:
        if ERROR in verified_config_data:
            return verified_config_data
        else:
            verified_data.update(verified_config_data)

    verified_reference_data = verify_forward_reference(_data, resource_verify, schema, idl)
    if verified_reference_data is not None:
        if ERROR in verified_reference_data:
            return verified_reference_data
        else:
            verified_data.update(verified_reference_data)

    is_root = schema.ovs_tables[resource_verify.table].is_root

    #Reference by is not allowed in put
    if resource.relation == OVSDB_SCHEMA_TOP_LEVEL and not is_root:
        if OVSDB_SCHEMA_REFERENCED_BY in data:
            app_log.info('referenced_by is not allowed when doing PUT')
            error_json = to_json_error("%s not allowed for PUT" % OVSDB_SCHEMA_REFERENCED_BY, None, OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

    return verified_data

def verify_config_data(data, resource, schema, http_method):
    config_keys = schema.ovs_tables[resource.table].config
    reference_keys = schema.ovs_tables[resource.table].references

    verified_config_data = {}
    error_json = {}

    # Check for extra or unknown attributes
    unknown_attribute = find_unknown_attribute(data, config_keys, reference_keys)
    if unknown_attribute is not None:
        error_json = to_json_error("Unknown configuration attribute", None, unknown_attribute)
        return {ERROR: error_json}

    non_mutable_attributes = get_non_mutable_attributes(resource, schema)

    # Check for all required/valid attributes to be present
    for column_name in config_keys:

        if column_name in data:

            check_type_result = verify_attribute_type(column_name, config_keys[column_name], data[column_name])
            if ERROR in check_type_result:
                return check_type_result

            check_range_result = verify_attribute_range(column_name, config_keys[column_name], data[column_name])
            if ERROR in check_range_result:
                return check_range_result

            if http_method == 'POST':
                verified_config_data[column_name] = data[column_name]

            elif http_method == 'PUT':
                if column_name not in non_mutable_attributes:
                    verified_config_data[column_name] = data[column_name]

        # PUT ignores non mutable attributes, otherwise they are required
        elif http_method == 'PUT':
            if column_name not in non_mutable_attributes:
                error_json = to_json_error("Attribute is missing from request", None, column_name)
                return {ERROR: error_json}

        # Anything else (POST) requires all attributes
        else:
            error_json = to_json_error("Attribute is missing from request", None, column_name)
            return {ERROR: error_json}

    return verified_config_data

def verify_attribute_type(column_name, column_data, request_data):
    data = request_data
    data_type = type(data)
    valid_types = column_data.type.python_types
    error_json = {}
    result = {}

    # If column is a list, data must be a list
    if column_data.is_list:
        valid_types = [list]

    # If column is a dictionary, data must be a dictionary
    elif column_data.is_dict:
        valid_types = [dict]

    # If data is a list but column is not,
    # we expect a single value in the list
    elif data_type is list:
        if len(data) == 1:
            data = data[0]
            data_type = type(data)

    if data_type in valid_types:
        if not verify_valid_attribute_values(data, column_data):
            error_json = to_json_error("Attribute value is invalid", None, column_name)
    else:
        error_json = to_json_error("Attribute type mismatch", None, column_name)

    if error_json:
        result = {ERROR: error_json}

    return result

def verify_valid_attribute_values(request_data, column_data):
    valid = True

    # If data has an enum defined, check for a valid value
    if column_data.enum:

        enum = set(column_data.enum.as_list())

        # Check if request's list contains values not valid
        if type(request_data) is list:
            if set(request_data).difference(enum):
                valid = False

        # Check if single request value is valid
        elif request_data not in enum:
            valid = False

    return valid

def verify_attribute_range(column_name, column_data, request_data):

    # We assume verify_attribute_type has already been called,
    # so request_data type must be correct (save for a small
    # exception if column is list)

    result = {}
    error_json = {}
    data_type = type(request_data)

    # Check elements in in a list
    if column_data.is_list:

        # Exception: a single value might be accepted
        # by OVSDB as a single element list
        request_list = []
        if data_type is not list:
            request_list.append(request_data)
        else:
            request_list = request_data

        request_len = len(request_list)
        if request_len < column_data.n_min or request_len > column_data.n_max:
            error_json = to_json_error("List's number of elements is out of range", None, column_name)
        else:
            for element in request_list:
                # We usually check the value itself
                # But for a string, we check its length instead
                value = element
                if type(element) in ovs_types.StringType.python_types:
                    value = len(element)

                if value < column_data.rangeMin or value > column_data.rangeMax:
                    error_json = to_json_error("List element '%s' is out of range" % element, None, column_name)
                    break

    # Check elements in a dictionary
    elif column_data.is_dict:
        request_len = len(request_data)
        if request_len < column_data.n_min or request_len > column_data.n_max:
            error_json = to_json_error("Dictionary's number of elements is out of range", None, column_name)
        else:
            for key, data in request_data.iteritems():

                value = key
                if type(key) in ovs_types.StringType.python_types:
                    value = len(key)

                if value < column_data.rangeMin or value > column_data.rangeMax:
                    error_json = to_json_error("Dictionary key '%s' is out of range" % key, None, column_name)
                    break

                value = data
                if type(data) in ovs_types.StringType.python_types:
                    value = len(data)

                if value < column_data.valueRangeMin or value > column_data.valueRangeMax:
                    error_json = to_json_error("Dictionary value '%s' is out of range" % data, None, column_name)
                    break

    # Check single elements (non-list/non-dictionary)
    # Except boolean, as there's no range for them
    elif data_type not in ovs_types.BooleanType.python_types:

        # Exception: if column is not a list,
        # a single value list is accepted
        if data_type is list:
            value = request_data[0]
            data_type = type(value)
        else:
            value = request_data

        if data_type in ovs_types.StringType.python_types:
            value = len(value)

        if value < column_data.rangeMin or value > column_data.rangeMax:
            error_json = to_json_error("Attribute value is out of range", None, column_name)

    if error_json:
        result = {ERROR: error_json}

    return result

def verify_forward_reference(data, resource, schema, idl):
    reference_keys = schema.ovs_tables[resource.table].references
    verified_references = {}

    for key in reference_keys:
        if reference_keys[key].relation == 'parent':
            continue
        else:
            ref_table = reference_keys[key].ref_table

        if key in data:
            index_list = data[key]

            # Check range of references
            index_len = len(index_list)
            reference_min = reference_keys[key].n_min
            reference_max = reference_keys[key].n_max
            if index_len < reference_min or index_len > reference_max:
                error_json = to_json_error("Reference list out of range", None, key)
                return {ERROR: error_json}

            reference_list = []
            for index in index_list:
                index_values = index.split('/')
                row = utils.index_to_row(index_values[-1:], schema.ovs_tables[ref_table], idl.tables[ref_table])
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
            app_log.debug('uri: ' + uri + ' not found')
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

def find_unknown_attribute(data, config_keys, reference_keys):

    for column_name in data:
        if not (column_name in config_keys or column_name in reference_keys):
            return column_name

    return None

def get_non_mutable_attributes(resource, schema):
    config_keys = schema.ovs_tables[resource.table].config
    reference_keys = schema.ovs_tables[resource.table].references

    attribute_keys = {}
    attribute_keys.update(config_keys)
    attribute_keys.update(reference_keys)

    result = []
    for key, column in attribute_keys.iteritems():
        if not column.mutable:
            result.append(key)

    return result

def get_config_data(data):
    # all PUT/POST data should be enclosed in { 'configuration' : { DATA } } JSON
    if OVSDB_SCHEMA_CONFIG not in data:
        app_log.debug("JSON is missing configuration data")
        error_json = to_json_error("Missing %s" % OVSDB_SCHEMA_CONFIG, None, OVSDB_SCHEMA_CONFIG)
        return {ERROR: error_json}

    return data[OVSDB_SCHEMA_CONFIG]
