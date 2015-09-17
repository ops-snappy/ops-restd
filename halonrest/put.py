from halonrest.constants import *
from halonrest.utils import utils
from halonrest.verify import *

from tornado.log import app_log

def put_resource(data, resource, schema, txn, idl):

    # Allow PUT operation on System table
    if resource is None:
        return None

    #We want to modify System table
    if resource.next is None:
        resource_update = resource
    else:
        while True:
            if resource.next.next is None:
                break
            resource = resource.next
        resource_update = resource.next

    app_log.debug("Resource = Table: %s Relation: %s Column: %s" % (resource.table, resource.relation, resource.column))
    if resource_update is not None:
        app_log.debug("Resource to Update = Table: %s " % resource_update.table)

    #Needs to be implemented
    verified_data = verify_data(data, resource, schema, idl, 'PUT')

    if verified_data is None:
        app_log.info("verification of data failed")
        return None

    if ERROR in verified_data:
        return verified_data

    #We want to modify System table
    if resource.next is None:
        updated_row = utils.update_row(resource, verified_data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_CHILD:
        '''
        Updating row from a child table
        Example:
        /system/bridges: PUT is allowed when modifying the bridge child table
        '''
        # update row, populate it with data, add it as a reference to the parent resource
        updated_row = utils.update_row(resource_update, verified_data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        '''
        In this case we only modify the data of the table, but we not modify
        the back reference.
        Example:
        /system/vrfs/vrf_default/bgp_routers: PUT allowed as we are modifying a back referenced resource
        '''
        # row for a back referenced item contains the parent's reference in the verified data
        updated_row = utils.update_row(resource_update, verified_data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        '''
        Updating row when we have a relationship with a top_level table
        Is not allowed to update the references in other tables.
        Example:
        /system/ports: PUT allowed as we are modifying Port to top level table
        '''
        updated_row = utils.update_row(resource_update, verified_data, schema, txn, idl)

    # TODO we need to query the modified object and return it
    return txn.commit()
