import json
import ovs.db.idl
import ovs
import ovs.db.types
import types

def row_to_json(row, column_keys, uri=None):

    data_json = {}
    for key in column_keys:
        data_json[key] = to_json(row.__getattr__(key), uri)

    return data_json

def to_json(data, uri=None):
    type_ = type(data)

    if type_ is types.DictType:
        return dict_to_json(data)

    elif type_ is types.ListType:
        return list_to_json(data, uri)

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

def list_to_json(data, uri=None):
    if not data:
        return data

    data_json = []
    for value in data:
        type_ = type(value)

        if isinstance(value, ovs.db.idl.Row):
            if uri:
                data_json.append(uri + '/' + str(value.uuid))
            else:
                data_json.append(str(value.uuid))
        else:
            data_json.append(str(value))

    return data_json
