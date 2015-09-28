#!/usr/bin/env python
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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

from opsrest.settings import settings
from opsrest.manager import OvsdbConnectionManager
from opsrest.utils import utils
from opsrest import resource
from opslib import restparser
import ovs
import json
import sys
import time
import traceback

import ovs.db.idl
import ovs.db.types
import types
import uuid


class StartupConfigUtil():
    def __init__(self):
        manager = OvsdbConnectionManager(settings.get('ovs_remote'),
                                         settings.get('cfg_db_schema'))
        manager.start()
        self.idl = manager.idl

        init_seq_no = 0
        # Wait until the connection is ready
        while True:
            self.idl.run()
            # print self.idl.change_seqno
            if init_seq_no != self.idl.change_seqno:
                break
            time.sleep(0.001)

    def get_config(self):
        '''
        Walk through the rows in the config table (if any)
        looking for a row with type == startup.

        If found, return content of the "config" field in that row.

        'config' is stored in DB as a JSON string
        '''

        for ovs_rec in self.idl.tables["config"].rows.itervalues():
            row_type = ovs_rec.__getattr__('type')
            if row_type and row_type == 'startup':
                    config = ovs_rec.__getattr__('config')
                    if config:
                        return json.loads(config)

        return None

    def write_config_to_db(self, config):
        '''
        Walk through the rows in the config table (if any)
        looking for a row with type == startup.

        If found, update content of the "config" field in that row.
        If not found, create new row and set "config" field
        '''
        row = None
        for ovs_rec in self.idl.tables['config'].rows.itervalues():
            row_type = ovs_rec.__getattr__('type')
            if row_type and row_type == 'startup':
                row = ovs_rec
                break

        txn = ovs.db.idl.Transaction(self.idl)

        if row is None:
            row = txn.insert(self.idl.tables['config'])
            row.__setattr__('type', 'startup')
            is_new = True

        row.__setattr__('config', json.dumps(config))

        result = txn.commit_block()
        error = txn.get_error()

        return (result, error)


def main():
    startup_config_util = StartupConfigUtil()
    config = startup_config_util.get_config()
    print("Startup Config: %s " % json.dumps(config, sort_keys=True,
                                             indent=4, separators=(',', ': ')))
