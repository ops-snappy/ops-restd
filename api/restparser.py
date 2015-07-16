#!/usr/bin/env python
# Copyright (C) 2015 Hewlett-Packard Enterprise Development Company, L.P.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import getopt
import json
import sys
import re

import ovs.dirs
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl


class OVSColumn(object):
    """__init__() functions as the class constructor"""
    def __init__(self, type, is_optional=True, can_update = True):
        # Possible values
        self.enum = set([])

        base_type = type.key
        if base_type.type == types.IntegerType:
            # For type Integer only
            self.minInteger = base_type.min
            self.maxInteger = base_type.max
        elif base_type.type == types.RealType:
            # For type Real only
            self.minReal = base_type.min
            self.maxReal = base_type.max
        elif base_type.type == types.StringType:
            # For type string only
            self.minLength = base_type.min_length
            self.maxLength = base_type.max_length

        # The number of instances
        self.is_list = (type.n_max != 1)

        # is this column entry optional
        self.is_optional = is_optional

class OVSReference(object):
    """__init__() functions as the class constructor"""
    def __init__(self, type, relation = 'reference'):
        base_type = type.key

        # Name of the table being referenced
        self.ref_table = base_type.ref_table_name

        # Relationship of the referenced to the current table
        # one of child, parent or reference
        if relation == "child":
            self.relation = "child"
        elif relation == "parent":
            self.relation = "parent"
        elif relation == "reference":
            self.relation = "reference"
        else:
            raise error.Error("unknown table relationship %s" % relation)

        # The number of instances
        self.is_plural = (type.n_max != 1)


class OVSTable(object):
    """__init__() functions as the class constructor"""
    def __init__(self, name, is_many = True, index = 'name'):
        self.name = name

        # list of all column names
        self.columns = []

        # What is the name of the index column
        self.index = index

        # Is the table in plural form?
        self.is_many = is_many

        # Dictionary of configuration attributes (RW)
        # column name to OVSColumn object mapping
        self.config = {}

        # Dictionary of status attributes (Read-only)
        # column name to OVSColumn object mapping
        self.status = {}

        # Dictionary of statistics attributes (Read-only)
        # column name to OVSColumn object mapping
        self.stats = {}

        # Parent table name
        self.parent = None

        # Child table list
        self.children = []

        # List of table referenced
        # table name to OVSReference object mapping
        self.references = {}

    @staticmethod
    def from_json(json, name):
        parser = ovs.db.parser.Parser(json, "schema of table %s" % name)
        columns_json = parser.get("columns", [dict])
        mutable = parser.get_optional("mutable", [bool], True)
        is_root = parser.get_optional("isRoot", [bool], False)
        max_rows = parser.get_optional("maxRows", [int])
        indexes_json = parser.get_optional("indexes", [list], [])
        parser.finish()

        if max_rows == None:
            max_rows = sys.maxint
        elif max_rows <= 0:
            raise error.Error("maxRows must be at least 1", json)

        if not columns_json:
            raise error.Error("table must have at least one column", json)

        table = OVSTable(name, max_rows != 1)
        for column_name, column_json in columns_json.iteritems():
            parser = ovs.db.parser.Parser(column_json, "column %s" % name)
            category = parser.get_optional("category", [str, unicode])
            mutable = parser.get_optional("mutable", [bool], True)
            ephemeral = parser.get_optional("ephemeral", [bool], False)
            type_ = types.Type.from_json(parser.get("type", [dict, str, unicode]))
            parser.finish()

            is_optional = False
            if isinstance(column_json['type'], dict):
                if 'min' in column_json['type'] and column_json['type']['min'] == 0:
                    is_optional = True

            table.columns.append(column_name)
            if category == "configuration":
                table.config[column_name] = OVSColumn(type_, is_optional)
            elif category == "status":
                table.status[column_name] = OVSColumn(type_, is_optional)
            elif category == "statistics":
                table.stats[column_name] = OVSColumn(type_, is_optional)
            elif category == "child":
                table.references[column_name] = OVSReference(type_, category)
            elif category == "parent":
                table.references[column_name] = OVSReference(type_, category)
            elif category == "reference":
                table.references[column_name] = OVSReference(type_, category)

        return table


class RESTSchema(object):
    """Schema for REST interface from an OVSDB database."""

    def __init__(self, name, version, tables):
        self.name = name
        self.version = version
        # A dictionary of table name to OVSTable object mappings
        self.ovs_tables = tables

        # get a table name map for all references
        self.reference_map = {}
        for table in self.ovs_tables:
            for k,v in self.ovs_tables[table].references.iteritems():
                if k not in self.reference_map:
                    self.reference_map[k] = v.ref_table

    @staticmethod
    def from_json(json):
        parser = ovs.db.parser.Parser(json, "extended OVSDB schema")
        name = parser.get("name", ['id'])
        version = parser.get_optional("version", [str, unicode])
        tablesJson = parser.get("tables", [dict])
        parser.finish()

        if (version is not None and
            not re.match('[0-9]+\.[0-9]+\.[0-9]+$', version)):
            raise error.Error('schema version "%s" not in format x.y.z'
                              % version)

        tables = {}
        for tableName, tableJson in tablesJson.iteritems():
            tables[tableName] = OVSTable.from_json(tableJson, tableName)

        # Backfill the parent/child relationship info, mostly for
        # parent pointers which cannot be handled in place.
        for tableName, table in tables.iteritems():
            for columnName, column in table.references.iteritems():
                if column.relation == "child":
                    table.children.append(columnName)
                    if tables[column.ref_table].parent is None:
                        tables[column.ref_table].parent = tableName
                elif column.relation == "parent":
                    tables[column.ref_table].children.append(tableName)

        return RESTSchema(name, version, tables)


def parseSchema(schemaFile, title=None, version=None):
    schema = RESTSchema.from_json(ovs.json.from_file(schemaFile))

    if title == None:
        title = schema.name
    if version == None:
        version = "UNKNOWN"

    return schema


def usage():
    print """\
%(argv0)s: REST API meta schema file parser
Parse the meta schema file based on OVSDB schema to obtain category and
relation information for each REST resource.
usage: %(argv0)s [OPTIONS] SCHEMA
where SCHEMA is an extended OVSDB schema in JSON format.

The following options are also available:
  --title=TITLE               use TITLE as title instead of schema name
  --version=VERSION           use VERSION to display on document footer
  -h, --help                  display this help message\
""" % {'argv0': argv0}
    sys.exit(0)


if __name__ == "__main__":
    try:
        try:
            options, args = getopt.gnu_getopt(sys.argv[1:], 'h',
                                              ['title=', 'version=', 'help'])
        except getopt.GetoptError, geo:
            sys.stderr.write("%s: %s\n" % (argv0, geo.msg))
            sys.exit(1)

        title = None
        version = None
        for key, value in options:
            if key == '--title':
                title = value
            elif key == '--version':
                version = value
            elif key in ['-h', '--help']:
                usage()
            else:
                sys.exit(0)

        if len(args) != 1:
            sys.stderr.write("Exactly 1 non-option arguments required "
                             "(use --help for help)\n")
            sys.exit(1)

        schema = parseSchema(args[0])
        for table_name, table in schema.ovs_tables.iteritems():
            print("Table %s: " % table_name)
            print("Parent  = %s" % table.parent)
            print("Configuration attributes: ")
            for column_name, column in table.config.iteritems():
                print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
            print("Status attributes: ")
            for column_name, column in table.status.iteritems():
                print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
            print("Stats attributes: ")
            for column_name, column in table.stats.iteritems():
                print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
            print("Subresources: ")
            for column_name, column in table.references.iteritems():
                print("Col name = %s: %s, %s" % (column_name, column.relation, "plural" if column.is_plural else "singular"))
            print("\n")

    except error.Error, e:
        sys.stderr.write("%s\n" % e.msg)
        sys.exit(1)

# Local variables:
# mode: python
# End:
