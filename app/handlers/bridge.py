from tornado.ioloop import IOLoop
from tornado import web, gen, locks
import ovs.db.idl

from constants import *
import json

class BridgeHandler(web.RequestHandler):
    def initialize(self, ref_object):
        self.ref_object = ref_object

    def set_up_transaction(self, attributes=None):
         get_object = self.ref_object.manager.idl.tables['Bridge']
         for row in get_object.rows.itervalues():
             row.stp_enable = True

    def get_handler(self, *args, **kwargs):
        list_output = []
        dict_output = {}
        dict_output[args[1]] = []
        get_bridge_object = self.ref_object.manager.idl.tables
        tables_dict = {}
        for name in get_bridge_object:
            column_keys = get_bridge_object['Bridge'].columns.keys()
            row_dict = {}
            for row in get_bridge_object['Bridge'].rows.itervalues():
                row_uuid = str(row.uuid)
                row_data = {}
                for key, value in zip(column_keys, row._data.itervalues()):
                    row_data[key] = value.to_string()
                row_dict[row_uuid] = row_data
            tables_dict['Bridge'] = row_dict
        if args[1] == None:
            self.write(json.dumps(tables_dict['Bridge'], ensure_ascii=False, indent=4, separators=(',',':')))
        else:
            for key, value in tables_dict['Bridge'].iteritems():
                for ke, va in value.iteritems():
                    if args[1] == ke:
                         list_output.append(va)
            dict_output[args[1]].append(list_output)
            self.write(json.dumps(dict_output, ensure_ascii=False, indent=4, separators=(',',':')))

    def post_handler(self, *args, **kwargs):
        pass

    @gen.coroutine
    def get(self, slug=None):
        self.get_handler(self, slug)
        self.finish()

    @gen.coroutine
    def post(self):
        self.txn = self.ref_object.manager.get_new_transaction()
        self.set_up_transaction()
        self.txn.commit()
        if self.txn.status not in (SUCCESS, UNCHANGED, ERROR, ABORTED):
            self.ref_object.manager.monitor_transaction(self.txn)
            yield self.txn.event.wait()

        self.post_handler()
        self.finish()
