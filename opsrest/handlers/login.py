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

from tornado import gen
from tornado.log import app_log

import httplib
import userauth

from opsrest.handlers import base


class LoginHandler(base.BaseHandler):

    # pass the application reference to the handlers
    def initialize(self, ref_object):
        pass

    # Overwrite BaseHandler's prepare, as LoginHandler does not
    # require authentication check prior to other operations
    def prepare(self):
        pass

    @gen.coroutine
    def get(self):

        app_log.debug("Executing Login GET...")

        is_authenticated = userauth.is_user_authenticated(self)
        if not is_authenticated:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
        else:
            self.set_status(httplib.OK)

        self.finish()

    @gen.coroutine
    def post(self):

        app_log.debug("Executing Login POST...")

        login_success = userauth.handle_user_login(self)
        if not login_success:
            self.set_status(httplib.UNAUTHORIZED)
            self.set_header("Link", "/login")
        else:
            self.set_status(httplib.OK)

        self.finish()
