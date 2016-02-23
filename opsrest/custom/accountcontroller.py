# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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
import crypt
import os
import base64
import userauth
import rbac

from tornado.log import app_log
from subprocess import call

# Local imports
import opsrest.utils.userutils as userutils

from opsrest.exceptions import TransactionFailed, \
    AuthenticationFailed, NotAuthenticated
from opsrest.custom.schemavalidator import SchemaValidator
from opsrest.custom.basecontroller import BaseController
from opsrest.custom.restobject import RestObject
from opsrest.custom.accountvalidator import AccountValidator
from opsrest.constants import REQUEST_TYPE_UPDATE, \
    USERNAME_KEY, OLD_PASSWORD_KEY, USER_ROLE_KEY, \
    USER_PERMISSIONS_KEY, OVSDB_SCHEMA_STATUS


class AccountController(BaseController):

    def __init__(self):
        self.schemavalidator = SchemaValidator("account_schema")
        self.validator = AccountValidator()
        self.base_uri_path = "account"

    def __get_encrypted_password__(self, username, password):
        """
        Encrypts the user passwords using SHA-512 and
        base 64 salt (userid + random value)
        Returns encrypted password
        $6$somesalt$someveryverylongencryptedpasswd
        """

        user_id = userutils.get_user_id(username)

        salt_data = str(user_id) + os.urandom(16)
        salt = base64.b64encode(salt_data)

        encoded_password = crypt.crypt(password, "$6$%s$" % salt)

        return encoded_password

    def __change_user_password__(self, username, encoded_new_passwd):
        # TODO change password using a different method after hardening
        cmd_result = call(["sudo", "usermod", "-p",
                           encoded_new_passwd, username])
        return cmd_result

    def __get_username__(self, current_user):
        if USERNAME_KEY in current_user and \
                current_user[USERNAME_KEY] is not None:
            return current_user[USERNAME_KEY]
        else:
            raise NotAuthenticated("No user currently logged in")

    def __verify_old_password__(self, username, password):
        req = DummyRequestHandler()
        req.set_argument(USERNAME_KEY, username)
        req.set_argument(OLD_PASSWORD_KEY, password)

        # Simulate a login with a dummy RequestHandler
        # to verify the user's password
        if not userauth.handle_user_login(req):
            raise AuthenticationFailed("Wrong username or password")

    def update(self, item_id, data, current_user):
        """
        Update user from ops_netop group
        Returns result dictionary
        """

        app_log.info("Updating account info...")

        username = self.__get_username__(current_user)

        # Validate json
        self.schemavalidator.validate_json(data, REQUEST_TYPE_UPDATE)

        # Validate user data
        account_info = RestObject.from_json(data)
        self.validator.validate_update(username, account_info)

        # Verify user's current password
        self.__verify_old_password__(username,
                                     account_info.configuration.password)

        # Encode new password
        unencoded_passwd = account_info.configuration.new_password
        encoded_new_passwd = self.__get_encrypted_password__(username,
                                                             unencoded_passwd)
        try:
            cmd_result = self.__change_user_password__(username,
                                                       encoded_new_passwd)
            if cmd_result != 0:
                error = "Unable to change password for user '%s'" % username
                raise TransactionFailed(error)
        except KeyError:
            error = "An error occurred while updating account information"
            raise TransactionFailed(error)

    def get_all(self, current_user, selector=None, query_args=None):
        """
        Get current user's information
        Returns dictionary with user's role and permissions
        """

        app_log.info("Querying account info...")

        username = self.__get_username__(current_user)

        role = rbac.get_user_role(username)
        permissions = rbac.get_user_permissions(username)

        account_info = RestObject.create_empty_json()
        account_info[OVSDB_SCHEMA_STATUS][USER_ROLE_KEY] = role
        account_info[OVSDB_SCHEMA_STATUS][USER_PERMISSIONS_KEY] = permissions

        return account_info


class DummyRequestHandler:

    '''
    ops-aaa-utils' userauth is tightly coupled with Tornado.
    This dummy class is used to check the user's old password
    by simulating a login with a dummy object that resembles
    a Tornado RequestHandler, as expected by userauth. This
    "hack" will be removed in the future when proper RBAC
    support is present (e.g. by using a password server).
    '''

    def __init__(self):
        self.__arguments = {}

    def get_argument(self, argument):
        if argument in self.__arguments:
            return self.__arguments[argument]
        else:
            return None

    def set_argument(self, argument, value):
        self.__arguments[argument] = value

    def set_secure_cookie(self, name, value):
        pass
