import time, re, json
from tornado.ioloop import IOLoop

from ovs.db.idl import Idl, SchemaHelper
from ovs.poller import Poller
from transaction import OvsdbTransactionList, OvsdbTransaction
from constants import *

class OvsdbConnectionManager:
    def __init__(self, remote, schema, *args, **kwargs):
        self.timeout = OVSDB_DEFAULT_CONNECTION_TIMEOUT
        self.remote = remote
        self.schema = schema
        self.schema_helper = None
        self.idl = None
        self.transactions = None

        self.curr_seqno = 0

    def start(self):
        # reset all connections
        try:
            if self.idl is not None:
                self.idl.close()

            # set up the schema and register all tables
            self.schema_helper = SchemaHelper(self.schema)
            self.schema_helper.register_all()
            self.idl = Idl(self.remote, self.schema_helper)
            self.curr_seqno = self.idl.change_seqno

            #  we do not reset transactions when the DB connection goes down
            if self.transactions is None:
                self.transactions = OvsdbTransactionList()

            self.idl_run()
            self.monitor_connection()

        except Exception as e:
            # TODO: log this exception
            # attempt again in the next IOLoop iteration
            IOLoop.current().add_timeout(time.time() + self.timeout, self.start)

    def monitor_connection(self):
        try:
            self.poller = Poller()
            self.idl.wait(self.poller)
            self.timeout = self.poller.timeout / 1000.0
            self.add_fd_callbacks()
        except:
            self.idl_run()
            IOLoop.current().add_timeout(time.time() + self.timeout, self.monitor_connection)

    def add_fd_callbacks(self):
        # add handlers to file descriptors from poll
        if len(self.poller.poll.rlist) is 0:
            self.rlist = []
            self.wlist = []
            self.xlist = []
            raise Exception('ovsdb read unavailable')

        for fd in self.poller.poll.rlist:
            if fd not in self.rlist:
                IOLoop.current().add_handler(fd, self.read_handler, IOLoop.READ | IOLoop.ERROR)
                self.rlist.append(fd)
                IOLoop.current().add_timeout(time.time() + self.timeout, self.read_handler)

    def read_handler(self, fd=None, events=None):
        if fd is not None:
            IOLoop.current().remove_handler(fd)
            self.rlist.remove(fd)

        self.idl_run()
        IOLoop.current().add_callback(self.monitor_connection)

    # TODO: This could be a blocking call
    def idl_run(self):

        while True:
            self.idl.run()
            if self.idl.change_seqno != self.curr_seqno:
                self.curr_seqno = self.idl.change_seqno
                self.check_transactions()
            else:
                break
        return

    def check_transactions(self):

        for item in self.transactions.txn_list:
            item.commit()

        count = 0
        for item in self.transactions.txn_list:

            # TODO: Handle all states
            if item.status in (SUCCESS, UNCHANGED, ERROR, ABORTED):
                item.event.set()
                self.transactions.txn_list.pop(count)
            else:
                count += 1

    def get_new_transaction(self):
        return OvsdbTransaction(self.idl)

    def monitor_transaction(self, txn):
        self.transactions.add_txn(txn)

    # Maintain a JSON cache of IDL
    def _update_cache(self):
        table_names = self.idl.tables.keys()
        tables_dict = {}

        # iterate over each table and create a dictionary
        for name in table_names:
            column_keys = self.idl.tables[name].columns.keys()
            # iterate over every row in a table
            row_dict = {}
            for row in self.idl.tables[name].rows.itervalues():
                row_uuid = row.uuid
                row_data = {}
                for k,v in zip(column_keys, row._data.itervalues()):
                    row_data[k] = v.to_string()
                row_dict[row_uuid] = row_data
            tables_dict[name] = row_dict
        self.db_cache = tables_dict
