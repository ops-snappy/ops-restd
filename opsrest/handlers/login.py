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
from opsrest.exceptions import APIException, AuthenticationFailed
from opsrest.constants import USERNAME_KEY
from opsrest.utils.userutils import is_user_login_authorized


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
        try:
            app_log.debug("Executing Login GET...")

            is_authenticated = userauth.is_user_authenticated(self)
            if not is_authenticated:
                raise AuthenticationFailed
            else:
                self.set_status(httplib.OK)

        except APIException as e:
            self.on_exception(e)

        except Exception as e:
            self.on_exception(e)

        self.finish()

    @gen.coroutine
    def post(self):
        try:
            app_log.debug("Executing Login POST...")

            username = self.get_argument(USERNAME_KEY)

            if not is_user_login_authorized(username):
                raise AuthenticationFailed

            login_success = userauth.handle_user_login(self)
            if not login_success:
                raise AuthenticationFailed
            else:
                self.set_status(httplib.OK)

        except APIException as e:
            self.on_exception(e)

        except Exception as e:
            self.on_exception(e)

        self.finish()
