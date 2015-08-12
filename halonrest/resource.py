'''
    A Resource uniquely identifies an OVSDB table entry.
      - Resource.table: name of the OVSDB table that this resource belongs to
      - Resource.row: UUID of the row in which this resource is found
      - Resource.column: name of the column in the table under which this resource is found
'''
class Resource(object):
    def __init__(self, table, row=None, column=None, index=None, relation=None):
        # these attriutes uniquely identify an entry in OVSDB table
        self.table = table
        self.row = None
        self.column = None

        # these attributes are used to build a relationship between various
        # resources identified using a URI. The URI is mapped to a linked list
        # of Resource objects
        self.index = None
        self.relation = None
        self.next = None
