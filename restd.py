#!/usr/bin/env python
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
from tornado.options import options
import tornado.web

from opsrest.settings import settings
from opsrest.application import OvsdbApiApplication

from tornado.log import app_log

# enable logging
from tornado.log import enable_pretty_logging
options.logging = settings['logging']
enable_pretty_logging()


def main():

    app_log.debug("Creating OVSDB API Application!")
    app = OvsdbApiApplication(settings)
    http_server = tornado.httpserver.HTTPServer(app)

    app_log.debug("Server listening to port: %s" % options.http_port)
    http_server.listen(options.http_port)

    app_log.info("Starting server!")
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
