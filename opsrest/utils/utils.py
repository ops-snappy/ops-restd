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

import json
import ovs.db.idl
import ovs
import ovs.db.types as ovs_types
import types
import uuid
import re
import urllib

from opsrest.resource import Resource
from opsrest.constants import *
from tornado.log import app_log


def get_row_from_resource(resource, idl):
    """
    using instance of Resource find the corresponding
    ovs.db.idl.Row instance(s)

    returns an instance of ovs.db.idl.Row or a list of
    ovs.db.idl.Row instances

    Parameters:
        resource - opsrest.resource.Resource instance
        idl - ovs.db.idl.Idl instance
    """

    if not isinstance(resource, Resource):
        return None

    elif resource.table is None or resource.row is None or idl is None:
        return None
    else:
        # resource.row can be a single UUID object or a list of UUID objects
        rows = resource.row
        if type(rows) is not types.ListType:
            return idl.tables[resource.table].rows[resource.row]
        else:
            rowlist = []
            for row in rows:
                rowlist.append(idl.tables[resource.table].rows[row])
            return rowlist


def get_column_data_from_resource(resource, idl):
    """
    return column data
    Parameters:
        resource - opsrest.resource.Resource instance
        idl - ovs.db.idl.Idl instance
    """
    if (resource.table is None or resource.row is None or
            resource.column is None or idl is None):
        return None

    row = idl.tables[resource.table].rows[resource.row]

    if type(resource.column) is types.StringType:
        return row.__getattr__(resource.column)
    elif type(resource.column) is types.ListType:
        columns = []
        for item in resource.column:
            columns.append(row.__getattr__(item))
        return columns
    else:
        return None


def get_column_data_from_row(row, column):
    """
    return column data from row
    Parameters:
        row - ovs.db.idl.Row instance
        column - column name
    """
    if type(str(column)) is types.StringType:
        return row.__getattr__(column)
    elif type(column) is types.ListType:
        columns = []
        for item in column:
            columns.append(row.__getattr__(item))
        return columns
    else:
        return None


def check_resource(resource, idl):
    """
    using Resource and Idl instance return a tuple
    containing the corresponding ovs.db.idl.Row
    and column name

    Parameters:
        resource - opsrest.resource.Resource instance
        idl - ovs.db.idl.Idl instance
    """

    if not isinstance(resource, Resource):
        return None
    elif (resource.table is None or resource.row is None or
            resource.column is None):
        return None
    else:
        return (get_row_from_resource(resource, idl), resource.column)


def add_kv_reference(key, reference, resource, idl):
    """
    Adds a KV type Row reference to a column entry in the DB
    Parameters:
        key - a unique key identifier
        reference - Row reference to be added
        resource - opsrest.resource.Resource instance
                   to which (key:reference) is added
        idl - ovs.db.idl.Idl instance
    """
    row = idl.tables[resource.table].rows[resource.row]
    kv_references = get_column_data_from_row(row, resource.column)

    updated_kv_references = {}
    for k, v in kv_references.iteritems():
        updated_kv_references[k] = v

    updated_kv_references[key] = reference
    row.__setattr__(resource.column, updated_kv_references)
    return True


def add_reference(reference, resource, idl):
    """
    Adds a Row reference to a column entry in the DB
    Parameters:
        reference - ovs.db.idl.Row instance
        resource - opsrest.resource.Resource instance
                   that corresponds to an entry in DB
        idl - ovs.db.idl.Idl instance
    """

    (row, column) = check_resource(resource, idl)
    if row is None or column is None:
        return False

    reflist = get_column_data_from_row(row, column)

    # a list of Row elements
    if len(reflist) == 0 or isinstance(reflist[0], ovs.db.idl.Row):
        updated_list = []
        for item in reflist:
            updated_list.append(item)
        updated_list.append(reference)
        row.__setattr__(column, updated_list)
        return True

    # a list-of-list of Row elements
    elif type(reflist[0]) is types.ListType:
        for _reflist in reflist:
            updated_list = []
            for item in _reflist:
                updated_list.append(item)
            updated_list.append(reference)
            row.__setattr__(column, updated_list)
        return True

    return False


def delete_reference(resource, parent, schema, idl):
    """
    Delete a referenced resource from another
    Parameters:
        resource - Resource instance to be deleted
        parent - Resource instance from which resource
                 is deleted
        schema - ovsdb schema object
        idl - ovs.db.idl.Idl instance
    """
    # kv type reference
    ref = None
    if schema.ovs_tables[parent.table].references[parent.column].kv_type:
        app_log.debug('Deleting KV type reference')
        key = resource.index[0]
        parent_row = idl.tables[parent.table].rows[parent.row]
        kv_references = get_column_data_from_row(parent_row, parent.column)
        updated_kv_references = {}
        for k, v in kv_references.iteritems():
            if str(k) == key:
                ref = v
            else:
                updated_kv_references[k] = v

        parent_row.__setattr__(parent.column, updated_kv_references)
    else:
        # normal reference
        app_log.debug('Deleting normal reference')
        ref = get_row_from_resource(resource, idl)
        parent_row = get_row_from_resource(parent, idl)
        reflist = get_column_data_from_row(parent_row, parent.column)

        if reflist is None:
            app_log.debug('reference list is empty')
            return False

        updated_references = []
        for item in reflist:
            if item.uuid != ref.uuid:
                updated_references.append(item)

        parent_row.__setattr__(parent.column, updated_references)

    return ref


def delete_all_references(resource, schema, idl):
    """
    Delete all occurrences of reference for resource
    Parameters:
        resource - resource whose references are to be
                   deleted from the entire DB
        schema - ovsdb schema object
        idl = ovs.db.idl.Idl instance
    """
    row = get_row_from_resource(resource, idl)
    #We get the tables that reference the row to delete table
    tables_reference = schema.references_table_map[resource.table]
    #Get the table name and column list we is referenced
    for table_name, columns_list in tables_reference.iteritems():
        app_log.debug("Table %s" % table_name)
        app_log.debug("Column list %s" % columns_list)
        #Iterate each row to see wich tuple has the reference
        for uuid, row_ref in idl.tables[table_name].rows.iteritems():
            #Iterate over each reference column and check if has the reference
            for column_name in columns_list:
                #get the referenced values
                reflist = get_column_data_from_row(row_ref, column_name)
                if reflist is not None:
                    #delete the reference on that row and column
                    delete_row_reference(reflist, row, row_ref, column_name)


def delete_row_reference(reflist, row, row_ref, column):
    updated_list = []
    for item in reflist:
        if item.uuid != row.uuid:
            updated_list.append(item)
    row_ref.__setattr__(column, updated_list)


# create a new row, populate it with data
def setup_new_row(resource, data, schema, txn, idl):

    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None
    row = txn.insert(idl.tables[resource.table])

    # add config items
    config_keys = schema.ovs_tables[resource.table].config
    set_config_fields(row, data, config_keys)

    # add reference iitems
    reference_keys = schema.ovs_tables[resource.table].references.keys()
    set_reference_items(row, data, reference_keys)

    return row


#Update columns from a row
def update_row(resource, data, schema, txn, idl):
    #Verify if is a Resource instance
    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None

    #get the row that will be modified
    row = get_row_from_resource(resource, idl)

    #Update config items
    config_keys = schema.ovs_tables[resource.table].config
    set_config_fields(row, data, config_keys)

    # add or modify reference items (Overwrite references)
    reference_keys = schema.ovs_tables[resource.table].references.keys()
    set_reference_items(row, data, reference_keys)

    return row


# set each config data on each column
def set_config_fields(row, data, config_keys):
    for key in config_keys:
        if key in data:
            row.__setattr__(key, data[key])


def set_reference_items(row, data, reference_keys):
    """
    set reference/list of references as a column item
    Parameters:
        row - ovs.db.idl.Row object to which references are added
        data - verified data
        reference_keys - reference column names
    """
    for key in reference_keys:
        if key in data:
            app_log.debug("Adding Reference, the key is %s" % key)
            if isinstance(data[key], ovs.db.idl.Row):
                row.__setattr__(key, data[key])
            elif type(data[key]) is types.ListType:
                reflist = []
                for item in data[key]:
                    reflist.append(item)
                row.__setattr__(key, reflist)


def row_to_json(row, column_keys):

    data_json = {}
    for key in column_keys:

        attribute = row.__getattr__(key)
        attribute_type = type(attribute)

        # Convert single element lists to scalar
        # if schema defines a max of 1 element
        if attribute_type is list and column_keys[key].n_max == 1:
            if len(attribute) > 0:
                attribute = attribute[0]
            else:
                attribute = get_empty_by_basic_type(column_keys[key].type)

        value_type = column_keys[key].type
        if attribute_type is dict:
            value_type = column_keys[key].value_type

        data_json[key] = to_json(attribute, value_type)

    return data_json


def get_empty_by_basic_type(data):
    type_ = type(data)

    # If data is already a type, just use it
    if type_ is type:
        type_ = data
    elif type_ is ovs_types.AtomicType:
        type_ = data

    if type_ is types.DictType:
        return {}

    elif type_ is types.ListType:
        return []

    elif type_ in ovs_types.StringType.python_types or \
            type_ is ovs_types.StringType:
        return ''

    elif type_ in ovs_types.IntegerType.python_types or \
            type_ is ovs_types.IntegerType:
        return 0

    elif type_ in ovs_types.RealType.python_types or \
            type_ is ovs_types.RealType:
        return 0.0

    elif type_ is types.BooleanType or \
            type_ is ovs_types.BooleanType:
        return False

    elif type_ is types.NoneType:
        return None

    else:
        return ''


def to_json(data, value_type=None):
    type_ = type(data)

    if type_ is types.DictType:
        return dict_to_json(data, value_type)

    elif type_ is types.ListType:
        return list_to_json(data, value_type)

    elif type_ in ovs_types.StringType.python_types:
        return str(data)

    elif (type_ in ovs_types.IntegerType.python_types or
            type_ in ovs_types.RealType.python_types):
        return data

    elif type_ is types.BooleanType:
        return data

    elif type_ is types.NoneType:
        return get_empty_by_basic_type(value_type)

    elif type_ is uuid.UUID:
        return str(data)

    elif type_ is ovs.db.idl.Row:
        return str(data.uuid)

    else:
        return str(data)


def has_column_changed(json_data, data):
    json_type_ = type(json_data)
    type_ = type(data)

    if json_type_ != type_:
        return False

    if (type_ is types.DictType or
            type_ is types.ListType or
            type_ is types.NoneType or
            type_ is types.BooleanType or
            type_ in ovs_types.IntegerType.python_types or
            type_ in ovs_types.RealType.python_types):
        return json_data == data

    else:
        return json_data == str(data)


def to_json_error(message, code=None, fields=None):
    dictionary = {"code": code, "fields": fields, "message": message}

    return dict_to_json(dictionary)


def dict_to_json(data, value_type=None):
    if not data:
        return data

    data_json = {}
    for key, value in data.iteritems():
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json[key] = str(value.uuid)

        elif value is None:
            data_json[key] = get_empty_by_basic_type(value_type)

        elif (type_ in ovs_types.IntegerType.python_types or
                type_ in ovs_types.RealType.python_types):
            data_json[key] = value

        else:
            data_json[key] = str(value)

    return data_json


def list_to_json(data, value_type=None):
    if not data:
        return data

    data_json = []
    for value in data:
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json.append(str(value.uuid))

        elif (type_ in ovs_types.IntegerType.python_types or
                type_ in ovs_types.RealType.python_types):
            data_json.append(value)

        elif value is None:
            data_json.append(get_empty_by_basic_type(value_type))

        else:
            data_json.append(str(value))

    return data_json


def index_to_row(index_values, table_schema, dbtable):
    """
    This subroutine fetches the row reference using index_values.
    index_values is a list which contains the combination indices
    that are used to identify a resource.
    """
    indexes = table_schema.indexes
    if len(index_values) != len(indexes):
        return None

    for row in dbtable.rows.itervalues():
        i = 0
        for index, value in zip(indexes, index_values):
            if index == 'uuid':
                if str(row.uuid) != value:
                    break
            elif str(row.__getattr__(index)) != value:
                break

            # matched index
            i += 1

        if i == len(indexes):
            return row

    return None


def kv_index_to_row(index_values, parent, idl):
    """
    This subroutine fetches the row reference using the index as key.
    Current feature uses a single index and not a combination of multiple
    indices. This is used for the new key/uuid type forward references
    introduced for BGP
    """
    index = index_values[0]
    column = parent.column
    row = idl.tables[parent.table].rows[parent.row]

    column_item = row.__getattr__(parent.column)
    for key, value in column_item.iteritems():
        if str(key) == index:
            return value

    return None


def row_to_index(row, table, restschema, idl, parent_row=None):

    index = None
    schema = restschema.ovs_tables[table]
    indexes = schema.indexes

    # if index is just UUID
    if len(indexes) == 1 and indexes[0] == 'uuid':

        if schema.parent is not None:
            parent = schema.parent
            parent_schema = restschema.ovs_tables[parent]

            # check in parent if a child 'column' exists
            column_name = schema.plural_name
            if column_name in parent_schema.references:
                # look in all resources
                parent_rows = None
                if parent_row is not None:
                    # TODO: check if this row exists in parent table
                    parent_rows = [parent_row]
                else:
                    parent_rows = idl.tables[parent].rows

                for item in parent_rows.itervalues():
                    column_data = item.__getattr__(column_name)

                    if isinstance(column_data, types.ListType):
                        for ref in column_data:
                            if ref.uuid == row:
                                index = str(row.uuid)
                                break
                    elif isinstance(column_data, types.DictType):
                        for key, value in column_data.iteritems():
                            if value == row:
                                # found the index
                                index = key
                                break

                    if index is not None:
                        break
        else:
            index = str(row.uuid)
    else:
        tmp = []
        for item in indexes:
            tmp.append(urllib.quote(str(row.__getattr__(item)), safe=''))
        index = '/'.join(tmp)

    return index

'''
# Old code
def escaped_split(s_in):
    strings = re.split(r'(?<!\\)/', s_in)
    res_strings = []

    for s in strings:
        s = s.replace('\\/', '/')
        res_strings.append(s)

    return res_strings
'''


def escaped_split(s_in):
    s_in = s_in.split('/')
    s_in = [urllib.unquote(i) for i in s_in if i != '']
    return s_in


def get_reference_parent_uri(table_name, row, schema, idl):
    uri = ''
    path = get_parent_trace(table_name, row, schema, idl)
    #Don't include Open_vSwitch table
    for table_name, indexes in path[1:]:
        plural_name = schema.ovs_tables[table_name].plural_name
        uri += str(plural_name) + '/' + "/".join(indexes) + '/'
    app_log.debug("Reference uri %s" % uri)
    return uri


def get_parent_trace(table_name, row, schema, idl):
    """
    Get the parent trace to one row
    Returns (table, index) list
    """
    table = schema.ovs_tables[table_name]
    path = []
    while table.parent is not None and row is not None:
        parent_table = schema.ovs_tables[table.parent]
        column = get_parent_column_ref(parent_table.name, table.name, schema)
        row = get_parent_row(parent_table.name, row, column, schema, idl)
        key_list = get_table_key(row, parent_table.name, schema, idl)
        table_path = (parent_table.name, key_list)
        path.insert(0, table_path)
        table = parent_table
    return path


def get_parent_column_ref(table_name, table_ref, schema):
    """
    Get column name where the child table is being referenced
    Returns column name
    """
    table = schema.ovs_tables[table_name]
    for column_name, reference in table.references.iteritems():
        if reference.ref_table == table_ref and reference.relation == 'child':
            return column_name


def get_parent_row(table_name, child_row, column, schema, idl):
    """
    Get the row where the item is being referenced
    Returns idl.Row object
    """
    table = schema.ovs_tables[table_name]
    for uuid, row_ref in idl.tables[table_name].rows.iteritems():
        reflist = get_column_data_from_row(row_ref, column)
        for value in reflist:
            if table.references[column].kv_type:
                db_col = row_ref.__getattr__(column)
                row_value = db_col[value]
                if row_value.uuid == child_row.uuid:
                    return row_ref, value
            else:
                if value.uuid == child_row.uuid:
                    return row_ref


def get_table_key(row, table_name, schema, idl):
    """
    Get the row index
    Return the row index
    """
    key_list = []
    table = schema.ovs_tables[table_name]

    # Verify if is kv reference
    if table.parent:
        parent_table = schema.ovs_tables[table.parent]
        column_ref = get_parent_column_ref(parent_table.name, table.name,
                                           schema)
        if parent_table.references[column_ref].kv_type:
            parent_row, key = get_parent_row(parent_table.name,
                                             row, column_ref, schema, idl)
            key_list.append(str(key))
            return key_list

    # If not is a kv_reference return the index
    indexes = table.indexes
    for index in indexes:
        if index == 'uuid':
            key_list.append(str(row.uuid))
        else:
            value = urllib.quote(str(row.__getattr__(index)), safe='')
            key_list.append(value)

    return key_list
