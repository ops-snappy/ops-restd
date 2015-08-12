from halonrest.constants import *
from halonrest.utils import utils
from halonrest.verify import *

def post_resource(data, resource, schema, txn, idl):

    # POST not allowed on Open_vSwitch table
    if resource is None or resource.next is None:
        return None

    while True:
        if resource.next.next is None:
            break
        resource = resource.next

    verified_data = verify_data(data, resource, schema, idl, 'POST')

    if verified_data is None:
        return None

    if resource.relation == OVSDB_SCHEMA_CHILD:

        # create new row, populate it with data, add it as a reference to the parent resource
        new_row = utils.setup_new_row(resource.next, data, schema, txn, idl)
        utils.add_reference(new_row, resource, None, idl)

    elif resource.relation == OVSDB_SCHEMA_REFERENCE:

        # create new row, populate it with data, add it as a reference to the resource that references it
        new_row = utils.setup_new_row(resource.next, data, schema, txn, idl)
        utils.add_reference(new_row, resource, None, idl)

    elif resource.relation == OVSDB_SCHEMA_BACK_REFERENCE:
        # row for a back referenced item contains the parent's reference in the verified data
        new_row = utils.setup_new_row(resource.next, data, schema, txn, idl)

    elif resource.relation == OVSDB_SCHEMA_TOP_LEVEL:
        new_row = utils.setup_new_row(resource.next, verified_data, schema, txn, idl)

        # a non-root table entry MUST be referenced elsewhere
        if 'references' in verified_data:
            for reference in verified_data['references']:
                utils.add_reference(new_row, reference, None, idl)

    return txn.commit()
