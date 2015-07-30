import json
import ovs.db.idl
import ovs
import ovs.db.types
import types

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

def uuid_to_uri(uuid_list, uri, key=None):

    uri_list = []
    for item in uuid_list:
        if key:
            uri_list.append(uri + '/' + key + '/' + item)
        else:
            uri_list.append(uri + '/' + item)

    return uri_list

# list of uuids to rows from a table
def uuid_to_row(uuid_list, table):
    row_list = []
    for uuid in uuid_list:
        row_list.append(table.rows[uuid])
    return row_list

# references is a list of references to Row objects
# row/column is the table item to which the references are added
def add_reference_to_table(references, row, column):

    current_references = []
    for item in row.__getattr__(column):
        current_references.append(item)

    # add the new references to the current list
    for item in references:
        current_list.append(item)

    # assign the updated list to the column
    row.__setattr__(column, current_list)
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
