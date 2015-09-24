from opsrest.constants import *
from opsrest.utils import utils
from opsrest.verify import *

from tornado.log import app_log

'''
/system/bridges: POST allowed as we are adding a new Bridge to a child table
/system/ports: POST allowed as we are adding a new Port to top level table
/system/vrfs/vrf_default/bgp_routers: POST allowed as we are adding a back referenced resource
/system/bridges/bridge_normal/ports: POST NOT allowed as we are attemtping to add a Port as a reference on bridge
'''
def post_resource(data, resource, schema, txn, idl):



    # POST not allowed on System table
    if resource is None or resource.next is None:
        app_log.info("POST is not allowed on System table")
        return None

    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    verified_data = verify_data(data, resource, schema, idl, 'POST')

    if verified_data is None:
        app_log.info("verification of data failed")
        return None

    if ERROR in verified_data:
        return verified_data

    app_log.debug("adding new resource to " + resource.next.table + " table")
    if resource.relation == OVSDB_SCHEMA_CHILD:
        # create new row, populate it with data, add it as a reference to the parent resource
        new_row = utils.setup_new_row(resource.next, verified_data, schema, txn, idl)
        utils.add_reference(new_row, resource, None, idl)

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        # row for a back referenced item contains the parent's reference in the verified data
        new_row = utils.setup_new_row(resource.next, verified_data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        new_row = utils.setup_new_row(resource.next, verified_data, schema, txn, idl)

        # a non-root table entry MUST be referenced elsewhere
        if OVSDB_SCHEMA_REFERENCED_BY in verified_data:
            for reference in verified_data[OVSDB_SCHEMA_REFERENCED_BY]:
                utils.add_reference(new_row, reference, None, idl)

    return txn.commit()
