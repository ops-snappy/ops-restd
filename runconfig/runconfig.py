#!/usr/bin/env python

from halonrest.settings import settings
from halonrest.manager import OvsdbConnectionManager
from halonrest.utils import utils
from halonrest import resource
from halonlib import restparser
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
immutable_tables = ['Fan', 'Power_supply', 'LED', 'Temp_sensor', 'Open_vSwitch', 'Subsystem', 'VRF']

class RunConfigUtil():
    def __init__(self, settings):
        manager = OvsdbConnectionManager(settings.get('ovs_remote'), settings.get('ovs_schema'))
        manager.start()
        self.idl = manager.idl

        init_seq_no = 0
        # Wait until the connection is ready
        while True:
            self.idl.run()
            # print self.idl.change_seqno
            if init_seq_no != self.idl.change_seqno:
                break
            time.sleep(1)

        self.restschema = restparser.parseSchema(settings.get('ext_schema'))

    def __init__(self, idl, restschema):
        self.idl = idl
        self.restschema = restschema

# READ CONFIG

    def get_row_data(self, table, row):
        rowobj = {}

        # Routes are special case - only static routes are returned
        if table == 'Route' and row.__getattr__('from') != 'static':
            return

        for column_name, column in table.config.iteritems():
            rowobj[column_name] = utils.to_json(row.__getattr__(column_name))

        for child_name in table.children:

            if child_name in table.references:
                column = table.references[child_name]
                refdata = row.__getattr__(child_name)

                reflist = []
                for i in range(0,len(refdata)):
                    reflist.append(refdata[i].uuid)

                if len(reflist) > 0:
                    tabledata = self.get_table_data(column.ref_table, self.restschema.ovs_tables[column.ref_table], reflist)
                    if len(tabledata) > 0:
                        rowobj[child_name] = tabledata
            else:
                tabledata = self.get_table_data_by_parent(child_name, self.restschema.ovs_tables[child_name], row.uuid)
                if len(tabledata) > 0:
                    rowobj[child_name] = tabledata

        for column_name, column in table.references.iteritems():
            if column.relation != 'reference':
                continue

            refdata = row.__getattr__(column_name)
            # this is a list of references
            reflist = []
            for i in refdata:
                reflist.append(utils.row_to_index(self.restschema.ovs_tables[column.ref_table], i))
            if len(reflist) > 0:
                rowobj[column_name] = reflist

        return rowobj

    def get_table_data_by_parent(self, table_name, schema_table, parent_uuid):

        tableobj = {}
        dbtable = self.idl.tables[table_name]

        # find the parent column
        parent_column = None
        for columnName, column in schema_table.references.iteritems():
            if column.relation == "parent":
                parent_column = columnName
                break

        rows = []
        for row in dbtable.rows.itervalues():
            uuid = row.__getattr__(parent_column).uuid
            if uuid == parent_uuid:
                rowdata = self.get_row_data(schema_table, row)
                if len(rowdata) > 0:
                    tableobj[utils.row_to_index(schema_table, row)] = rowdata

        return tableobj

    def get_table_data(self, table_name, schema_table, uuid_list = None):

        tableobj = {}
        dbtable = self.idl.tables[table_name]

        rows = []
        if uuid_list is not None:
            for uuid in uuid_list:
                rows.append(dbtable.rows[uuid])
        else:
            for item in dbtable.rows.itervalues():
                rows.append(item)

        for item in rows:
            rowdata = self.get_row_data(schema_table, item)
            if len(rowdata) > 0:
                tableobj[utils.row_to_index(schema_table, item)] = rowdata

        return tableobj


    def get_running_config(self):
        try:
            config = {}

            #foreach table in Tables, create uri and add to the data
            for table_name, table in self.restschema.ovs_tables.iteritems():

                # print("Parent  = %s" % table.parent)
                # print("Configuration attributes: ")
                # for column_name, column in table.config.iteritems():
                #     print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
                # print("Status attributes: ")
                # for column_name, column in table.status.iteritems():
                #     print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
                # print("Stats attributes: ")
                # for column_name, column in table.stats.iteritems():
                #     print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
                # print("Subresources: ")
                # for column_name, column in table.references.iteritems():
                #     print("Col name = %s: %s, %s" % (column_name, column.relation, "plural" if column.is_plural else "singular"))
                # print("\n")

                if table.parent is not None:
                    continue
                tabledata = self.get_table_data(table_name, table)

                if len(tabledata) > 0:
                    config[table_name] = tabledata

            return config
        except Exception,e:
            print str(e)
            print traceback.format_exc()
            print "Unexpected error:", sys.exc_info()[0]
            return None

    # WRITE CONFIG

    # this relies already on the references/children being marked as configurable or not
    def is_table_configurable(self, table_name):
        if len(self.restschema.ovs_tables[table_name].config.keys()) > 0:
            return True
        # references
        for column_name, column in self.restschema.ovs_tables[table_name].references.iteritems():
            if column.relation == 'reference':
                return True
        # children
        for column_name in self.restschema.ovs_tables[table_name].children:
            if column_name not in self.restschema.ovs_tables[table_name].references:
                child_table = column_name
            else:
                child_table = self.restschema.ovs_tables[table_name].references[column_name].ref_table
            if is_table_configurable(child_table):
                return True

        return False

    def setup_row(self, index_values, table, row_data, txn, reflist, parent=None):

        # find out if this row exists
        # If table is Open_vswitch, return first row from table
        if table == 'Open_vSwitch':
            row = self.idl.tables[table].rows.values()[0]
        else:
            row = utils.index_to_row(index_values, self.restschema.ovs_tables[table], self.idl.tables[table])

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
                row.__setattr__(key, utils.get_empty_by_basic_type(row.__getattr__(key)))
            elif key in row_data and (is_new or row.__getattr__(key) != row_data[key]):
                     row.__setattr__(key, row_data[key])

        references = self.restschema.ovs_tables[table].references
        children = self.restschema.ovs_tables[table].children

        # delete all the keys that don't exist
        for key in children:
            child_table = references[key].ref_table if key in references else key
            if child_table in immutable_tables:
                continue

            # forward child references
            if key in references:
                if not is_new and key not in row_data:
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
            child_table = references[key].ref_table if key in references else key

            if key in row_data:

                # forward child references
                if key in references:
                    child_reference_list = self.setup_table(child_table, row_data[key], txn, reflist)
                    if child_table not in immutable_tables:
                        row.__setattr__(key, child_reference_list)
                else:
                    self.setup_table(child_table, row_data[key], txn, reflist, row)

            if child_table in immutable_tables and (key not in row_data or not row_data[key]):
                # Deep cleanup children, even if missing or empty, if can't delete because immutable
                if key in references:
                    self.clean_subtree(child_table, row.__getattr__(key), txn)
                else:
                    self.clean_subtree(child_table, [], txn, row)


        # Looks unnecessary - probably needs to be removed - commenting out for now
        # for key,value in references.iteritems():
        #     if key in self.restschema.ovs_tables[table].children and key in row_data:
        #         child_table = value.ref_table
        #
        #         # this becomes the new reference list.
        #         child_reference_list = self.setup_table(child_table, row_data[key], txn, reflist)
        #         if child_table not in immutable_tables:
        #             row.__setattr__(key, child_reference_list)

        return (row, is_new)

    def clean_subtree(self, table, entries, txn, parent = None):

        if parent is None:
            for row in entries:
                self.clean_row(table, row, txn)
        else:
            #back references
            if table not in immutable_tables:
                self.remove_deleted_rows(table, {}, txn, parent)
            else:
                parent_column = None
                for key,value in self.restschema.ovs_tables[table].references.iteritems():
                    if value.relation == 'parent':
                        parent_column = key
                        break
                for row in self.idl.tables[table].rows.itervalues():
                    if parent_column is not None and row.__getattr__(parent_column) == parent:
                        self.clean_row(table, row, txn)

    def clean_row(self, table, row, txn):
        references = self.restschema.ovs_tables[table].references
        children = self.restschema.ovs_tables[table].children

        # clean children
        for key in children:
            if key in references:
                child_table = references[key].ref_table
                if child_table not in immutable_tables:
                    row.__setattr__(key, [])
                else:
                    self.clean_subtree(child_table, row.__getattr__(key), txn)
            else:
                child_table = key
                self.clean_subtree(child_table, [], txn, row)

        # clean references
        for key,val in references.iteritems():
            if val.relation == 'reference' and val.mutable:
                row.__setattr__(key,[])



    def setup_table(self, table, table_data, txn, reflist, parent = None):

        config_keys = self.restschema.ovs_tables[table].config.keys()
        reference_keys = self.restschema.ovs_tables[table].references.keys()

        parent_column = None
        if parent is not None:
            for key,value in self.restschema.ovs_tables[table].references.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break

        # iterate over each row
        rows = []
        for index, row_data in table_data.iteritems():
            index_values = utils.escaped_split(index)
            (row, isNew) = self.setup_row(index_values, table, row_data, txn, reflist)
            if row is None:
                continue

            # back reference
            if parent_column is not None:
                row.__setattr__(parent_column, parent)

            rows.append(row)

            # save this in global reflist
            reflist[(table, index)] = (row, isNew)

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

            for key,value in references.iteritems():
                if value.relation == 'reference':
                    if not value.mutable and not isNew:
                        continue
                    new_reference_list = []
                    if key in row_data:
                        ref_table = value.ref_table
                        for item in row_data[key]:
                            # TODO: missing item/references will throw an exception
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
                    self.setup_references(child_table, row_data[key], txn, reflist)

    def remove_deleted_rows(self, table, table_data, txn, parent = None):

        parent_column = None
        if parent is not None:
            for key,value in self.restschema.ovs_tables[table].references.iteritems():
                if value.relation == 'parent':
                    parent_column = key
                    break

        # delete rows from DB that are not in declarative config
        delete_rows = []
        for row in self.idl.tables[table].rows.itervalues():
            index = utils.row_to_index(self.restschema.ovs_tables[table], row)

            if parent_column is not None and row.__getattr__(parent_column) != parent:
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
            for key,value in references.iteritems():
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

        # start with Open_vSwitch table
        table_name = 'Open_vSwitch'
        if len(data[table_name]) != 1:
            # TODO: return error - this is not allowed
            return

        self.setup_table(table_name, data[table_name], txn, reflist)

        # All other top level tables, according to schema
        for table_name, table_data in self.restschema.ovs_tables.iteritems():

            if table_data.parent is not None:
                continue

            if table_name == 'Open_vSwitch':
                continue
            if table_name not in data:
                new_data = {}
            else:
                new_data = data[table_name]

            if table_name not in immutable_tables:
                self.remove_deleted_rows(table_name, new_data, txn)

            self.setup_table(table_name, new_data, txn, reflist)

        # the tables are all set up, now connect the references together
        for table_name,value in data.iteritems():
            self.setup_references(table_name, data[table_name], txn, reflist)

        # remove orphaned rows
        # TODO: FIX THIS and turn on - not critical right away since VRF entry can't be removed
        # self.remove_orphaned_rows(txn)

        # verify txn
        # commit txn
        print txn.commit_block()
        print txn.get_error()

def test_write():
    # read the config file
    filename = 'config.db'
    with open(filename) as json_data:
        data = json.load(json_data)
        json_data.close()

    # set up IDL
    manager = OvsdbConnectionManager(settings.get('ovs_remote'), settings.get('ovs_schema'))
    manager.start()
    manager.idl.run()

    init_seq_no = 0
    while True:
        manager.idl.run()
        if init_seq_no != manager.idl.change_seqno:
            break

    # read the schema
    schema = restparser.parseSchema(settings.get('ext_schema'))
    run_config_util = RunConfigUtil(manager.idl, schema)
    run_config_util.write_config_to_db(data)

def main():
    run_config_util = RunConfigUtil(settings)
    config = run_config_util.get_running_config()
    print("Running Config: %s " % json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))

def test_read():
    manager = OvsdbConnectionManager(settings.get('ovs_remote'), settings.get('ovs_schema'))
    manager.start()
    idl = manager.idl

    init_seq_no = 0
    # Wait until the connection is ready
    while True:
        idl.run()
        # print self.idl.change_seqno
        if init_seq_no != idl.change_seqno:
            break
        time.sleep(1)

    restschema = restparser.parseSchema(settings.get('ext_schema'))

    run_config_util = RunConfigUtil(idl, restschema)
    config = run_config_util.get_running_config()
    filename = 'config.db'
    with open(filename, 'w') as fp:
        json.dump(config, fp, sort_keys = True, indent=4, separators=(',', ': '))
        fp.write('\n')
    print(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))

if __name__ == "__main__":
    #test_read()
    #time.sleep(1)
    test_write()
