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

OP_CREATE = 1,
OP_UPDATE = 2,
OP_DELETE = 3,
OP_GET = 4,
OP_GET_ALL = 5


class BaseController():
    """
    BaseController base controller class with generic
    CRUD operations.
    """

    def create(self, data, current_user=None):
        pass

    def update(self, item_id, data, current_user=None):
        pass

    def delete(self, item_id, current_user=None):
        pass

    def get(self, item_id, current_user=None, selector=None, query_args=None):
        pass

    def get_all(self, current_user=None, selector=None, query_args=None):
        pass
