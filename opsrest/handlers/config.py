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

from tornado import gen

import json
import httplib

from opsrest.constants import *
import opsrest.utils.startupconfig
from opsrest.handlers.base import BaseHandler
from opsrest.transaction import OvsdbTransactionResult
import ops.dc

from tornado.log import app_log


class ConfigHandler(BaseHandler):

    def prepare(self):

        try:
            # Call parent's prepare to check authentication
            super(ConfigHandler, self).prepare()

            self.request_type = self.get_argument('type', 'running')
            app_log.debug('request type: %s', self.request_type)

            if self.request_type not in ['running', 'startup']:
                self.set_status(httplib.BAD_REQUEST)
                self.finish()

        except APIException as e:
            self.on_exception(e)
            self.finish()

        except Exception, e:
            self.on_exception(e)
            self.finish()

    @gen.coroutine
    def get(self):
        try:
            if self.request_type == 'running':
                result = ops.dc.read(self.schema, self.idl)
            else:
                # FIXME: This is a blocking call
                result = opsrest.utils.startupconfig.read()

            if result is None:
                if self.request_type == 'running':
                    self.set_status(httplib.INTERNAL_SERVER_ERROR)
                else:
                    self.set_status(httplib.NOT_FOUND)
            else:
                self.set_status(httplib.OK)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                        HTTP_CONTENT_TYPE_JSON)
                self.write(json.dumps(result))

        except Exception as e:
            self.on_exception(e)

        self.finish()

    @gen.coroutine
    def put(self):
        try:

            if HTTP_HEADER_CONTENT_LENGTH not in self.request.headers:
                raise LengthRequired

            data = json.loads(self.request.body)
            status = None
            error = None

            if self.request_type == 'running':
                self.txn = self.ref_object.manager.get_new_transaction()
                result = OvsdbTransactionResult(ops.dc.write(data, self.schema,
                                                self.idl, self.txn.txn))
                status = result.status
                if status == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    yield self.txn.event.wait()
                    status = self.txn.status

            else:
                # FIXME: This is a blocking call.
                (status, error) = opsrest.utils.startupconfig.write(data)

            if status == SUCCESS:
                self.set_status(httplib.OK)
            elif status == UNCHANGED:
                self.set_status(httplib.NOT_MODIFIED)
            else:
                raise APIException(error)

        except Exception as e:
            self.on_exception(e)

        self.finish()
