# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from tornado.ioloop import IOLoop
from tornado import web, gen, locks
from tornado.log import app_log

import json
import httplib
import re
import hashlib

from opsrest.resource import Resource
from opsrest.parse import parse_url_path
from opsrest.constants import *
from opsrest.utils import utils
from opsrest.exceptions import *

from opsrest import get, post, delete, put

import userauth
from opsrest.settings import settings

# TODO refactor common handler functions


class BaseHandler(web.RequestHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        self.ref_object = ref_object
        self.schema = self.ref_object.restschema
        self.idl = self.ref_object.manager.idl
        self.request.path = re.sub("/{2,}", "/", self.request.path).rstrip('/')

    def set_default_headers(self):
        # CORS
        allow_origin = self.request.protocol + "://"
        # removing port if present
        allow_origin += self.request.host.split(":")[0]
        self.set_header("Cache-control", "no-cache")
        self.set_header("Access-Control-Allow-Origin", allow_origin)
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Expose-Headers", "Date")

        # TODO - remove next line before release - needed for testing
        if HTTP_HEADER_ORIGIN in self.request.headers:
            self.set_header("Access-Control-Allow-Origin",
                            self.request.headers[HTTP_HEADER_ORIGIN])

    def get_current_user(self):
        return userauth.get_request_user(self)


class LoginHandler(BaseHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        pass

    @gen.coroutine
    def get(self):

        is_authenticated = userauth.is_user_authenticated(self)
        if not is_authenticated:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
        else:
            self.set_status(httplib.OK)

        self.finish()

    @gen.coroutine
    def post(self):

        login_success = userauth.handle_user_login(self)
        if not login_success:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
        else:
            self.set_status(httplib.OK)

        self.finish()


class AutoHandler(BaseHandler):

    # parse the url and http params.
    def prepare(self):

        app_log.debug("Incoming request from %s: %s",
                      self.request.remote_ip,
                      self.request)

        if settings['auth_enabled'] and self.request.method != "OPTIONS":
            is_authenticated = userauth.is_user_authenticated(self)
        else:
            is_authenticated = True

        if not is_authenticated:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
            self.finish()
        else:
            self.resource_path = parse_url_path(self.request.path,
                                                self.schema,
                                                self.idl,
                                                self.request.method)

            if self.resource_path is None:
                self.set_status(httplib.NOT_FOUND)
                self.finish()

    def on_finish(self):
        app_log.debug("Finished handling of request from %s",
                      self.request.remote_ip)

    @gen.coroutine
    def options(self):

        resource = self.resource_path
        while resource.next is not None:
            resource = resource.next

        allowed_methods = ', '.join(resource.get_allowed_methods(self.schema))

        self.set_header(HTTP_HEADER_ALLOW, allowed_methods)
        self.set_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_METHODS,
                        allowed_methods)

        if HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS in self.request.headers:
            header_ = HTTP_HEADER_ACCESS_CONTROL_REQUEST_HEADERS
            self.set_header(HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS,
                            self.request.headers[header_])

        self.set_status(httplib.OK)
        self.finish()

    @gen.coroutine
    def get(self):

        selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)

        app_log.debug("Query arguments %s" % self.request.query_arguments)

        result = get.get_resource(self.idl, self.resource_path,
                                  self.schema, self.request.path,
                                  selector, self.request.query_arguments)

        if result is None:
            self.set_status(httplib.NOT_FOUND)
        elif self.successful_query(result):
            self.set_status(httplib.OK)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(json.dumps(result))

        self.finish()

    @gen.coroutine
    def post(self):

        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:
            try:
                # get the POST body
                post_data = json.loads(self.request.body)

                # create a new ovsdb transaction
                self.txn = self.ref_object.manager.get_new_transaction()

                # post_resource performs data verficiation, prepares and
                # commits the ovsdb transaction
                result = post.post_resource(post_data, self.resource_path,
                                            self.schema, self.txn,
                                            self.idl)

                status = result.status
                if status == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction
                    # completes with either success or failure
                    yield self.txn.event.wait()
                    status = self.txn.status

                # complete transaction
                self.transaction_complete(status)

            except APIException as e:
                self.on_exception(e)

            except ValueError as e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(utils.to_json_error(e))

            except Exception as e:
                self.on_exception(e)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    def compute_etag(self, data=None):
        if data is None:
            return super(AutoHandler, self).compute_etag()

        hasher = hashlib.sha1()
        for element in data:
            hasher.update(element)
        return '"%s"' % hasher.hexdigest()

    def process_if_match(self):
        if HTTP_HEADER_CONDITIONAL_IF_MATCH in self.request.headers:
            result = get.get_resource(self.idl, self.resource_path,
                                      self.schema, self.request.path,
                                      None, self.request.query_arguments)
            if result is None:
                self.set_status(httplib.PRECONDITION_FAILED)
                return False

            match = False
            etags = self.request.headers.get(HTTP_HEADER_CONDITIONAL_IF_MATCH,
                                             "").split(',')
            current_etag = self.compute_etag(json.dumps(result))
            for e in etags:
                if e == current_etag or e == '"*"':
                    match = True
                    break

            if not match:
                if self.request.method == 'DELETE':
                    self.set_status(httplib.PRECONDITION_FAILED)
                    return False

                data = json.loads(self.request.body)
                if OVSDB_SCHEMA_CONFIG in data:
                    if data[OVSDB_SCHEMA_CONFIG] == \
                            result[OVSDB_SCHEMA_CONFIG]:
                        self.set_status(httplib.OK)
                        return False
                self.set_status(httplib.PRECONDITION_FAILED)
                return False

        return True

    @gen.coroutine
    def put(self):
        if HTTP_HEADER_CONTENT_LENGTH in self.request.headers:
            try:
                proceed = self.process_if_match()
                if proceed:
                    # get the PUT body
                    update_data = json.loads(self.request.body)
                    # create a new ovsdb transaction
                    self.txn = self.ref_object.manager.get_new_transaction()

                    # put_resource performs data verfication, prepares and
                    # commits the ovsdb transaction
                    result = put.put_resource(update_data, self.resource_path,
                                              self.schema, self.txn, self.idl)

                    status = result.status
                    if status == INCOMPLETE:
                        self.ref_object.manager.monitor_transaction(self.txn)
                        # on 'incomplete' state we wait until the transaction
                        # completes with either success or failure
                        yield self.txn.event.wait()
                        status = self.txn.status

                    # complete transaction
                    self.transaction_complete(status)

            except APIException as e:
                self.on_exception(e)

            except ValueError as e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(utils.to_json_error(e))

            except Exception as e:
                self.on_exception(e)

        else:
            self.set_status(httplib.LENGTH_REQUIRED)

        self.finish()

    @gen.coroutine
    def delete(self):

        try:
            proceed = self.process_if_match()
            if proceed:
                self.txn = self.ref_object.manager.get_new_transaction()

                result = delete.delete_resource(self.resource_path,
                                                self.schema, self.txn,
                                                self.idl)
                status = result.status
                if status == INCOMPLETE:
                    self.ref_object.manager.monitor_transaction(self.txn)
                    # on 'incomplete' state we wait until the transaction
                    # completes with either success or failure
                    yield self.txn.event.wait()
                    status = self.txn.status

            # complete transaction
            self.transaction_complete(status)

        except APIException as e:
            self.on_exception(e)

        except Exception as e:
            self.on_exception(e)

        self.finish()

    def transaction_complete(self, status):

        # TODO: The http status codes are currently
        # not in accordance with REST good practices.

        app_log.debug("Transaction result: %s", status)

        method = self.request.method
        if status == SUCCESS:
            if method == 'POST':
                self.set_status(httplib.CREATED)
            elif method == 'PUT':
                self.set_status(httplib.OK)
            elif method == 'DELETE':
                self.set_status(httplib.NO_CONTENT)

        elif status == UNCHANGED:
            self.set_status(httplib.OK)

        else:
            error = self.txn.get_error()
            raise APIException(error)

    def successful_query(self, result):

        if isinstance(result, dict) and ERROR in result:
            self.set_status(httplib.BAD_REQUEST)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(utils.to_json(result))
            return False
        else:
            return True

    def on_exception(self, e):

        app_log.debug(e)
        self.txn.abort()

        # uncaught exceptions
        if not isinstance(e, APIException):
            self.set_status = httplib.INTERNAL_SERVER_ERROR
        else:
            self.set_status(e.status_code)

        self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
        self.write(str(e))
