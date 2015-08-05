import json
import ovs.db.idl
import ovs
import ovs.db.types
import types
import uuid

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

def uuid_to_index(uuid, index, table):

    if type(uuid) is not types.ListType:
        return str(table.rows[ovs.ovsuuid.from_string(uuid)].__getattr__(index))

    else:
        index_list = []
        for item in uuid:
            index_list.append(str(table.rows[ovs.ovsuuid.from_string(item)].__getattr__(index)))
        return index_list

def index_to_uri(index, uri):

    if type(index) is not types.ListType:
        return uri + '/' + index

    else:
        uri_list = []
        for i in index:
            uri_list.append(uri+'/'+i)
        return uri_list

# references is a list of references to Row objects
# row/column is the table item to which the references are added
def add_reference_to_table(references, row, column):

    current_references = []
    for item in row.__getattr__(column):
        current_references.append(item)

    # add the new references to the current list
    for item in references:
        current_references.append(item)

    # assign the updated list to the column
    row.__setattr__(column, current_references)
    return

# Populates the new row object with 'validated' data
def populate_row(row, data, schema, columns):
    for key in columns:
        if key in data:
            if key in schema.references:
                add_reference()
            else:
                row.__setattr__(key, data[key])
    return
