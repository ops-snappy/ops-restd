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
import re

# Local imports
import opsrest.utils.userutils as userutils
from opsrest.constants import\
    REQUEST_TYPE_CREATE, REQUEST_TYPE_UPDATE,\
    DEFAULT_USER_GRP
from opsrest.exceptions import DataValidationFailed, NotFound

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
        if operation == REQUEST_TYPE_CREATE and \
                (not hasattr(user.configuration, "username") or
                 user.configuration.username is None):
            error = "Attribute username is required"
            raise DataValidationFailed(error)

        if not hasattr(user.configuration, "password") or \
                user.configuration.password is None:
            error = "Attribute password is required"
            raise DataValidationFailed(error)

    def __validate_username__(self, username):
        """
        Validate username using a regular expression
        Returns None when valid else returns error json dict
        """
        re_result = re.match(USERNAME_REGEX, username)
        if not re_result or username != re_result.group():
            error = "Invalid username"
            raise DataValidationFailed(error)

    def validate_create(self, user, current_user):
        """
        Validate required fields, username and if the user exists
        Returns None when valid else returns error json dict
        """
        self.__validate_required_fields__(user, REQUEST_TYPE_CREATE)

        username = user.configuration.username
        self.__validate_username__(username)

        if self.check_user_exists(username):
            error = "User %s already exists" % username
            raise DataValidationFailed(error)

    def validate_update(self, user, current_user):
        """
        Validates required fields, username, verifies if the user
        exists, verifies that the user is not root and that belongs to
        ovsdb_user group
        Returns None when valid else returns error json dict
        """
        self.__validate_required_fields__(user, REQUEST_TYPE_UPDATE)

        username = user.configuration.username

        if self.check_user_exists(username):
            # Validate Username
            self.__validate_username__(username)
            # Avoid update a root user
            if username == "root":
                error = "Permission denied. Cannot update the root user."
                raise DataValidationFailed(error)
        else:
            raise NotFound

    def validate_delete(self, username, current_user):
        """
        This functions verifies the following:
        User is not root
        User is not the current user
        User belongs to ovsdb_user group
        User is not the last user at ovsdb_group
        Returns None when valid else returns error json dict
        """
        if self.check_user_exists(username):
            # Avoid delete a root user
            if username == "root":
                error = "Permission denied. Cannot remove the root user."
                raise DataValidationFailed(error)

            # Avoid to delete the current user
            if username == current_user["username"]:
                error = "Permission denied. Cannot remove the current user."
                raise DataValidationFailed(error)

            # Check if deleting the last user from that group
            if userutils.get_group_user_count(DEFAULT_USER_GRP) <= 1:
                error = "Cannot delete the last user %s" % username
                raise DataValidationFailed(error)
        else:
            raise NotFound

    def check_user_exists(self, username):
        if username and userutils.user_exists(username) and\
                userutils.check_user_group(username, DEFAULT_USER_GRP):
            return True
        return False
