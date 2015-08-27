#!/usr/bin/env python
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
from tornado.options import options
import tornado.web

from halonrest.settings import settings
from halonrest.application import OvsdbApiApplication

# enable logging
from tornado.log import enable_pretty_logging
options.logging = settings['logging']
enable_pretty_logging()

def main():
    app = OvsdbApiApplication(settings)
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.http_port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
