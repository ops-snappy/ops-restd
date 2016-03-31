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
    options.parse_command_line()

    app_log.debug("Creating OVSDB API Application!")
    app = OvsdbApiApplication(settings)
    HTTPS_server = tornado.httpserver.HTTPServer(app, ssl_options={
        "certfile":"/etc/ssl/certs/server.crt",
        "keyfile":"/etc/ssl/certs/server-private.key"})

    HTTP_server = tornado.httpserver.HTTPServer(app)

    app_log.debug("Server listening to port: %s" % options.HTTPS_port)
    HTTPS_server.listen(options.HTTPS_port)

    app_log.debug("Server listening to port: %s" % options.HTTP_port)
    HTTP_server.listen(options.HTTP_port)

    app_log.info("Starting server!")
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
