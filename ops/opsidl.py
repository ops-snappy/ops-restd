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


from ovs.db.idl import Idl, Row
import ovs

class OpsIdl(Idl):
    """
    OpsIdl inherits from Class Idl. The index to row mapping feature
    is used in order to improve dc write time by doing the lookup from
    the index_map.

    """
    def __init__(self, remote, schema):
        Idl.__init__(self, remote, schema)
        for table in self.tables.itervalues():
            table.index_map = {}

    def _Idl__clear(self):
        changed = False

        for table in self.tables.itervalues():
            if table.rows:
                changed = True
                table.rows = {}
                table.index_map = {}

        if changed:
            self.change_seqno += 1

    # Overriding parent process_update
    def _Idl__process_update(self, table, uuid, old, new):
        """Returns True if a column changed, False otherwise."""
        row = table.rows.get(uuid)
        changed = False
        if not new:
            # Delete row.
            if row:
                self._update_index_map(row, table, ovs.db.idl.ROW_DELETE)
                del table.rows[uuid]
                changed = True
                self.notify(ovs.db.idl.ROW_DELETE, row)
            else:
                # XXX rate-limit
                vlog.warn("cannot delete missing row %s from table %s"
                          % (uuid, table.name))
        elif not old:
            # Insert row.
            if not row:
                row = self._Idl__create_row(table, uuid)
                changed = True
            else:
                # XXX rate-limit
                vlog.warn("cannot add existing row %s to table %s"
                          % (uuid, table.name))
            if self._Idl__row_update(table, row, new):
                changed = True
                self.notify(ovs.db.idl.ROW_CREATE, row)

            self._update_index_map(row, table, ovs.db.idl.ROW_CREATE, new)
        else:
            op = ovs.db.idl.ROW_UPDATE
            if not row:
                row = self._Idl__create_row(table, uuid)
                changed = True
                op = ovs.db.idl.ROW_CREATE
                # XXX rate-limit
                vlog.warn("cannot modify missing row %s in table %s"
                          % (uuid, table.name))
            if self._Idl__row_update(table, row, new):
                changed = True
                self.notify(op, row, Row.from_json(self, table, uuid, old))

            if op == ovs.db.idl.ROW_CREATE:
                self._update_index_map(row, table, ovs.db.idl.ROW_CREATE, new)

        return changed

    def _update_index_map(self, row, table, operation, new=None):

        if operation == ovs.db.idl.ROW_DELETE:
            index = self._row_to_index_lookup(row, table)
            if index in table.index_map:
                del table.index_map[index]

        elif operation == ovs.db.idl.ROW_CREATE:
            if table.indexes:
                index_values = []
                for v in table.indexes[0]:
                    if v.name in row._data:
                        column = table.columns.get(v.name)
                        if column.type.key.type == ovs.db.types.UuidType:
                            val = new[v.name][1]
                        else:
                            val = row.__getattr__(v.name)
                        val = str(val)
                        index_values.append(val)
                table.index_map[tuple(index_values)] = row

    def index_to_row_lookup(self, index, table_name):
        """
        This subroutine fetches the row reference using index_values.
        index_values is a list which contains the combination indices
        that are used to identify a resource.
        """
        table = self.tables.get(table_name)
        index = tuple([str(item) for item in index])
        if index in table.index_map:
            return table.index_map[index]

        return None

    def _row_to_index_lookup(self, row, table):
        # Given the row return the index
        index_values = []
        if not table.indexes:
            return None
        for v in table.indexes[0]:
            val = row.__getattr__(v.name)
            if isinstance(val, Row):
                val = val.uuid
            val = str(val)
            index_values.append(val)
        return tuple(index_values)
