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
import re

# Local imports
import opsrest.utils.user_utils as user_utils

from opsrest.utils.utils import to_json_error
from opsrest.constants import DEFAULT_USER_GRP
from opsrest.custom.base_controller import OP_CREATE, OP_UPDATE

'''
Constants
'''
USERNAME_REGEX = r'^[a-z_][a-z0-9_-]*[$]?$'
REQUIRED_FIELD_MESSAGE = "Attribute is missing from request"


class UserValidator():

    def __validate_required_fields__(self, user, operation):
        """
        Validate required user fields
        Returns None when valid else returns error json dict
        """
        if operation == OP_CREATE and \
                (not hasattr(user.configuration, "username") or
                 user.configuration.username is None):
            validation_result = to_json_error(REQUIRED_FIELD_MESSAGE,
                                              None, "username")
            return validation_result

        if not hasattr(user.configuration, "password") or \
                user.configuration.password is None:
            validation_result = to_json_error(REQUIRED_FIELD_MESSAGE,
                                              None, "password")
            return validation_result
        return None

    def __validate_username__(self, username):
        """
        Validate username using a regular expression
        Returns None when valid else returns error json dict
        """
        re_result = re.match(USERNAME_REGEX, username)
        if not re_result or username != re_result.group():
            validation_result = to_json_error("Invalid username",
                                              None, "username")
            return validation_result

        return None

    def validate_create(self, user, current_user):
        """
        Validate required fields, username and if the user exists
        Returns None when valid else returns error json dict
        """
        validation_result = self.__validate_required_fields__(user, OP_CREATE)
        if validation_result is not None:
            return validation_result

        username = user.configuration.username
        validation_result = self.__validate_username__(username)
        if validation_result is not None:
            return validation_result

        if user_utils.user_exists(username):
            error_message = "User %s already exists" % username
            validation_result = to_json_error(error_message, None, None)
            return validation_result

    def validate_update(self, user, current_user):
        """
        Validates required fields, username, verifies if the user
        exists, verifies that the user is not root and that belongs to
        ovsdb_user group
        Returns None when valid else returns error json dict
        """
        validation_result = self.__validate_required_fields__(user, OP_UPDATE)
        if validation_result is not None:
            return validation_result

        username = user.configuration.username
        validation_result = self.__validate_username__(username)
        if validation_result is not None:
            return validation_result

        if user_utils.user_exists(username):
            # Avoid update a root user
            if username == "root":
                error_message = "Permission denied."\
                                "Cannot update the root user."
                validation_result = to_json_error(error_message, None, None)
                return validation_result
            # Avoid update users from another group
            if not user_utils.check_user_group(username, DEFAULT_USER_GRP):
                error_message = "Unknown user %s" % username
                validation_result = to_json_error(error_message, None, None)
                return validation_result
        else:
            error_message = "User %s doesn't exists." % username
            validation_result = to_json_error(error_message, None, None)
            return validation_result

        return None

    def validate_delete(self, username, current_user):
        """
        This functions verifies the following:
        User is not root
        User is not the current user
        User belongs to ovsdb_user group
        User is not the last user at ovsdb_group
        Returns None when valid else returns error json dict
        """
        # Avoid delete a root user
        if username == "root":
            error_message = "Permission denied." \
                            "Cannot remove the root user."
            validation_result = to_json_error(error_message, None, None)
            return validation_result

        # Avoid to delete the current user
        if username == current_user["username"]:
            error_message = "Permission denied." \
                            "Cannot remove the current user."
            validation_result = to_json_error(error_message, None, None)
            return validation_result

        # Avoid delete system users.
        if not user_utils.check_user_group(username, DEFAULT_USER_GRP):
            validation_result = to_json_error("Unknown user %s" % username,
                                              None, None)
            return validation_result

        # Check if deleting the last user from that group
        if user_utils.get_group_user_count(DEFAULT_USER_GRP) <= 1:
            validation_result = "Cannot delete the last user %s" % username
            validation_result = to_json_error(error_message, None, None)
            return validation_result

        return None
