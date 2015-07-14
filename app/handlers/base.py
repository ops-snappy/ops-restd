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
        self.resource_path = self.request.path.split('/')
        self.resource_path = [i for i in self.resource_path if i != '']
        self.resource_path = Resource.parse_url_path(self.resource_path, self.ref_object.restschema)

    @gen.coroutine
    def get(self):

        # /config returns config data
        # /stats returns stats data
        # /status returns status data
        # /subresource returns uuid-name if subresource is a reference
        #              returns configuration if subresource is a child
        try:
            Resource.verify_resource_path(self.ref_object.manager.idl, self.resource_path)

            resource = self.resource_path
            while True:
                if resource.next is None:
                    break
                else:
                    resource = resource.next

            table = self.ref_object.manager.idl.tables[resource.table]
            schema = self.ref_object.restschema.ovs_tables[resource.table]

            # only return config, status, stats datatype
            if resource.datatype == 'config':
                keys = schema.config.keys()
            elif resource.datatype == 'status':
                keys = schema.status.keys()
            elif resource.datatype == 'stats':
                keys = schema.stats.keys()
            else:
                raise Exception("Incorrect URL")

            for row in table.rows.itervalues():
                if str(row.uuid) == resource.uuid:
                    data = read_column_from_row(row, keys)
                    break

            # we have the data, write it back to the http connection
            response = {'status' : 'success',
                    'data' : data, }
            self.write(response)
        except Exception, e:
            print e
            self.write({'status' : 'fail'})

        self.finish()
