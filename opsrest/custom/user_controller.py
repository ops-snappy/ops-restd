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
import pwd
import crypt
import os
import base64

from subprocess import call

# Local imports
import opsrest.utils.user_utils as user_utils

from opsrest.utils.utils import to_json_error
from opsrest.constants import ERROR
from opsrest.custom.schema_validator import SchemaValidator
from opsrest.custom.base_controller import BaseController
from opsrest.custom.rest_object import RestObject
from opsrest.custom.user_validator import UserValidator
from opsrest.constants import OVSDB_SCHEMA_CONFIG, DEFAULT_USER_GRP
from opsrest.custom.base_controller import OP_CREATE, OP_UPDATE


class UserController(BaseController):

    def __init__(self):
        self.schema_validator = SchemaValidator("user_schema")
        self.validator = UserValidator()

    def __get_encrypted_password__(self, user):
        """
        Encrypts the user password using SHA-512 and
        base 64 salt (userid + random value)
        Returns encrypted password
        $6$somesalt$someveryverylongencryptedpasswd
        """
        user_id = user_utils.get_user_id(user.configuration.username)
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
        validation_result = self.schema_validator.validate_json(data,
                                                                OP_CREATE)
        if validation_result is not None:
            return {ERROR: validation_result}

        # Validate user
        user = RestObject.from_json(data)
        validation_result = self.validator.validate_create(user, current_user)
        if validation_result is not None:
            return {ERROR: validation_result}

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
                    message_error = ""
                    if cmd_result_del == 0:
                        message_error = "User password not set, user deleted."
                    else:
                        message_error = "User password not set, failed deleting "\
                                        "user."
                    error_json = to_json_error(message_error, None, None)
                    result = {ERROR: error_json}
            else:
                error_json = to_json_error("User %s not added" % username,
                                           None, None)
                result = {ERROR: error_json}
        except KeyError:
            error_json = to_json_error("An error ocurred", None, None)
            result = {ERROR: error_json}

        return result

    def update(self, item_id, data, current_user):
        """
        Update user from ovsdb_users group
        Returns result dictionary
        """
        # Validate json
        validation_result = self.schema_validator.validate_json(data,
                                                                OP_UPDATE)
        if validation_result is not None:
            return {ERROR: validation_result}
        # Validate user
        data[OVSDB_SCHEMA_CONFIG]["username"] = item_id
        user = RestObject.from_json(data)
        validation_result = self.validator.validate_update(user, current_user)
        if validation_result is not None:
            return {ERROR: validation_result}

        # Update user
        username = user.configuration.username
        encoded_password = self.__get_encrypted_password__(user)
        result = {}
        try:
            cmd_result = self.__call_user_mod__(username, encoded_password)
            if cmd_result != 0:
                error_json = to_json_error("User %s not modified" % username,
                                           None, None)
                result = {ERROR: error_json}
        except KeyError:
            error_json = to_json_error("An error ocurred", None, None)
            result = {ERROR: error_json}
        return result

    def delete(self, item_id, current_user):
        """
        Delete user from ovsdb_users group
        Returns result dictionary
        """
        username = item_id
        validation_result = self.validator.validate_delete(username,
                                                           current_user)
        if validation_result is not None:
            return {ERROR: validation_result}

        cmd_result = self.__call_user_del__(username)
        result = {}
        if cmd_result != 0:
            if cmd_result == 8:
                error_message = "User %s currently logged in." % username
                error_json = to_json_error(error_message, None, None)
                return {ERROR: error_json}
            else:
                error_json = to_json_error("User %s not deleted." % username,
                                           None, None)
                return {ERROR: error_json}
        return result

    def get_all(self, current_user, selector=None, query_args=None):
        """
        Retrieve all users from ovsdb_users group
        Return users dictionary list
        """
        group_id = user_utils.get_group_id(DEFAULT_USER_GRP)
        all_users = []
        users = pwd.getpwall()
        for user_data in users:
            if user_data.pw_gid == group_id:
                user_instance = self.__fill_user_data__(user_data, selector)
                if user_instance:
                    all_users.append(user_instance)

        result = RestObject.to_json_list(all_users)
        return result
