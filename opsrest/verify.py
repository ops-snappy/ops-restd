# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

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

    # when adding a child with kv_type of forward referencing,
    # the configuration data must contain the 'keyname' used to
    # identify the reference of the new resource created.
    if resource.relation is OVSDB_SCHEMA_CHILD:
        ref = schema.ovs_tables[resource.table].references[resource.column]
        reference = ref
        if reference.kv_type:
            keyname = reference.column.keyname
            if keyname not in _data:
                error_json = to_json_error("Missing keyname attribute to" +
                                           " reference the new resource" +
                                           " from the parent")
                return {ERROR: error_json}
            else:
                verified_data[keyname] = _data[keyname]
                _data.pop(keyname)

    verified_config_data = verify_config_data(_data,
                                              resource.next,
                                              schema, 'POST')
    if verified_config_data is not None:
        if ERROR in verified_config_data:
            return verified_config_data
        else:
            verified_data.update(verified_config_data)

    verified_reference_data = verify_forward_reference(_data,
                                                       resource.next,
                                                       schema, idl)
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
            error_json = to_json_error("Missing %s"
                                       % OVSDB_SCHEMA_REFERENCED_BY,
                                       None, OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

        _data = data[OVSDB_SCHEMA_REFERENCED_BY]
        try:
            verified_referenced_by_data = verify_referenced_by(_data,
                                                               resource.next,
                                                               schema, idl)
            if ERROR in verified_referenced_by_data:
                return verified_referenced_by_data
            else:
                verified_data.update(verified_referenced_by_data)

        except Exception as e:
            app_log.debug('referenced_by uri verification failed')
            app_log.debug("Reason: %s" % e)
            error_json = to_json_error(str(e), None,
                                       OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        references = schema.ovs_tables[resource.next.table].references
        for key, value in references.iteritems():
            if value.relation == 'parent':
                verified_data.update({key: resource})

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
    verified_config_data = verify_config_data(_data,
                                              resource_verify,
                                              schema, 'PUT')

    if verified_config_data is not None:
        if ERROR in verified_config_data:
            return verified_config_data
        else:
            verified_data.update(verified_config_data)

    verified_reference_data = verify_forward_reference(_data,
                                                       resource_verify,
                                                       schema, idl)
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
            error_json = to_json_error("%s not allowed for PUT"
                                       % OVSDB_SCHEMA_REFERENCED_BY,
                                       None, OVSDB_SCHEMA_REFERENCED_BY)
            return {ERROR: error_json}

    return verified_data


def verify_config_data(data, resource, schema, http_method):
    config_keys = schema.ovs_tables[resource.table].config
    reference_keys = schema.ovs_tables[resource.table].references

    verified_config_data = {}
    error_json = {}

    # Check for extra or unknown attributes
    unknown_attribute = find_unknown_attribute(data,
                                               config_keys,
                                               reference_keys)
    if unknown_attribute is not None:
        error_json = to_json_error("Unknown configuration attribute",
                                   None, unknown_attribute)
        return {ERROR: error_json}

    non_mutable_attributes = get_non_mutable_attributes(resource, schema)

    # Check for all required/valid attributes to be present
    for column_name in config_keys:

        is_optional = config_keys[column_name].is_optional

        if column_name in data:

            check_type_result = verify_attribute_type(column_name,
                                                      config_keys[column_name],
                                                      data[column_name])
            if ERROR in check_type_result:
                return check_type_result

            check_range_result = \
                verify_attribute_range(column_name,
                                       config_keys[column_name],
                                       data[column_name])
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
                if not is_optional:
                    error_json = to_json_error("Attribute is missing from request",
                                               None, column_name)
                    return {ERROR: error_json}

        # Anything else (POST) requires all attributes
        else:
            if not is_optional:
                error_json = to_json_error("Attribute is missing from request",
                                           None, column_name)
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

        # Check each value's type for elements in lists and dictionaries
        if column_data.n_max > 1:
            error_json = verify_container_values_type(column_name, column_data,
                                                      request_data)

        # Now check for invalid values
        if not error_json:
            error_json = verify_valid_attribute_values(data, column_data,
                                                       column_name)

    else:
        error_json = to_json_error("Attribute type mismatch",
                                   None, column_name)

    if error_json:
        result = {ERROR: error_json}

    return result


def verify_container_values_type(column_name, column_data, request_data):

    error_json = {}

    if column_data.is_list:
        for value in request_data:
            if type(value) not in column_data.type.python_types:
                error_json = to_json_error("Value type mismatch in list",
                                           None, column_name)
                break

    elif column_data.is_dict:
        for key, value in request_data.iteritems():

            value_type = type(value)

            # Values in dict must match JSON schema
            if value_type in column_data.value_type.python_types:

                # If they match, they might be strings that represent other
                # types, so each value must be checked if kvs type exists

                if value_type in ovs_types.StringType.python_types \
                        and column_data.kvs:

                    kvs_value_type = column_data.kvs[key]['type']
                    converted_value = \
                        convert_string_to_value_by_type(value, kvs_value_type)

                    if converted_value is None:
                        error_json = \
                            to_json_error("Value type mismatch for key" + \
                                          " '%s'" % key,
                                          None, column_name)
                        break
            else:
                error_json = \
                    to_json_error("Value type mismatch for key '%s'" % key,
                                  None, column_name)
                break

    return error_json

def convert_string_to_value_by_type(value, type_):

    converted_value = value

    if type_ == ovs_types.IntegerType:
        try:
            converted_value = int(value)
        except ValueError, e:
            converted_value = None
    elif type_ == ovs_types.RealType:
        try:
            converted_value = float(value)
        except ValueError, e:
            converted_value = None
    elif type_ == ovs_types.BooleanType:
        if not (value == 'true' or value == 'false'):
            converted_value = None

    return converted_value

def verify_valid_attribute_values(request_data, column_data, column_name):
    valid = True
    error_json = {}
    error_details = ""
    error_message = "Attribute value is invalid"

    # If data has an enum defined, check for a valid value
    if column_data.enum:

        enum = set(column_data.enum.as_list())
        valid = is_value_in_enum(request_data, enum)

    # If data has key-values dict defined, check for missing/invalid keys
    # It's assumed type is validated, meaning kvs is defined for dicts only
    elif column_data.kvs:

        valid_keys = set(column_data.kvs.keys())
        data_keys = set(request_data.keys())

        unknown_keys = data_keys.difference(valid_keys)
        missing_keys = valid_keys.difference(data_keys)

        if unknown_keys:
            error_details += "Unknown keys: '%s'. " % list(unknown_keys)

        if missing_keys:
            true_missing_keys = []

            for key in missing_keys:
                if not column_data.kvs[key]["is_optional"]:
                    true_missing_keys.append(key)

            if true_missing_keys:
                missing_keys = true_missing_keys
                error_details += "Missing keys: '%s'. " % list(missing_keys)
            else:
                missing_keys = []

        if unknown_keys or missing_keys:
            valid = False

        if valid:
            # Now that keys have been checked,
            # verify their values are valid
            for key, value in column_data.kvs.iteritems():
                if key in request_data and value['enum']:
                    enum = set(value['enum'].as_list())

                    data_value = request_data[key]

                    if type(data_value) \
                            in ovs_types.StringType.python_types:
                        data_value = \
                            convert_string_to_value_by_type(data_value,
                                                            value['type'])

                    if not is_value_in_enum(data_value, enum):
                        valid = False
                        error_details += "Invalid value for key '%s'. " % key
                        break

    if not valid:
        if error_details:
            error_message += ": " + error_details
        error_json = to_json_error(error_message,
                                   None, column_name)

    return error_json


def is_value_in_enum(value, enum):

    valid = True

    # Check if request's list contains values not valid
    if type(value) is list:
        if set(value).difference(enum):
            valid = False

    # Check if single request value is valid
    elif value not in enum:
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
            error_json = to_json_error("List's number of elements is " +\
                                       "out of range", None, column_name)
        else:
            for element in request_list:
                # We usually check the value itself
                # But for a string, we check its length instead
                value = element
                if type(element) in ovs_types.StringType.python_types:
                    value = len(element)

                if (value < column_data.rangeMin or
                        value > column_data.rangeMax):
                    error_json = to_json_error("List element '%s'" % element +\
                                               " is out of range",
                                               None, column_name)
                    break

    # Check elements in a dictionary
    elif column_data.is_dict:
        request_len = len(request_data)
        if request_len < column_data.n_min or request_len > column_data.n_max:
            error_json = to_json_error("Dictionary's number of elements " +\
                                       "is out of range", None, column_name)
        else:
            for key, data in request_data.iteritems():

                # First check the key
                # TODO is this necessary? Valid keys are verified prior to this

                value = key
                if type(key) in ovs_types.StringType.python_types:
                    value = len(key)

                if (value < column_data.rangeMin or
                        value > column_data.rangeMax):
                    error_json = to_json_error("Dictionary key '%s'" % key + \
                                               " is out of range",
                                               None, column_name)
                    break

                # Now check ranges for values in dictionary

                # Skip range check for bools
                if type(data) is bool:
                    continue

                value = data

                min_ = column_data.valueRangeMin
                max_ = column_data.valueRangeMax

                # If kvs is defined, ranges shouldbe taken from it
                if column_data.kvs:
                    # Skip range check for booleans
                    if column_data.kvs[key]['type'] == ovs_types.BooleanType:
                        continue
                    else:
                        min_ = column_data.kvs[key]['rangeMin']
                        max_ = column_data.kvs[key]['rangeMax']

                    # If value is a string, it might represent values of other
                    # types and therefore it needs to be converted
                    if type(value) in ovs_types.StringType.python_types:
                        value = \
                            convert_string_to_value_by_type(value,
                                                column_data.kvs[key]['type'])

                # If it was a string all along or if after convertion it's
                # still a string, its length range is checked instead
                if type(value) in ovs_types.StringType.python_types:
                    value = len(value)

                if (value < min_ or
                        value > max_):
                    error_json = to_json_error("Dictionary value '%s'" % data \
                                               + " is out of range for key " \
                                               + "'%s'" % key,
                                               None, column_name)
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
            error_json = to_json_error("Attribute value is out of range",
                                       None, column_name)

    if error_json:
        result = {ERROR: error_json}

    return result


def verify_forward_reference(data, resource, schema, idl):
    """
    converts the forward reference URIs to corresponding Row references
    Parameters:
        data - post/put data
        resource - Resource object being accessed
        schema = restparser schema object
        idl - ovs.db.idl.Idl object
    """
    reference_keys = schema.ovs_tables[resource.table].references
    verified_references = {}

    # check for invalid keys
    for key in reference_keys:
        if key in data:
            category = reference_keys[key].category
            relation = reference_keys[key].relation

            if category != OVSDB_SCHEMA_CONFIG or \
                    relation == 'parent':
                    error_json = to_json_error("Invalid reference %s" \
                            % key, None, key)
                    return {ERROR: error_json}

    for key in reference_keys:
        if key in data:
            # this is either a URI or list of URIs
            _refdata = data[key]
            notList = False
            if type(_refdata) is not types.ListType:
                notList = True
                _refdata = [_refdata]

            # check range
            _min = reference_keys[key].n_min
            _max = reference_keys[key].n_max
            if len(_refdata) < _min or len(_refdata) > _max:
                error_json = to_json_error("Reference list out of " +
                                           "range", None, key)
                return {ERROR: error_json}

            references = []
            for uri in _refdata:
                verified_resource = parse.parse_url_path(uri, schema, idl)
                if verified_resource is None:
                    error_json = to_json_error("Reference could not " +
                                               "be identified", None, uri)
                    return {ERROR: error_json}

                # get the Row instance of the reference we are adding
                while verified_resource.next is not None:
                    verified_resource = verified_resource.next
                row = utils.get_row_from_resource(verified_resource, idl)
                references.append(row)

            if notList:
                references = references[0]
            verified_references[key] = references

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

    verified_referenced_by = {OVSDB_SCHEMA_REFERENCED_BY: []}
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

        # if attribute list has only one element, make it a non-list to keep
        # it consistent with single attribute case (that need not be mentioned)
            if len(attributes) == 1:
                attributes = attributes[0]
        else:
            # find the lone attribute
            _found = False
            for key, value in references.iteritems():
                if value.ref_table == table:
                    if _found:
                        raise Exception('multiple attributes possible,\
                                        specify one')
                    else:
                        _found = True
                        attributes = key

        # found the uri and attributes
        uri_resource.column = attributes
        verified_referenced_by[OVSDB_SCHEMA_REFERENCED_BY].append(uri_resource)

    return verified_referenced_by


def find_unknown_attribute(data, config_keys, reference_keys):

    for column_name in data:
        if not (column_name in config_keys or
                column_name in reference_keys):
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
        error_json = to_json_error("Missing %s" % OVSDB_SCHEMA_CONFIG,
                                   None, OVSDB_SCHEMA_CONFIG)
        return {ERROR: error_json}

    return data[OVSDB_SCHEMA_CONFIG]
