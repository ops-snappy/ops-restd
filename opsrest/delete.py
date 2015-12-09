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

from opsrest.constants import *
from opsrest.utils import utils
from opsrest import verify
from opsrest.transaction import OvsdbTransactionResult
from opsrest.exceptions import MethodNotAllowed, DataValidationFailed

import httplib
from tornado.log import app_log


def delete_resource(resource, schema, txn, idl):

    if resource.next is None:
        return None

    # get the last resource pair
    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    # Check for invalid resource deletioin
    if verify.verify_http_method(resource, schema, "DELETE") is False:
        raise MethodNotAllowed

    try:
        verified_data = verify.verify_data(None, resource, schema,
                                           idl, "DELETE")
    except DataValidationFailed as e:
        app_log.debug(e)
        raise e

    if resource.relation == OVSDB_SCHEMA_CHILD:

        if resource.next.row is None:
            raise MethodNotAllowed

        row = utils.delete_reference(resource.next, resource, schema, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        row = utils.get_row_from_resource(resource.next, idl)
        row.delete()

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        utils.delete_all_references(resource.next, schema, idl)

    result = txn.commit()
    return OvsdbTransactionResult(result)
