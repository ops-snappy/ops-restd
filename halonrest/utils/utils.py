import json
import ovs.db.idl
import ovs
import ovs.db.types
import types
import uuid

from halonrest.resource import Resource
from halonrest.constants import *


# get a row from a resource
def get_row(resource, idl=None):

    if isinstance(resource, ovs.db.idl.Row):
        return resource

    elif isinstance(resource, Resource):
        if resource.table is None or resource.row is None or idl is None:
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

    return None

# get column item from a row or resource
def get_column(resource, column=None, idl=None):

    if isinstance(resource, ovs.db.idl.Row):
        if column is None:
            return None
        else:
            return resource.__getattr__(column)

    elif isinstance(resource, Resource):
        if resource.table is None or resource.row is None or resource.column is None or idl is None:
            return None
        else:
            row = idl.tables[resource.table].rows[resource.row]
            return row.__getattr__(resource.column)

    return None

# returns ovs.db.idl.Row object
def check_reference(reference, idl=None):

    if isinstance(reference, Resource):
        if reference.table is None or reference.row is None or idl is None:
            return None
        else:
            ref = get_row(reference, idl)
            return ref

    elif isinstance(reference, ovs.db.idl.Row):
        return reference

    return None

# returns a tuple of consisting of (ovs.db.idl.Row, column)
def check_resource(resource, column=None, idl=None):

    if isinstance(resource, Resource):
        if resource.table is None or resource.row is None or resource.column is None: # or idl is None:
            return None
        else:
            return (get_row(resource, idl), resource.column)

    elif isinstance(resource, ovs.db.idl.Row):
        if column is None:
            return False
        else:
            return (resource, column)

    return None

# add a Row reference to a Resource
def add_reference(reference, resource, column=None, idl=None):

    ref = check_reference(reference, idl)
    if ref is None:
        return False

    (row, column) = check_resource(resource, column, idl)
    if row is None or column is None:
        return False

    reflist = get_column(row, column)

    updated_list = []
    for item in reflist:
        updated_list.append(item)
    updated_list.append(ref)

    row.__setattr__(column, updated_list)
    return True

# delete a Row reference from a Resource
def delete_reference(reference, resource, column=None, idl=None):

    ref = check_reference(reference, idl)
    if ref is None:
        return False

    (row, column) = check_resource(resource, column, idl)
    if row is None or column is None:
        return False

    reflist = get_column(row, column, idl)
    if reflist is None:
        return False

    updated_list = []
    for item in reflist:
        if item.uuid != ref.uuid:
            updated_list.append(item)

    row.__setattr__(column, updated_list)
    return True

# create a new row, populate it with data
def setup_new_row(resource, data, schema, txn, idl):

    if not isinstance(resource, Resource):
        return None

    if resource.table is None:
        return None
    row = txn.insert(idl.tables[resource.table])

    # add config items
    config_keys = schema.ovs_tables[resource.table].config
    for key in config_keys:
        if key in data:
            row.__setattr__(key, data[key])

    # add reference items
    reference_keys = schema.ovs_tables[resource.table].references.keys()
    for key in reference_keys:
        if key in data:
            reflist = []
            for item in data[key]:
                # item is of type Resource
                reflist.append(get_row(item, idl))
            row.__setattr__(key, reflist)
    return row

def row_to_json(row, column_keys):

    data_json = {}
    for key in column_keys:
        data_json[key] = to_json(row.__getattr__(key))

    return data_json

def to_json(data):
    type_ = type(data)

    if type_ is types.DictType:
        return dict_to_json(data)

    elif type_ is types.ListType:
        return list_to_json(data)

    elif type_ is types.UnicodeType:
        return str(data)

    elif type_ is types.BooleanType:
        return json.dumps(data)

    elif type_ is types.NoneType:
        return data

    elif type_ is uuid.UUID:
        return str(data)

    elif type_ is ovs.db.idl.Row:
        return str(data.uuid)

    else:
        return str(data)

def dict_to_json(data):
    if not data:
        return data

    data_json = {}
    for key,value in data.iteritems():
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json[key] = str(value.uuid)
        else:
            data_json[key] = str(value)

    return data_json

def list_to_json(data):
    if not data:
        return data

    data_json = []
    for value in data:
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            data_json.append(str(value.uuid))
        else:
            data_json.append(str(value))

    return data_json

def index_to_row(index_values, table_schema, dbtable):

    indexes = table_schema.indexes

    if len(index_values) != len(indexes):
        return None

    for row in dbtable.rows.itervalues():
        i = 0
        for index, value in zip(indexes, index_values):
            if str(row.__getattr__(index)) != value:
                break
            i+=1

        if i == len(indexes):
            return row

    return None
