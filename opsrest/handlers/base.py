# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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

import re
import userauth
import rbac
import httplib
import hashlib
import json

from tornado import web

from opsrest.constants import *
from opsrest.exceptions import APIException, TransactionFailed, \
    ParameterNotAllowed, NotAuthenticated, \
    AuthenticationFailed, ForbiddenMethod
from opsrest.settings import settings
from opsrest.utils.auditlogutils import audit_log_user_msg
from opsrest.utils.getutils import get_query_arg

from tornado.log import app_log


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
        self.set_header("Access-Control-Expose-Headers", "Date,%s" %
                        HTTP_HEADER_ETAG)
        self.set_header("Access-Control-Request-Headers",
                        HTTP_HEADER_CONDITIONAL_IF_MATCH)

        # TODO - remove next line before release - needed for testing
        if HTTP_HEADER_ORIGIN in self.request.headers:
            self.set_header("Access-Control-Allow-Origin",
                            self.request.headers[HTTP_HEADER_ORIGIN])

    def prepare(self):
        try:
            app_log.debug("Incoming request from %s: %s",
                          self.request.remote_ip,
                          self.request)

            if settings['auth_enabled'] and self.request.method != "OPTIONS":
                is_authenticated = userauth.is_user_authenticated(self)
            else:
                is_authenticated = True

            if not is_authenticated:
                raise NotAuthenticated

            # Check user's permissions
            self.check_method_permission()

            sort = get_query_arg(REST_QUERY_PARAM_SORTING,
                                 self.request.query_arguments)

            depth = get_query_arg(REST_QUERY_PARAM_DEPTH,
                                  self.request.query_arguments)

            columns = get_query_arg(REST_QUERY_PARAM_COLUMNS,
                                    self.request.query_arguments)

            if self.request.method != REQUEST_TYPE_READ \
               and (depth is not None or columns is not None or
                    sort is not None):
                raise ParameterNotAllowed("Arguments %s, %s and %s "
                                          "are only allowed in %s" %
                                          (REST_QUERY_PARAM_SORTING,
                                           REST_QUERY_PARAM_DEPTH,
                                           REST_QUERY_PARAM_COLUMNS,
                                           REQUEST_TYPE_READ))

        except APIException as e:
            self.on_exception(e)
            self.finish()

        except Exception, e:
            self.on_exception(e)
            self.finish()

    def get_current_user(self):
        return userauth.get_request_user(self)

    def on_exception(self, e):

        if hasattr(self, 'txn'):
            self.txn.abort()

        # uncaught exceptions
        if not isinstance(e, APIException):
            app_log.debug("Caught unexpected exception:\n%s" % e)
            self.set_status(httplib.INTERNAL_SERVER_ERROR)
        elif isinstance(e, NotAuthenticated) or \
                isinstance(e, AuthenticationFailed):
            app_log.debug("Caught Authentication Exception:\n%s" % e)
            self.set_header(HTTP_HEADER_LINK, REST_LOGIN_PATH)
            self.set_status(e.status_code)
        else:
            app_log.debug("Caught APIException:\n%s" % e)
            self.set_status(e.status_code)

        self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
        self.write(str(e))

    def compute_etag(self, data=None):
        if data is None:
            return super(BaseHandler, self).compute_etag()

        hasher = hashlib.sha1()
        for element in data:
            hasher.update(element)
        return '"%s"' % hasher.hexdigest()

    def process_if_match(self):
        if HTTP_HEADER_CONDITIONAL_IF_MATCH in self.request.headers:

            app_log.debug("Processing If-Match")

            selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)
            query_arguments = self.request.query_arguments
            result = None

            from opsrest.handlers.ovsdbapi import OVSDBAPIHandler
            if isinstance(self, OVSDBAPIHandler):
                app_log.debug("If-Match is for OVSDBAPIHandler")
                from opsrest import get
                result = get.get_resource(self.idl, self.resource_path,
                                          self.schema, self.request.path,
                                          selector, query_arguments)
            elif self.controller is not None:
                app_log.debug("If-Match is for custom resource")

                if 'resource_id' in self.path_kwargs:
                    item_id = self.path_kwargs['resource_id']
                else:
                    item_id = None

                app_log.debug("Using resource_id=%s" % item_id)
                if item_id:
                    result = self.controller.get(item_id,
                                                 self.get_current_user(),
                                                 selector, query_arguments)
                else:
                    result = self.controller.get_all(self.get_current_user(),
                                                     selector, query_arguments)

            else:
                raise TransactionFailed("Resource cannot handle If-Match")

            if result is None:
                app_log.debug("If-Match's result is empty")
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
                # If is a PUT operation and the change request state
                # is already reflected in the current state of the
                # target resource it must return 2xx(Succesful)
                # https://tools.ietf.org/html/rfc7232#section-3.1
                if self.request.method == REQUEST_TYPE_UPDATE:
                    data = json.loads(self.request.body)
                    if OVSDB_SCHEMA_CONFIG in data and \
                        data[OVSDB_SCHEMA_CONFIG] == \
                            result[OVSDB_SCHEMA_CONFIG]:
                            # Set PUT Successful code and finish
                            self.set_status(httplib.OK)
                            return False
                # For POST, GET, DELETE, PATCH return precondition failed
                self.set_status(httplib.PRECONDITION_FAILED)
                return False
        # Etag matches
        return True

    def on_finish(self):
        app_log.debug("Finished handling of request from %s",
                      self.request.remote_ip)
        # AuditLog call
        op = self.request.method
        if op in AUDIT_LOG_ACCEPTED_REQUESTS:
            path = self.request.path
            user = None
            cfgdata = self.request.body
            if path == REST_LOGIN_PATH and \
               USERNAME_KEY in self.request.arguments:
                user = self.request.arguments[USERNAME_KEY][0]
            if not user and self.get_current_user():
                user = self.get_current_user()
            hostname = self.request.host
            addr = self.request.remote_ip
            # HTTP/1.1 Status Code Successful 2xx validation
            result = int(200 <= self.get_status() < 300)
            audit_log_user_msg(op, cfgdata, user, hostname, addr, result)

    def check_method_permission(self):

        method = self.request.method

        # Check permissions only if authentication is enabled
        # Plus, OPTIONS is allowed for unauthenticated users
        if method != REQUEST_TYPE_OPTIONS:
            username = self.get_current_user()
            if username is None:
                if settings['auth_enabled']:
                    raise NotAuthenticated
            else:
                permissions = rbac.get_user_permissions(username)
                if METHOD_PERMISSION_MAP[method] not in permissions:
                    raise ForbiddenMethod
