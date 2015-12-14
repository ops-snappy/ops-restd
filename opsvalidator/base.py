from tornado.log import app_log
from opsrest import constants


class ValidationArgs(object):
    """
    Arguments from the validation framework used by validators
    """
    def __init__(self, idl, schema, resource, data):
        # General arguments
        self.idl = idl
        self.schema = schema
        self.data = data

        # Data will be none in a DELETE case.
        if data is not None:
            self.config_data = data[constants.OVSDB_SCHEMA_CONFIG]
        else:
            self.config_data = None

        # Arguments specific to parent/child resources
        if resource.next is not None:
            self.p_resource = resource
            self.p_resource_schema = schema.ovs_tables[self.p_resource.table]
            self.p_resource_idl_table = idl.tables[self.p_resource.table]
            self.p_resource_row = \
                self.p_resource_idl_table.rows[self.p_resource.row]

            self.resource = resource.next
        else:
            self.resource = resource

        self.resource_schema = schema.ovs_tables[self.resource.table]
        self.resource_idl_table = idl.tables[self.resource.table]

        # New resources will not have an associated row
        if self.resource.row is not None:
            self.resource_row =\
                self.resource_idl_table.rows[self.resource.row]
        else:
            self.resource_row = None


class BaseValidator(object):
    """
    Base class for validators to provide as a hook and registration
    mechanism. Derived classes will be registered as validators.

    resource: Used for registering a validator with a resource/table name.
              It is used for validator lookup. Derived classes must define
              a value for proper registration/lookup.
    """
    resource = ""

    def type(self):
        return self.__class__.__name__

    def validate_create(self, validation_args):
        app_log.debug("validate_create not implemented for " + self.type())

    def validate_update(self, validation_args):
        app_log.debug("validate_update not implemented for " + self.type())

    def validate_delete(self, validation_args):
        app_log.debug("validate_delete not implemented for " + self.type())
