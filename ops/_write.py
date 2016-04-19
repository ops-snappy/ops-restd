#  Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import types

import ops.utils
import ops.constants
import urllib


global_ref_list = {}

# FIXME: ideally this info should come from extschema
def is_immutable_table(table, extschema):
    default_tables = ['Bridge', 'VRF']
    if extschema.ovs_tables[table].mutable and table not in default_tables:
        return False
    return True


def _delete(row, table, extschema, idl, txn):
    for key in extschema.ovs_tables[table].children:
        if key in extschema.ovs_tables[table].references:
            child_table_name = extschema.ovs_tables[table].references[key].ref_table
            child_ref_list = row.__getattr__(key)
            if isinstance(child_ref_list, types.DictType):
                child_ref_list = child_ref_list.values()
            if child_ref_list:
                child_uuid_list = []
                for item in child_ref_list:
                    child_uuid_list.append(item.uuid)
                while child_uuid_list:
                    child = idl.tables[child_table_name].rows[child_uuid_list[0]]
                    _delete(child, child_table_name, extschema, idl, txn)
                    child_uuid_list.pop(0)
    row.delete()


def setup_table(table_name, data, extschema, idl, txn):

    # table is missing from config json
    if table_name not in data:
        if not is_immutable_table(table_name, extschema):
            # if mutable, empty table
            table_rows = idl.tables[table_name].rows.values()
            while table_rows:
                _delete(table_rows[0], table_name, extschema, idl, txn)
                table_rows = idl.tables[table_name].rows.values()
        return
    else:
        # update table
        tabledata = data[table_name]
        for rowindex, rowdata in tabledata.iteritems():
            setup_row({rowindex:rowdata}, table_name, extschema, idl, txn)


def setup_references(table, data, extschema, idl):
    if table not in data:
        return

    tabledata = data[table]

    for rowindex, rowdata in tabledata.iteritems():
        setup_row_references({rowindex:rowdata}, table, extschema, idl)


def setup_row_references(rowdata, table, extschema, idl):
    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = extschema.ovs_tables[table]

    row = ops.utils.index_to_row(row_index, table_schema, idl)

    if row is None and table in global_ref_list:
        if row_index in global_ref_list[table]:
            row = global_ref_list[table][row_index]
        else:
            raise Exception('reference not found')

    # set references for this row
    for name, column in table_schema.references.iteritems():

        if name in table_schema.children or column.relation == ops.constants.OVSDB_SCHEMA_PARENT:
            continue

        if name not in row_data:
            row.__setattr__(name, [])
        else:
            reflist = []
            reftable = column.ref_table
            refidl = idl.tables[reftable]
            refschema = extschema.ovs_tables[reftable]
            for refindex in row_data[name]:
                refrow = ops.utils.index_to_row(refindex, refschema, idl)
                if refrow is None and reftable in global_ref_list:
                    if refindex in global_ref_list[reftable]:
                        refrow = global_ref_list[reftable][refindex]
                    else:
                        raise Exception('reference not found')
                reflist.append(refrow)

            row.__setattr__(name, reflist)


    for child in table_schema.children:

        # check if child data exists
        if child not in row_data:
            continue
        # get the child table name
        child_data = row_data[child]
        child_table = None
        if child in table_schema.references:
            child_table = table_schema.references[child].ref_table
        else:
            child_table = child

        for index, data in child_data.iteritems():
            if child_table in extschema.ovs_tables[table].children and\
                    child_table not in extschema.ovs_tables[table].references:
                        index = str(row.uuid) + '/' + index
            setup_row_references({index:data}, child_table, extschema, idl)


def setup_row(rowdata, table_name, extschema, idl, txn):
    """
    set up rows recursively
    """
    row_index = rowdata.keys()[0]
    row_data = rowdata.values()[0]
    table_schema = extschema.ovs_tables[table_name]

    # get row reference from table
    _new = False
    row = ops.utils.index_to_row(row_index, table_schema, idl)
    if row is None:
        # do not add row to an immutable table
        if is_immutable_table(table_name, extschema):
            return (None, None)

        row = txn.insert(idl.tables[table_name])
        _new = True

        if table_name not in global_ref_list:
            global_ref_list[table_name] = {}
        global_ref_list[table_name][row_index] = row
    # NOTE: populate configuration data
    config_keys = table_schema.config.keys()
    for key in config_keys:

        # TODO: return error if trying to set an immutable column
        # skip if trying to set an immutable column for an existing row
        if not _new and not table_schema.config[key].mutable:
            continue

        if key not in row_data:
            # skip if it's a new row
            if _new or row.__getattr__(key) is None:
                continue
            else:
                # set the right empty value
                value =  ops.utils.get_empty_by_basic_type(row.__getattr__(key))
        else:
            value = row_data[key]

        row.__setattr__(key, value)

    # NOTE: populate non-config index columns
    if _new:
        for key in table_schema.indexes:
            if key is 'uuid':
                continue

            if key not in table_schema.config.keys() and key in row_data:
                row.__setattr__(key, row_data[key])

    # NOTE: set up child references
    for key in table_schema.children:

        # NOTE: 'forward' type children
        if key in table_schema.references:

            child_table_name = table_schema.references[key].ref_table

            # set up empty reference list if table entry is missing
            # Do this only for mutable tables
            if key not in row_data or not row_data[key]:
                if is_immutable_table(child_table_name, extschema):
                    if _new or row.__getattr__(key) is None:
                        continue
                    else:
                       value = ops.utils.get_empty_by_basic_type(row.__getattr__(key))
                    # set only if its immutable child table
                    if not is_immutable_table(table_name, extschema):
                        row.__setattr__(key, value)
            else:
                new_data = row_data[key]

                # {key:UUID} type of reference check
                kv_type = table_schema.references[key].kv_type

                # if not a new row, delete non-existent child references
                if not _new:
                    current_list = row.__getattr__(key)
                    if current_list:
                        if kv_type:
                            current_list = current_list.values()
                        delete_list = []
                        for item in current_list:
                            index = ops.utils.row_to_index(item, child_table_name, extschema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                        if not is_immutable_table(child_table_name, extschema):
                            while delete_list:
                                _delete(delete_list[0], child_table_name, extschema, idl, txn)
                                delete_list.pop(0)

                # setup children
                children = {}
                for index, child_data in new_data.iteritems():
                    (_child, is_new) = setup_row({index:child_data}, child_table_name, extschema, idl, txn)
                    # NOTE: None is returned when attempting to add a new row in an immutable table
                    if _child is None:
                        continue

                    children.update(_child)

                # NOTE: If the child table doesn't have indexes, replace json index
                # with row.uuid
                if not extschema.ovs_tables[child_table_name].index_columns:
                    for k,v in children.iteritems():
                        new_data[v.uuid] = new_data[k]
                        del new_data[k]

                if kv_type:
                    if table_schema.references[key].kv_key_type.name == 'integer':
                        tmp = {}
                        for k,v in children.iteritems():
                            tmp[int(k)] = v
                        children = tmp
                    row.__setattr__(key, children)
                else:
                    row.__setattr__(key, children.values())

        # Backward reference
        else:

            # get list of all 'backward' references
            column_name = None
            for x, y in extschema.ovs_tables[key].references.iteritems():
                if y.relation == ops.constants.OVSDB_SCHEMA_PARENT:
                    column_name = x
                    break

            # delete non-existent rows

            # get list of all rows with same parent
            if not _new:
                current_list = []
                for item in idl.tables[key].rows.itervalues():
                    parent = item.__getattr__(column_name)
                    if parent.uuid == row.uuid:
                        current_list.append(item)

                new_data = None
                if key in row_data:
                    new_data = row_data[key]

                if current_list:
                    delete_list = []
                    if new_data is None:
                        delete_list = current_list
                    else:
                        for item in current_list:
                            index = ops.utils.row_to_index(item,key, extschema, idl)
                            if index not in new_data:
                                delete_list.append(item)

                    # NOTE: delete only from immutable table
                    if not is_immutable_table(key, extschema):
                        while delete_list:
                            _delete(delete_list[0], key, extschema, idl, txn)
                            delete_list.pop(0)

                # set up children rows
                if new_data is not None:
                    for x,y in new_data.iteritems():
                        # NOTE: adding parent UUID to index
                        split_x = ops.utils.unquote_split(x)
                        split_x.insert(extschema.ovs_tables[key].index_columns.index(column_name),str(row.uuid))
                        tmp = []
                        for _x in split_x:
                            tmp.append(urllib.quote(str(_x), safe=''))
                        x = '/'.join(tmp)
                        (child, is_new) = setup_row({x:y}, key, extschema, idl, txn)

                        # fill the parent reference column
                        if child is not None and is_new:
                            child.values()[0].__setattr__(column_name, row)

    return ({row_index:row}, _new)
