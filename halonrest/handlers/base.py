from tornado.ioloop import IOLoop
from tornado import web, gen, locks

import json
import httplib

from halonrest.constants import *
from halonrest.resource import Resource
from halonrest import get

class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl

class AutoHandler(BaseHandler):

    # parse the url and http params.
    def prepare(self):

        self.resource_path = Resource.parse_url_path(self.request.path, self.schema, self.idl, self.request.method)

        if self.resource_path is None:
            self.set_status(httplib.NOT_FOUND)
            self.finish()

    @gen.coroutine
    def get(self):

        result = get.get_resource(self.idl, self.resource_path, self.schema, self.request.path)
        if result is None:
            self.set_status(httplib.NOT_FOUND)
        else:
            self.write(json.dumps({'data': result}))

        self.finish()
