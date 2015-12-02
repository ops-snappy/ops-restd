#!/usr/bin/env python
#
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from opsrest.utils import utils
from opsrest import resource
from opslib import restparser
import declarativeconfig
import ovs
import json
import sys
import time
import traceback

import ovs.db.idl
import ovs.db.types
import types
import uuid

# immutable tables cannot have any additions or deletions
immutable_tables = ['Fan', 'Power_supply', 'LED', 'Temp_sensor',
                    'System', 'Subsystem', 'VRF']


class RunConfigUtil():
    def __init__(self, idl, restschema):
        self.idl = idl
        self.restschema = restschema

    def get_running_config(self):
        return declarativeconfig.read(self.restschema, self.idl)

    # WRITE CONFIG

    # this relies already on the references/children being
    #marked as configurable or not
    def is_table_configurable(self, table_name):
        if len(self.restschema.ovs_tables[table_name].config.keys()) > 0:
            return True
        # references
        i_ = self.restschema.ovs_tables[table_name].references
        for column_name, column in i_.iteritems():
            if column.relation == 'reference':
                return True
        # children
        for column_name in self.restschema.ovs_tables[table_name].children:
            references_ = self.restschema.ovs_tables[table_name].references
            if column_name not in references_:
                child_table = column_name
            else:
                child_table = self.restschema.ovs_tables[table_name].\
                    references[column_name].ref_table
            if is_table_configurable(child_table):
                return True

        return False

    def setup_row(self, index_values, table, row_data,
                  txn, reflist, parent=None, old_row=None):

        # find out if this row exists
        # If table is System, return first row from table
        if table == 'System':
            row = self.idl.tables[table].rows.values()[0]
        else:
            if old_row is not None:
                row = old_row
            else:
                row = utils.index_to_row(index_values,
                                     self.restschema.ovs_tables[table],
                                     self.idl.tables[table])

        is_new = False
        if row is None:
            if table in immutable_tables:
                # Adding a row to an immutable table is ignored
                return (None, False)
            row = txn.insert(self.idl.tables[table])
            is_new = True

        # we have the row. update the data

        # Routes are special case - only static routes can be updated
        if table == 'Route':
            if not is_new and row.__getattr__('from') != 'static':
                return (None, False)
            elif is_new:
                row.__setattr__('from', 'static')

        config_rows = self.restschema.ovs_tables[table].config
        config_keys = self.restschema.ovs_tables[table].config.keys()

        for key in config_rows.keys():
            if not is_new and not config_rows[key].mutable:
                continue

            if key not in row_data and not is_new:
                empty_val = utils.get_empty_by_basic_type(row.__getattr__(key))
                row.__setattr__(key, empty_val)
            elif (key in row_data and
                    (is_new or row.__getattr__(key) != row_data[key])):
                row.__setattr__(key, row_data[key])

        references = self.restschema.ovs_tables[table].references
        children = self.restschema.ovs_tables[table].children

        # delete all the keys that don't exist
        for key in children:
            child_table = references[key].ref_table \
                if key in references else key

            if child_table in immutable_tables:
                if (key not in row_data or not row_data[key]):
                    # Deep cleanup children, even if missing or empty,
                    #if can't delete because immutable
                    if key in references:
                        kv_type = references[key].kv_type
                        if kv_type:
                            rowlist = row.__getattr__(key).values()
                        else:
                            rowlist = row.__getattr__(key)
                        self.clean_subtree(child_table,
                                           rowlist, txn)
                    else:
                        self.clean_subtree(child_table, [], txn, row)
                continue

            # forward child references
            if key in references:
                table_schema = self.restschema.ovs_tables[table]
                reference = table_schema.references[key]
                kv_type = reference.kv_type

                if not is_new and key not in row_data:
                    if kv_type:
                        row.__setattr__(key, {})
                    else:
                        row.__setattr__(key, [])
            else:
                # back-references
                if child_table not in row_data:
                    new_data = {}
                else:
                    new_data = row_data[child_table]
                self.remove_deleted_rows(child_table, new_data, txn, row)

        # set up children that exist
        for key in children:
            child_table = references[key].ref_table \
                if key in references else key

            if key in row_data:

                # forward child references
                if key in references:
                    table_schema = self.restschema.ovs_tables[table]
                    reference = table_schema.references[key]
                    kv_type = reference.kv_type
                    kv_key_type = None
                    current_child_rows = {}

                    if kv_type:
                        kv_key_type = reference.kv_key_type
                        current_child_rows = row.__getattr__(key)
                    child_reference_list = self.setup_table(child_table,
                                                            row_data[key],
                                                            txn, reflist,
                                                            None, kv_type,
                                                            kv_key_type,
                                                            current_child_rows)

                    if child_table not in immutable_tables:
                        row.__setattr__(key, child_reference_list)
                else:
                    self.setup_table(child_table, row_data[key],
                                     txn, reflist, row)

# Looks unnecessary - probably needs to be removed - commenting out for now
# for key,value in references.iteritems():
#     if key in self.restschema.ovs_tables[table].children and key in row_data:
#         child_table = value.ref_table
#
#         # this becomes the new reference list.
#         child_reference_list = self.setup_table(child_table,
#                                                 row_data[key],
#                                                 txn, reflist)
#         if child_table not in immutable_tables:
#             row.__setattr__(key, child_reference_list)

        return (row, is_new)

    def clean_subtree(self, table, entries, txn, parent=None):

        if parent is None:
            for row in entries:
                self.clean_row(table, row, txn)
        else:
            #back references
            if table not in immutable_tables:
                self.remove_deleted_rows(table, {}, txn, parent)
            else:
                parent_column = None
                references_ = self.restschema.ovs_tables[table].references
                for key, value in references_.iteritems():
                    if value.relation == 'parent':
                        parent_column = key
                        break
                for row in self.idl.tables[table].rows.itervalues():
                    if parent_column is not None and \
                       row.__getattr__(parent_column) == parent:
                        self.clean_row(table, row, txn)

    def clean_row(self, table, row, txn):
        references = self.restschema.ovs_tables[table].references
        children = self.restschema.ovs_tables[table].children
        config_rows = self.restschema.ovs_tables[table].config

        # clean children
        for key in children:
            if key in references:
                kv_type = references[key].kv_type
                child_table = references[key].ref_table
                if child_table not in immutable_tables:
                    if kv_type:
                        row.__setattr__(key, {})
                    else:
                        row.__setattr__(key, [])
                else:
                    if kv_type:
                        rowlist = row.__getattr__(key).values()
                    else:
                        rowlist = row.__getattr__(key)
                    self.clean_subtree(child_table, rowlist, txn)
            else:
                child_table = key
                self.clean_subtree(child_table, [], txn, row)

        # clean config fields
        for key in config_rows.keys():
            if not config_rows[key].mutable:
                continue
            empty_val = utils.get_empty_by_basic_type(row.__getattr__(key))
            row.__setattr__(key, empty_val)

        # clean references
        for key, val in references.iteritems():
            if val.relation == 'reference' and val.mutable:
                row.__setattr__(key, [])

    def setup_table(self, table, table_data, txn, reflist, parent=None,
                    kv_type=False, kv_key_type=None, current_rows={}):

        config_keys = self.restschema.ovs_tables[table].config.keys()
        reference_keys = self.restschema.ovs_tables[table].references.keys()

        parent_column = None
        if parent is not None:
            references = self.restschema.ovs_tables[table].references
            for key, value in references.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break

        # iterate over each row
        rows = []
        kv_index_list = []
        for index, row_data in table_data.iteritems():
            current_row = None
            if kv_type:
                if (kv_key_type is not None and
                        kv_key_type.name == 'integer'):
                    index = int(index)
                if index in current_rows:
                    current_row = current_rows[index]
                index_values = []
            else:
                index_values = utils.escaped_split(index)

            (row, isNew) = self.setup_row(index_values,
                                          table,
                                          row_data,
                                          txn,
                                          reflist,
                                          None,
                                          current_row)
            if row is None:
                continue

            # back reference
            if parent_column is not None and isNew:
                row.__setattr__(parent_column, parent)

            rows.append(row)

            if kv_type:
                kv_index_list.append(index)


            # save this in global reflist
            if not kv_type:
                reflist[(table, index)] = (row, isNew)

        if kv_type:
            kv_rows = {}
            for index, row in zip(kv_index_list, rows):
                kv_rows[index] = row
            return kv_rows
        else:
            return rows

    def setup_references(self, table, table_data, txn, reflist):

        references = self.restschema.ovs_tables[table].references

        # iterate over every row of the table
        for index, row_data in table_data.iteritems():

            # fetch the row from the reflist we maintain
            if (table, index) in reflist:
                (row, isNew) = reflist[(table, index)]
            else:
                continue

            for key, value in references.iteritems():
                if value.relation == 'reference':
                    if not value.mutable and not isNew:
                        continue
                    new_reference_list = []
                    if key in row_data:
                        ref_table = value.ref_table
                        for item in row_data[key]:
                            # TODO: missing item/references will throw
                            #an exception
                            if (ref_table, item) not in reflist:
                                continue
                            (ref_row, isNew) = reflist[(ref_table, item)]
                            new_reference_list.append(ref_row)
                    # set row attribute
                    row.__setattr__(key, new_reference_list)

            # do the same for all child tables
            for key in self.restschema.ovs_tables[table].children:
                if key in row_data:
                    if key in references:
                        child_table = references[key].ref_table
                    else:
                        child_table = key
                    self.setup_references(child_table,
                                          row_data[key],
                                          txn,
                                          reflist)

    def remove_deleted_rows(self, table, table_data, txn, parent=None):

        parent_column = None
        if parent is not None:
            references = self.restschema.ovs_tables[table].references
            for key, value in references.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break

        # delete rows from DB that are not in declarative config
        delete_rows = []
        for row in self.idl.tables[table].rows.itervalues():
            index = utils.row_to_index(row, table, self.restschema, self.idl, parent)

            if parent_column is not None and \
               row.__getattr__(parent_column) != parent:
                continue

            # Routes are special case - only static routes can be deleted
            if table == 'Route' and row.__getattr__('from') != 'static':
                continue

            if index not in table_data:
                delete_rows.append(row)

        for i in delete_rows:
            i.delete()

    def remove_orphaned_rows(self, txn):

        for table_name, table_schema in self.restschema.ovs_tables.iteritems():
            if table_schema.parent is None:
                continue

            parent_column = None
            references = table_schema.references
            for key, value in references.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break

            if parent_column is None:
                continue

            # delete orphans
            delete_rows = []
            for row in self.idl.tables[table_name].rows.itervalues():
                parent_row = row.__getattr__(parent_column)
                if parent_row not in self.idl.tables[table_schema.parent].rows:
                    delete_rows.append(row)
            for i in delete_rows:
                i.delete()

    def write_config_to_db(self, data):

        # create a transaction
        txn = ovs.db.idl.Transaction(self.idl)

        # maintain a dict with all index:references
        reflist = {}

        # start with System table
        table_name = 'System'

        # reconstruct System record with correct UUID from the DB
        system_uuid = str(self.idl.tables[table_name].rows.keys()[0])

        self.setup_table(table_name, {system_uuid: data[table_name]},
                         txn, reflist)

        # All other top level tables, according to schema
        for table_name, table_data in self.restschema.ovs_tables.iteritems():

            if table_data.parent is not None:
                continue

            if table_name == 'System':
                continue
            if table_name not in data:
                new_data = {}
            else:
                new_data = data[table_name]

            if table_name not in immutable_tables:
                self.remove_deleted_rows(table_name, new_data, txn)

            self.setup_table(table_name, new_data, txn, reflist)

        # the tables are all set up, now connect the references together
        for table_name, value in data.iteritems():
            if table_name == 'System':
                new_data = {system_uuid: data[table_name]}
            else:
                new_data = data[table_name]
            self.setup_references(table_name, new_data, txn, reflist)

        # remove orphaned rows
        # TODO: FIX THIS and turn on - not critical right away since VRF
        # entry can't be removed
        # self.remove_orphaned_rows(txn)

        # verify txn
        # commit txn
        result = txn.commit_block()
        error = txn.get_error()
        return (result, error)
