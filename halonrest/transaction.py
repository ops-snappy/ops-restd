import ovs.db.idl
import json
from tornado.locks import Event

class OvsdbTransactionList:
    def __init__(self):
        self.txn_list = []

    def add_txn(self, txn):
        self.txn_list.append(txn)

class OvsdbTransaction:
    def __init__(self, idl):
        self.status = None
        self.txn = ovs.db.idl.Transaction(idl)
        self.event = Event()

    def commit(self):
        self.status = self.txn.commit()
        return self.status

    def insert(self, table):
        return self.txn.insert(table)

    def abort(self):
        self.txn.abort()

    def get_db_error_msg(self):
        db_dict = json.loads(self.txn.get_error())
        return db_dict['details']
