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


# Third party imports
import json
import httplib
import re
import userauth
from tornado import gen
from tornado.log import app_log

# Local imports
from opsrest.handlers.base import BaseHandler
from opsrest.settings import settings
from opsrest.utils.utils import to_json
from opsrest.utils.utils import to_json_error
from opsrest.constants import\
    ERROR,\
    HTTP_HEADER_CONTENT_TYPE,\
    HTTP_CONTENT_TYPE_JSON,\
    REST_QUERY_PARAM_SELECTOR


class CustomRESTHandler(BaseHandler):

    # Pass the application reference and controller reference to the handlers
    def initialize(self, ref_object, controller_class):
        self.controller = controller_class()
        self.request.path = re.sub("/{2,}", "/", self.request.path).rstrip('/')

    # Parse the url and http params.
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
            self.current_user = {}
            self.current_user["username"] = self.get_current_user()

    def on_finish(self):
        app_log.debug("Finished handling of request from %s",
                      self.request.remote_ip)

    @gen.coroutine
    def get(self, resource_id=None):
        try:
            query_arguments = self.request.query_arguments
            selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)
            if resource_id:
                result = self.controller.get(resource_id, self.current_user,
                                             selector, query_arguments)
            else:
                result = self.controller.get_all(self.current_user,
                                                 selector, query_arguments)
            if result is None:
                self.set_status(httplib.NOT_FOUND)
            elif self.successful_request(result):
                self.set_status(httplib.OK)
                self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
                self.write(json.dumps(result))
        except Exception, e:
                app_log.debug("Unexpected exception: %s", e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
        self.finish()

    @gen.coroutine
    def post(self, resource_id=None):
        if resource_id:
            self.set_status(httplib.NOT_FOUND)
        else:
            try:
                data = json.loads(self.request.body)
                result = self.controller.create(data, self.current_user)
                if result is None:
                    self.set_status(httplib.NOT_FOUND)
                elif self.successful_request(result):
                    self.set_status(httplib.CREATED)
                    new_uri = self.request.path + "/" + result["key"]
                    self.set_header("Location", new_uri)
            except ValueError, e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(to_json_error(e))
            except Exception, e:
                app_log.debug("Unexpected exception: %s", e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
        self.finish()

    @gen.coroutine
    def put(self, resource_id):
        if resource_id:
            try:
                data = json.loads(self.request.body)
                result = self.controller.update(resource_id,
                                                data,
                                                self.current_user)
                if result is None:
                    self.set_status(httplib.NOT_FOUND)
                elif self.successful_request(result):
                    self.set_status(httplib.OK)
            except ValueError, e:
                self.set_status(httplib.BAD_REQUEST)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(to_json_error(e))
            except Exception, e:
                app_log.debug("Unexpected exception: %s", e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
        else:
            self.set_status(httplib.NOT_FOUND)
        self.finish()

    @gen.coroutine
    def delete(self, resource_id):
        if resource_id:
            try:
                result = self.controller.delete(resource_id, self.current_user)
                if result is None:
                    self.set_status(httplib.NOT_FOUND)
                elif self.successful_request(result):
                    self.set_status(httplib.NO_CONTENT)
            except Exception, e:
                app_log.debug("Unexpected exception: %s", e)
                self.set_status(httplib.INTERNAL_SERVER_ERROR)
        else:
            self.set_status(httplib.NOT_FOUND)
        self.finish()

    def successful_request(self, result):
        if isinstance(result, dict) and ERROR in result:
            self.set_status(httplib.BAD_REQUEST)
            self.set_header(HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON)
            self.write(to_json(result))
            return False
        else:
            return True
