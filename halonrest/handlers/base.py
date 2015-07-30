from tornado.ioloop import IOLoop
from tornado import web, gen, locks

import json
import httplib

from halonrest.constants import *
from halonrest.resource import Resource

class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl

class AutoHandler(BaseHandler):

    def print_(self, resource):
        if resource is None:
            return

        print resource.table, resource.row, resource.column, resource.relation
        self.print_(resource.next)

    # parse the url and http params.
    def prepare(self):

        self.resource_path = Resource.parse_url_path(self.request.path, self.schema, self.idl)

        if self.resource_path is None:
            self.set_status(httplib.NOT_FOUND)
            self.finish()
        self.print_r(self.resource_path)

    @gen.coroutine
    def get(self):

        if Resource.verify_resource_path(self.resource_path, self.schema, self.idl):
            result = Resource.get_resource(self.idl, self.resource_path, self.schema, self.request.path)
            self.write(json.dumps({'data': result}))
        else:
            self.set_status(httplib.NOT_FOUND)

        self.finish()

    @gen.coroutine
    def post(self):
        if Resource.verify_resource_path(self.resource_path, self.schema, self.idl):
            self.txn = self.ref_object.manager.get_new_transaction()
            result = Resource.post_resource(self.idl, self.txn, self.resource_path, self.schema, json.loads(self.request.body))
            if result not in (SUCCESS, UNCHANGED, ERROR, ABORTED):
                self.ref_object.manager.monitor_transaction(self.txn)
            yield self.txn.event.wait()

            self.set_status(httplib.OK)
            self.finish()
        else:
            self.set_status(httplib.BAD_REQUEST)
            self.finish()
