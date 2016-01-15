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

from opsrest.constants import OVSDB_SCHEMA_CONFIG, ERROR
from opsrest.patch import create_patch, apply_patch
from opsrest.utils.utils import to_json_error
from opsrest.exceptions import APIException

from tornado.log import app_log

OP_CREATE = 1,
OP_UPDATE = 2,
OP_DELETE = 3,
OP_GET = 4,
OP_GET_ALL = 5
OP_PATCH = 6

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
        raise NotImplementedError

    def get_all(self, current_user=None, selector=None, query_args=None):
        pass

    def patch(self, item_id, data, current_user=None):

        result = {}

        # TODO change JSON error objects to APIException
        try:
            # Get the resource's JSON to patch
            resource_json = self.get(item_id, current_user,
                                     OVSDB_SCHEMA_CONFIG)

            if resource_json is None:
                return None
            elif isinstance(resource_json, dict) and ERROR in resource_json:
                return resource_json

            # Create and verify patch
            (patch, needs_update) = create_patch(data)

            # Apply patch to the resource's JSON
            patched_resource = apply_patch(patch, resource_json)

        # In case the resource doesn't implement GET
        except NotImplementedError:
            error_json = to_json_error("PATCH not allowed on resource")
            return {ERROR: error_json}

        # Anything PATCH-related will throw APIException
        except APIException as e:
            app_log.debug(e)
            error_json = to_json_error(str(e))
            return {ERROR: error_json}

        # Update resource only if needed, since a valid
        # patch can contain PATCH_OP_TEST operations
        # only, which do not modify the resource
        if needs_update:
            result = self.update(item_id, patched_resource, current_user)

        return result
