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

import json
import time

from opsrest.settings import settings
from ovs.db.idl import Idl, SchemaHelper, Transaction


def connect():
    ovsschema = settings.get('cfg_db_schema')
    ovsremote = settings.get('ovs_remote')
    schema_helper = SchemaHelper(ovsschema)
    schema_helper.register_all()
    idl = Idl(ovsremote, schema_helper)

    change_seqno = idl.change_seqno
    while True:
        idl.run()
        if change_seqno != idl.change_seqno:
            break
        time.sleep(0.001)

    return idl


def read():
    '''
    Walk through the rows in the config table (if any)
    looking for a row with type == startup.

    If found, return content of the "config" field in that row.

    'config' is stored in DB as a JSON string
    '''

    idl = connect()
    for ovs_rec in idl.tables["config"].rows.itervalues():
        row_type = ovs_rec.__getattr__('type')
        if row_type and row_type == 'startup':
                config = ovs_rec.__getattr__('config')
                if config:
                    return json.loads(config)

    return None


def write(data):
    '''
    Walk through the rows in the config table (if any)
    looking for a row with type == startup.

    If found, update content of the "config" field in that row.
    If not found, create new row and set "config" field
    '''
    idl = connect()
    row = None
    for ovs_rec in idl.tables['config'].rows.itervalues():
        row_type = ovs_rec.__getattr__('type')
        if row_type and row_type == 'startup':
            row = ovs_rec
            break

    txn = Transaction(idl)

    if row is None:
        row = txn.insert(idl.tables['config'])
        row.__setattr__('type', 'startup')
        is_new = True

    row.__setattr__('config', json.dumps(data))

    result = txn.commit_block()
    error = txn.get_error()

    return (result, error)
