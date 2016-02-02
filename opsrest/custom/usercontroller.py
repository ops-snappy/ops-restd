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
import pwd
import crypt
import os
import base64

from tornado.log import app_log
from subprocess import call

# Local imports
import opsrest.utils.userutils as userutils

from opsrest.exceptions import\
    TransactionFailed, DataValidationFailed,\
    NotFound
from opsrest.custom.schemavalidator import SchemaValidator
from opsrest.custom.basecontroller import BaseController
from opsrest.custom.restobject import RestObject
from opsrest.custom.uservalidator import UserValidator
from opsrest.utils import getutils
from opsrest.constants import\
    REQUEST_TYPE_CREATE, REQUEST_TYPE_UPDATE,\
    OVSDB_SCHEMA_CONFIG, DEFAULT_USER_GRP, ERROR, \
    REST_QUERY_PARAM_OFFSET, REST_QUERY_PARAM_LIMIT


class UserController(BaseController):

    def __init__(self):
        self.schemavalidator = SchemaValidator("user_schema")
        self.validator = UserValidator()
        self.base_uri_path = "users"

    def __get_encrypted_password__(self, user):
        """
        Encrypts the user password using SHA-512 and
        base 64 salt (userid + random value)
        Returns encrypted password
        $6$somesalt$someveryverylongencryptedpasswd
        """
        user_id = userutils.get_user_id(user.configuration.username)
        salt_data = str(user_id) + os.urandom(16)
        salt = base64.b64encode(salt_data)
        encoded_password = crypt.crypt(user.configuration.password,
                                       "$6$%s$" % salt)
        return encoded_password

    def __fill_user_data__(self, user_data, selector):
        """
        Encapsulates user information inside RestObject instance
        Returns RestObject instance
        """
        # TODO create empty object using schema definition
        user_dict = RestObject.create_empty_json(selector)
        if OVSDB_SCHEMA_CONFIG in user_dict:
            user_dict[OVSDB_SCHEMA_CONFIG]["username"] = user_data.pw_name

        user_instance = RestObject.from_json(user_dict)
        return user_instance

    def __call_user_add__(self, username):
        cmd_result = call(["sudo", "useradd", username,
                           "-g", DEFAULT_USER_GRP])
        return cmd_result

    def __call_user_mod__(self, username, encoded_password):
        cmd_result = call(["sudo", "usermod", "-p",
                           encoded_password, username])
        return cmd_result

    def __call_user_del__(self, username):
        cmd_result = call(["sudo", "userdel", "-r", username], shell=False)
        return cmd_result

    def create(self, data, current_user):
        """
        Create user at ovsdb_users group
        Returns result dictionary
        """
        # Validate json
        self.schemavalidator.validate_json(data, REQUEST_TYPE_CREATE)

        # Validate user data
        user = RestObject.from_json(data)
        self.validator.validate_create(user, current_user)

        # Create user
        username = user.configuration.username
        result = {}
        try:
            """
            Add the user first because the user_id is going to be used as
            part of the salt
            """
            cmd_result_add = self.__call_user_add__(username)
            if cmd_result_add == 0:
                encoded_password = self.__get_encrypted_password__(user)
                cmd_result_mod = self.__call_user_mod__(username,
                                                        encoded_password)
                if cmd_result_mod == 0:
                    result = {"key": username}
                else:
                    # Try to delete the added user
                    cmd_result_del = self.__call_user_del__(username)
                    error = ""
                    if cmd_result_del == 0:
                        error = "User password not set, user deleted."
                    else:
                        error = "User password not set, failed deleting user."
                    raise TransactionFailed(error)
            else:
                error = "User %s not added" % username
                raise TransactionFailed(error)
        except KeyError:
            error = "An error ocurred creating user."
            raise TransactionFailed(error)

        return result

    def update(self, item_id, data, current_user):
        """
        Update user from ovsdb_users group
        Returns result dictionary
        """
        # Validate json
        self.schemavalidator.validate_json(data, REQUEST_TYPE_UPDATE)

        # Validate user data
        data[OVSDB_SCHEMA_CONFIG]["username"] = item_id
        user = RestObject.from_json(data)
        self.validator.validate_update(user, current_user)

        # Update user
        username = user.configuration.username
        encoded_password = self.__get_encrypted_password__(user)
        try:
            cmd_result = self.__call_user_mod__(username, encoded_password)
            if cmd_result != 0:
                error = "User %s not modified" % username
                raise TransactionFailed(error)
        except KeyError:
            error = "An error ocurred creating user"
            raise TransactionFailed(error)

    def delete(self, item_id, current_user):
        """
        Delete user from ovsdb_users group
        Returns result dictionary
        """
        username = item_id
        self.validator.validate_delete(username, current_user)

        cmd_result = self.__call_user_del__(username)
        result = {}
        if cmd_result != 0:
            if cmd_result == 8:
                error = "User %s currently logged in." % username
                raise TransactionFailed(error)
            else:
                error = "User %s not deleted." % username
                raise TransactionFailed(error)
        return result

    def get(self, item_id, current_user=None, selector=None, query_args=None):
        """
        Retrieve an specific user from ovsdb_users group
        Return user json representation
        """
        username = item_id
        if self.validator.check_user_exists(username):
            user_data = pwd.getpwnam(username)
            if user_data:
                user_instance = self.__fill_user_data__(user_data, selector)
                return user_instance.to_json()
        else:
            raise NotFound
        return None

    def get_all(self, current_user, selector=None, query_args=None):
        """
        Retrieve all users from ovsdb_users group
        Return users dictionary list
        """

        depth = getutils.get_depth_param(query_args)
        if isinstance(depth, dict) and ERROR in depth:
            raise DataValidationFailed(depth[ERROR]['message'])
        elif depth > 1:
            error = "Resource doesn't support depth parameter greater than 1"
            raise DataValidationFailed(error)

        sorting_args = []
        filter_args = {}
        pagination_args = {}
        offset = None
        limit = None

        schema = self.schemavalidator.validator.schema
        validation_result = getutils.validate_query_args(sorting_args,
                                                         filter_args,
                                                         pagination_args,
                                                         query_args,
                                                         schema, None,
                                                         selector, depth)

        if ERROR in validation_result:
            raise DataValidationFailed(validation_result[ERROR]['message'])

        if REST_QUERY_PARAM_OFFSET in pagination_args:
            offset = pagination_args[REST_QUERY_PARAM_OFFSET]
        if REST_QUERY_PARAM_LIMIT in pagination_args:
            limit = pagination_args[REST_QUERY_PARAM_LIMIT]

        app_log.debug("Sorting args: %s" % sorting_args)
        app_log.debug("Filter args: %s" % filter_args)
        app_log.debug("Limit % s" % limit)
        app_log.debug("Offset % s" % offset)

        group_id = userutils.get_group_id(DEFAULT_USER_GRP)
        all_users = []
        users = pwd.getpwall()
        for user_data in users:
            if user_data.pw_gid == group_id:
                user_instance = self.__fill_user_data__(user_data, selector)
                if user_instance:
                    if depth:
                        all_users.append(user_instance)
                    else:
                        username = user_instance.configuration.username
                        all_users.append(self.create_uri(username))

        # Convert to json
        if depth:
            user_list = RestObject.to_json_list(all_users)
            data = getutils.post_process_get_data(user_list, sorting_args,
                                                  filter_args, offset,
                                                  limit, schema, selector,
                                                  categorize=True)
            if ERROR in data:
                raise DataValidationFailed(data[ERROR]['message'])

            return data
        else:
            return all_users
