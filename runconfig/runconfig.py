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
                # this is a list of references

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
                for columnName, column in table.references.iteritems():
                    if column.relation == "parent":
                        table.parent = column.ref_table

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

def main():
    run_config_util = RunConfigUtil(settings)
    config = run_config_util.get_running_config()
    print("Running Config: %s " % json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))

def test():
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
    print(json.dumps(config, sort_keys=True, indent=4, separators=(',', ': ')))

if __name__ == "__main__":
    test()
