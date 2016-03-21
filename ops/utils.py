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

import ovs
import urllib
import types
import uuid

import ovs.db.types as ovs_types


def escaped_split(s_in):
    s_in = s_in.split('/')
    s_in = [urllib.unquote(i) for i in s_in if i != '']
    return s_in


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


def index_to_row(index, table_schema, dbtable):
    """
    This subroutine fetches the row reference using index.
    index is either of type uuid.UUID or is a uri escaped string which contains
    the combination indices that are used to identify a resource.
    """
    table = table_schema.name
    if isinstance(index, uuid.UUID):
        # index is of type UUID
        if index in dbtable.rows:
            return dbtable.rows[index]
        else:
            raise Exception("""resource with UUID %(i) not found
                            in table %(j)
                            """ % {"i":str(index), "j":table})
    else:
        # index is an escaped combine indices string
        index_values = escaped_split(index)
        indexes = table_schema.indexes

        # if table has no indexes, we create a new entry
        if not table_schema.index_columns:
            return None

        if len(index_values) != len(indexes):
            raise Exception('Combination index error for table %s' % table)

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
