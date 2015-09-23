from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop

from ovs.db.idl import Idl
from ovs.db.idl import SchemaHelper
from ovs.poller import Poller

from halonrest.manager import OvsdbConnectionManager
from halonlib import restparser
from halonrest import constants
import cookiesecret

class OvsdbApiApplication(Application):
    def __init__(self, settings):
        self.settings = settings
        self.settings['cookie_secret'] = cookiesecret.generate_cookie_secret()
        self.manager = OvsdbConnectionManager(self.settings.get('ovs_remote'), self.settings.get('ovs_schema'))
        self.restschema = restparser.parseSchema(self.settings.get('ext_schema'))
        self._url_patterns = self._get_url_patterns()
        Application.__init__(self, self._url_patterns, **self.settings)

        # connect to OVSDB using a callback
        IOLoop.current().add_callback(self.manager.start)

    # adds 'self' to url_patterns
    def _get_url_patterns(self):
        from urls import url_patterns
        modified_url_patterns = []
        for url in url_patterns:
            modified_url_patterns.append( url + ({ 'ref_object': self },))
        return modified_url_patterns
