from tornado.ioloop import IOLoop
from tornado import web, gen, locks
from tornado.web import asynchronous
from tornado.concurrent import Future

import json
import httplib
import re

import userauth
from runconfig import runconfig, startupconfig

from opsrest.resource import Resource
from opsrest.parse import parse_url_path
from opsrest.constants import *
from opsrest.utils.utils import *
from opsrest import get, post, delete, put

from tornado.log import app_log

class ConfigHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl
        self.request.path = re.sub("/{2,}", "/", self.request.path)

        # CORS
        allow_origin = self.request.protocol + "://"
        allow_origin += self.request.host.split(":")[0] # removing port if present
        self.set_header("Access-Control-Allow-Origin", allow_origin)
        self.set_header("Access-Control-Expose-Headers", "Date")

        # TODO - remove next line before release - needed for testing
        self.set_header("Access-Control-Allow-Origin", "*")

    def prepare(self):
        self.request_type = self.get_argument('type', 'running')
        app_log.debug('request type: %s', self.request_type)

        if self.request_type == 'running':
            self.config_util = runconfig.RunConfigUtil(self.idl, self.schema)
        elif self.request_type == 'startup':
            self.config_util = startupconfig.StartupConfigUtil()
        else:
            self.set_status(httplib.BAD_REQUEST)
            self.finish()

    @gen.coroutine
    def get(self):

        result, error = yield self._get_config()
        app_log.debug('Transaction result: %s, Transaction error: %s', result, error)

        if result is None:
            if self.request_type == 'running':
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
            else:
                self.set_status(httplib.NOT_FOUND)
        else:
            self.set_status(httplib.OK)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(json.dumps(result))

        self.finish()

    def _get_config(self):
        waiter = Future()
        waiter.set_result((self.config_util.get_config(), True))
        return waiter

    @gen.coroutine
    def put(self):

        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:

            # get the config
            config_data = json.loads(self.request.body)
            result, error = yield self._write_config(config_data)
            app_log.debug('Transaction result: %s, Transaction error: %s', result, error)

            if result.lower() != 'success' and result.lower() != 'unchanged':
                self.set_status(httplib.BAD_REQUEST)
                self.write(to_json_error(err_msg))
            else:
                self.set_status(httplib.OK)

            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    def _write_config(self, config_data):
        waiter = Future()
        waiter.set_result(self.config_util.write_config_to_db(config_data))
        return waiter
