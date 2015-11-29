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

'''
    A Resource uniquely identifies an OVSDB table entry.
      - Resource.table: name of the OVSDB table this resource belongs to
      - Resource.row: UUID of the row in which this resource is found
      - Resource.column: name of the column in the table under which
        this resource is found
'''


class Resource(object):
    def __init__(self, table, row=None, column=None,
                 index=None, relation=None):
        # these attriutes uniquely identify an entry in OVSDB table
        self.table = table
        self.row = row
        self.column = column

        # these attributes are used to build a relationship between various
        # resources identified using a URI. The URI is mapped to a linked list
        # of Resource objects
        self.index = index
        self.relation = relation
        self.next = None

    def get_allowed_methods(self, schema):
        # TODO: Process schema to determine allowed methods
        return ["DELETE", "GET", "OPTIONS", "POST", "PUT"]
