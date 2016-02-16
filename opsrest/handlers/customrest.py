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


# Third party imports
import json
import httplib
import re
from tornado import gen
from tornado.log import app_log

# Local imports
from opsrest.handlers.base import BaseHandler
from opsrest.exceptions import APIException, MethodNotAllowed, LengthRequired
from opsrest.constants import\
    HTTP_HEADER_CONTENT_TYPE, HTTP_CONTENT_TYPE_JSON,\
    REST_QUERY_PARAM_SELECTOR, HTTP_HEADER_CONTENT_LENGTH


class CustomRESTHandler(BaseHandler):

    # Pass the application reference and controller reference to the handlers
    def initialize(self, ref_object, controller_class):
        self.controller = controller_class()
        self.request.path = re.sub("/{2,}", "/", self.request.path).rstrip('/')

    # Parse the url and http params.
    def prepare(self):
        try:
            # Call parent's prepare to check authentication
            super(CustomRESTHandler, self).prepare()

            self.current_user = {}
            self.current_user["username"] = self.get_current_user()

            # If Match support
            match = self.process_if_match()
            if not match:
                self.finish()

        except APIException as e:
            self.on_exception(e)
            self.finish()

        except Exception, e:
            self.on_exception(e)
            self.finish()

    @gen.coroutine
    def get(self, resource_id=None):
        try:
            selector = self.get_query_argument(REST_QUERY_PARAM_SELECTOR, None)
            query_args = self.request.query_arguments
            result = None
            if resource_id:
                result = self.controller.get(resource_id, self.current_user,
                                             selector, query_args)
            else:
                result = self.controller.get_all(self.current_user,
                                                 selector, query_args)
            if result is not None:
                self.set_status(httplib.OK)
                self.set_header(HTTP_HEADER_CONTENT_TYPE,
                                HTTP_CONTENT_TYPE_JSON)
                self.write(json.dumps(result))
        except APIException as e:
            self.on_exception(e)
        except Exception, e:
            self.on_exception(e)
        self.finish()

    @gen.coroutine
    def post(self, resource_id=None):
        try:

            if HTTP_HEADER_CONTENT_LENGTH not in self.request.headers:
                raise LengthRequired

            if resource_id:
                raise MethodNotAllowed
            data = json.loads(self.request.body)
            result = self.controller.create(data, self.current_user)
            self.set_status(httplib.CREATED)
            if result is not None:
                new_uri = self.request.path + "/" + result["key"]
                self.set_header("Location", new_uri)

        except APIException as e:
            self.on_exception(e)

        except Exception, e:
            self.on_exception(e)

        self.finish()

    @gen.coroutine
    def put(self, resource_id=None):
        try:

            if HTTP_HEADER_CONTENT_LENGTH not in self.request.headers:
                raise LengthRequired

            data = json.loads(self.request.body)
            self.controller.update(resource_id, data,
                                   self.current_user)
            self.set_status(httplib.OK)

        except APIException as e:
            self.on_exception(e)

        except Exception, e:
            self.on_exception(e)

        self.finish()

    @gen.coroutine
    def patch(self, resource_id):
        try:

            if HTTP_HEADER_CONTENT_LENGTH not in self.request.headers:
                raise LengthRequired

            data = json.loads(self.request.body)
            self.controller.patch(resource_id, data, self.current_user)
            self.set_status(httplib.NO_CONTENT)

        except APIException as e:
            self.on_exception(e)

        except Exception, e:
            self.on_exception(e)

        self.finish()

    @gen.coroutine
    def delete(self, resource_id):
        try:
            self.controller.delete(resource_id, self.current_user)
            self.set_status(httplib.NO_CONTENT)

        except APIException as e:
            self.on_exception(e)

        except Exception, e:
            self.on_exception(e)

        self.finish()
