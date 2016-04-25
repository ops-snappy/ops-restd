#!/usr/bin/env python
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.autoreload
from tornado.options import options
import tornado.web
from tornado.ioloop import IOLoop
from opsrest.settings import settings
from opsrest.application import OvsdbApiApplication
from opsrest.manager import OvsdbConnectionManager
from tornado.log import app_log
import ovs.unixctl
import ovs.unixctl.server
import ops_diagdump
import tornado.http1connection

# enable logging
from tornado.log import enable_pretty_logging
options.logging = settings['logging']
enable_pretty_logging()


def diag_basic_handler(argv):
    # argv[0] is set to the string "basic"
    # argv[1] is set to the feature name, e.g. rest
    feature = argv.pop()
    buff = "Diagnostic dump response for feature " + feature + ".\n"
    buff += "Active HTTPS connections:\n"
    for conn in HTTPS_server._connections:
        buff += "  Client IP is %s\n" % conn.context
    buff += "Transactions list:\n"
    buff += "  Index\t  Status\n"
    buff += "  ---------------\n"
    transactions = app.manager.transactions
    for index, txn in enumerate(transactions.txn_list):
        buff += "  %s\t  %s\n" % (index, txn.status)
    buff += "Total number of pending "\
            "transactions is %s" % len(transactions.txn_list)
    return buff


class UnixctlManager:
    def start(self):
        app_log.info("Creating unixctl server")
        ovs.daemon.set_pidfile(None)
        ovs.daemon._make_pidfile()
        global unixctl_server
        error, unixctl_server = ovs.unixctl.server.UnixctlServer.create(None)
        if error:
            app_log.error("Failed to create unixctl server")
        else:
            app_log.info("Created unixctl server")
            app_log.info("Init diag dump")
            ops_diagdump.init_diag_dump_basic(diag_basic_handler)
            # Add handler in tornado
            IOLoop.current().add_handler(
                unixctl_server._listener.socket.fileno(),
                self.unixctl_run,
                IOLoop.READ | IOLoop.ERROR)

    def unixctl_run(self, fd=None, events=None):
        app_log.debug("Inside unixctl_run")
        if events & IOLoop.ERROR:
            app_log.error("Unixctl socket fd %s error" % fd)
        elif events & IOLoop.READ:
            app_log.debug("READ on unixctl")
            unixctl_server.run()


def main():
    global app, HTTPS_server, HTTP_server

    options.parse_command_line()
    app_log.debug("Creating OVSDB API Application!")
    app = OvsdbApiApplication(settings)

    HTTPS_server = tornado.httpserver.HTTPServer(app, ssl_options={
        "certfile": "/etc/ssl/certs/server.crt",
        "keyfile": "/etc/ssl/certs/server-private.key"})

    HTTP_server = tornado.httpserver.HTTPServer(app)

    app_log.debug("Server listening to port: %s" % options.HTTPS_port)
    HTTPS_server.listen(options.HTTPS_port)

    app_log.debug("Server listening to port: %s" % options.HTTP_port)
    HTTP_server.listen(options.HTTP_port)

    unixmgr = UnixctlManager()
    unixmgr.start()
    app_log.info("Starting server!")
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
