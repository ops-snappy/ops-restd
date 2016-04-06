# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import time
from tornado.ioloop import IOLoop
from tornado.log import app_log

from ovs.db import error
from ovs.db.idl import SchemaHelper

from ops.opsidl import OpsIdl
from opsrest.transaction import OvsdbTransactionList, OvsdbTransaction
from opsrest.constants import \
    OVSDB_DEFAULT_CONNECTION_TIMEOUT,\
    INCOMPLETE


class OvsdbConnectionManager:
    def __init__(self, remote, schema, *args, **kwargs):
        self.timeout = OVSDB_DEFAULT_CONNECTION_TIMEOUT
        self.remote = remote
        self.schema = schema
        self.schema_helper = None
        self.idl = None
        self.transactions = None
        self.curr_seqno = 0
        self.connected = False

    def start(self):
        try:
            app_log.info("Starting Connection Manager!")
            if self.idl is not None:
                self.idl.close()
            self.schema_helper = SchemaHelper(self.schema)
            self.schema_helper.register_all()
            self.idl = OpsIdl(self.remote, self.schema_helper)
            self.curr_seqno = self.idl.change_seqno

            # We do not reset transactions when the DB connection goes down
            if self.transactions is None:
                self.transactions = OvsdbTransactionList()

            self.idl_init()

        except Exception as e:
            app_log.info("Connection Manager failed! Reason: %s" % e)
            IOLoop.current().add_timeout(time.time() + self.timeout,
                                         self.start)

    def idl_init(self):
        try:
            self.idl.run()
            if not self.idl.has_ever_connected():
                app_log.debug("ovsdb unavailable retrying")
                IOLoop.current().add_timeout(time.time() + self.timeout,
                                             self.idl_init)
            else:
                self.idl_establish_connection()
        except error.Error as e:
            # idl will raise an error exception if cannot connect
            app_log.debug("Failed to connect, retrying. Reason: %s" % e)
            IOLoop.current().add_timeout(time.time() + self.timeout,
                                         self.idl_init)

    def idl_reconnect(self):
        try:
            app_log.debug("Trying to reconnect to ovsdb")
            # Idl run will do the reconnection
            self.idl.run()
            # If the seqno change the ovsdb connection is restablished.
            if self.curr_seqno == self.idl.change_seqno:
                app_log.debug("ovsdb unavailable retrying")
                self.connected = False
                IOLoop.current().add_timeout(time.time() + self.timeout,
                                             self.idl_reconnect)
            else:
                self.idl_establish_connection()
        except error.Error as e:
            # idl will raise an error exception if cannot reconnect
            app_log.debug("Failed to connect, retrying. Reason: %s" % e)
            IOLoop.current().add_timeout(time.time() + self.timeout,
                                         self.idl_reconnect)

    def idl_establish_connection(self):
        app_log.info("ovsdb connection ready")
        self.connected = True
        self.curr_seqno = self.idl.change_seqno
        self.ovs_socket = self.idl._session.rpc.stream.socket
        IOLoop.current().add_handler(self.ovs_socket.fileno(),
                                     self.idl_run,
                                     IOLoop.READ | IOLoop.ERROR)

    def idl_run(self, fd=None, events=None):
        if events & IOLoop.ERROR:
            app_log.debug("Socket fd %s error" % fd)
            if fd is not None:
                IOLoop.current().remove_handler(fd)
                self.idl_reconnect()
        elif events & IOLoop.READ:
            app_log.debug("Updating idl replica")
            self.idl.run()
            if self.curr_seqno != self.idl.change_seqno and \
               len(self.transactions.txn_list):
                self.check_transactions()
            self.curr_seqno = self.idl.change_seqno

    def check_transactions(self):
        for index, tx in enumerate(self.transactions.txn_list):
            tx.commit()
            # TODO: Handle all states
            if tx.status is not INCOMPLETE:
                self.transactions.txn_list.pop(index)
                tx.event.set()

    def get_new_transaction(self):
        return OvsdbTransaction(self.idl)

    def monitor_transaction(self, txn):
        self.transactions.add_txn(txn)
