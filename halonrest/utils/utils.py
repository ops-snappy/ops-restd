import ovs.db.idl
import json

def read_row(row):
    assert isinstance(row, ovs.db.idl.Row)
    data = {}
    for k,v in row._data.iteritems():
        data[k] = v.to_json()
    return json.dumps(data, ensure_ascii=False)

def read_column_from_row(row, columns):
    assert isinstance(row, ovs.db.idl.Row)
    data = {}
    for k,v in row._data.iteritems():
        if k in columns:
            data[k] = v.to_json()
    return json.dumps(data, ensure_ascii=False)
