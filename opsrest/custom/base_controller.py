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

from opsrest.constants import\
    REST_VERSION_PATH, OVSDB_SCHEMA_SYSTEM_URI
from opsrest.exceptions import MethodNotAllowed


class BaseController():
    """
    BaseController base controller class with generic
    CRUD operations.
    """

    def __init__(self):
        self.base_uri_path = ""

    def create(self, data, current_user=None):
        raise MethodNotAllowed

    def update(self, item_id, data, current_user=None):
        raise MethodNotAllowed

    def delete(self, item_id, current_user=None):
        raise MethodNotAllowed

    def get(self, item_id, current_user=None, selector=None, query_args=None):
        raise MethodNotAllowed

    def get_all(self, current_user=None, selector=None, query_args=None):
        raise MethodNotAllowed

    def create_uri(self, item_id):
        return REST_VERSION_PATH + OVSDB_SCHEMA_SYSTEM_URI + "/" +\
            self.base_uri_path + "/" + item_id
