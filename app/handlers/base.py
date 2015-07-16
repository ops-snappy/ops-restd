from tornado.ioloop import IOLoop
from tornado import web, gen, locks
import ovs.db.idl

from constants import *
import json
from resource import Resource
from utils.utils import *

class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object

class AutoHandler(BaseHandler):

    # parse the url and http params.
    def prepare(self):
        self.resource_path = Resource.parse_url_path(self.request.path, self.ref_object.restschema, self.ref_object.manager.idl)

    @gen.coroutine
    def get(self):
        try:
            Resource.verify_resource_path(self.ref_object.manager.idl, self.resource_path, self.ref_object.restschema)
            result = Resource.get_resource(self.ref_object.manager.idl, self.resource_path, self.ref_object.restschema, self.request.path)
            result = {'data' : json.dumps(result)}
            self.write(result)
            self.finish()
        except:
            self.write({'status' : 'failed'})
            self.finish()
