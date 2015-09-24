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
import string

import inflect
import xml.etree.ElementTree as ET

import ovs.dirs
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl

from tornado.log import app_log

# Global variables
inflect_engine = inflect.engine()

xml_tree = None


# Convert name into all lower case and into plural format
def normalizeName(name):
    lower_case = name.lower()
    # Assuming table names use underscore to link words
    words = string.split(lower_case, '_')
    words[-1] = inflect_engine.plural_noun(words[-1])
    return(string.join(words, '_'))


def extractColDesc(column_desc):
    if column_desc == None:
        column_desc = ""
    # Remove unecessary tags at the beginning of each description
    if column_desc != "":
        column_desc = " ".join(column_desc.split())
    reg =  '<column .*?>(.*)</column>'
    r = re.search(reg, column_desc)
    if r == None:
        return ""
    else:
        return str(r.group(1)).lstrip().rstrip()


class OVSColumn(object):
    """__init__() functions as the class constructor"""
    def __init__(self, table, col_name, type_, is_optional=True, mutable=True):
        self.name = col_name

        # is this column entry optional
        self.is_optional = is_optional

        # is this column modifiable after creation
        self.mutable = mutable

        base_key = type_.key
        base_value = type_.value

        # Possible values for keys only
        self.enum = base_key.enum

        self.type, self.rangeMin, self.rangeMax = self.process_type(base_key)

        self.value_type = None
        if base_value is not None:
            self.value_type, self.valueRangeMin, self.valueRangeMax = self.process_type(base_value)

        # The number of instances
        self.is_dict = self.value_type is not None
        self.is_list = (not self.is_dict) and type_.n_max > 1
        self.n_max = type_.n_max
        self.n_min = type_.n_min

        self.kvs = {}
        self.desc = self.parse_xml_desc(table.name, col_name, self.kvs)


    # Read the description for each column from XML source
    def parse_xml_desc(self, xmlTable, xmlColumn, kvs):
        columnDesc = ""
        for node in xml_tree.iter():
            if node.tag != 'table' or xmlTable != node.attrib['name']:
                continue

            for group in node.getchildren():
                for column in group.getchildren():
                    if column.tag != 'column' or xmlColumn != column.attrib['name']:
                        continue

                    if ('key' not in column.attrib):
                        columnDesc = ET.tostring(column, encoding='utf8', method='html')
                        continue

                    # When an attribute is of type string in schema file,
                    # it may have detailed structure information in its
                    # companion XML description.
                    kvs[column.attrib['key']] = {}
                    if ('type' in column.attrib):
                        typeData = json.loads(column.attrib['type'])
                        base = types.BaseType.from_json(typeData)
                        type, min, max = self.process_type(base)
                        kvs[column.attrib['key']]['type'] = type
                        kvs[column.attrib['key']]['rangeMin'] = min
                        kvs[column.attrib['key']]['rangeMax'] = max
                    key_desc = ET.tostring(column, encoding='utf8', method='html')
                    kvs[column.attrib['key']]['desc'] = extractColDesc(key_desc)
            break

        return extractColDesc(columnDesc)


    def process_type(self, base):
        type = base.type
        rangeMin = None
        rangeMax = None

        if type not in types.ATOMIC_TYPES or \
           type == types.VoidType or \
           type == types.UuidType:
            raise error.Error("unknown attribute type %s" % type)

        if type == types.StringType:
            rangeMin = base.min_length
            rangeMax = base.max_length
        elif type != types.BooleanType:
            rangeMin = base.min
            rangeMax = base.max

        return (type, rangeMin, rangeMax)

class OVSReference(object):
    """__init__() functions as the class constructor"""
    def __init__(self, type_, relation='reference', mutable=True):
        base_type = type_.key
        self.mutable = mutable

        # Name of the table being referenced
        if base_type.type != types.UuidType:
            # referenced table name must be in value part of KV pair
            base_type = type_.value
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
        self.is_plural = (type_.n_max != 1)
        self.n_max = type_.n_max
        self.n_min = type_.n_min

class OVSTable(object):
    """__init__() functions as the class constructor"""
    def __init__(self, name, is_root, is_many = True, indexes = ['uuid']):
        self.name = name
        self.plural_name = normalizeName(name)

        self.is_root = is_root

        # list of all column names
        self.columns = []

        # What is the name of the index column
        self.indexes = indexes


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

    def setIndexes(self, indexes):
        if len(indexes) > 0:
            self.indexes = indexes

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

        table = OVSTable(name, is_root, max_rows != 1)
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
                table.config[column_name] = OVSColumn(table, column_name, type_, is_optional, mutable)
            elif category == "status":
                table.status[column_name] = OVSColumn(table, column_name, type_, is_optional)
            elif category == "statistics":
                table.stats[column_name] = OVSColumn(table, column_name, type_, is_optional)
            elif category == "child":
                table.references[column_name] = OVSReference(type_, category)
            elif category == "parent":
                table.references[column_name] = OVSReference(type_, category)
            elif category == "reference":
                table.references[column_name] = OVSReference(type_, category, mutable)

        indexes_list = []
        for index_list in indexes_json:
            tmp_indexes = []
            for index in index_list:
                if index in table.references and table.references[index].relation == "parent":
                    continue
                tmp_indexes.append(index)
            if len(tmp_indexes) > 0:
                indexes_list = tmp_indexes
                break

        table.setIndexes(indexes_list)

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

        # tables that has the refereces to one table
        self.references_table_map = {}
        for table in self.ovs_tables:
            tables_references = get_references_tables(self, table)
            self.references_table_map[table] = tables_references

        # get a plural name map for all tables
        self.plural_name_map = {}
        for table in self.ovs_tables.itervalues():
            self.plural_name_map[table.plural_name] = table.name

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
                    if tableName not in tables[column.ref_table].children:
                        tables[column.ref_table].children.append(tableName)
                    table.parent = column.ref_table

        return RESTSchema(name, version, tables)


def get_references_tables(schema, ref_table):
    table_references = {}
    for table in schema.ovs_tables:
        columns = []
        for column_name, reference in schema.ovs_tables[table].references.iteritems():
            if reference.ref_table == ref_table:
                columns.append(column_name)
        if columns:
            table_references[table] = columns
    return table_references

def parseSchema(schemaFile, title=None, version=None):
    # Initialize a global variable here
    global xml_tree

    # Assume the companion XML file and schema file differ only in extension
    # for their names (.extschema vs .xml)
    xmlFile = schemaFile[:-len("extschema")] + "xml"
    with open(xmlFile, 'rt') as f:
        xml_tree = ET.parse(f)

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
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" % (column.type, column.rangeMin, column.rangeMax))
                print("key enum = %s" % column.enum)
                print("key kvs = %s" % column.kvs)
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" % (column.value_type, column.valueRangeMin, column.valueRangeMax))
            print("Status attributes: ")
            for column_name, column in table.status.iteritems():
                print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" % (column.type, column.rangeMin, column.rangeMax))
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" % (column.value_type, column.valueRangeMin, column.valueRangeMax))
            print("Stats attributes: ")
            for column_name, column in table.stats.iteritems():
                print("Col name = %s: %s" % (column_name, "plural" if column.is_list else "singular"))
                print("n_min = %d: n_max = %d" % (column.n_min, column.n_max))
                print("key type = %s: min = %s, max = %s" % (column.type, column.rangeMin, column.rangeMax))
                if column.value_type is not None:
                    print("value type = %s: min = %s, max = %s" % (column.value_type, column.valueRangeMin, column.valueRangeMax))
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
