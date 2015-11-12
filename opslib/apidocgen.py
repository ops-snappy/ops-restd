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

import xml.etree.ElementTree as ET

import ovs.dirs
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl

from restparser import OVSColumn
from restparser import OVSReference
from restparser import OVSTable
from restparser import RESTSchema
from restparser import normalizeName
from restparser import parseSchema


def addCommonResponse(responses):
    response = {}
    response["description"] = "Unauthorized"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["401"] = response

    response = {}
    response["description"] = "Forbidden"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["403"] = response

    response = {}
    response["description"] = "Not found"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["404"] = response

    response = {}
    response["description"] = "Method not allowed"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["405"] = response

    response = {}
    response["description"] = "Internal server error"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["500"] = response

    response = {}
    response["description"] = "Service unavailable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["503"] = response


def addGetResponse(responses):
    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    addCommonResponse(responses)


def addPostResponse(responses):
    response = {}
    response["description"] = "Created"
    schema = {}
    schema["$ref"] = "#/definitions/Resource"
    response["schema"] = schema
    responses["201"] = response

    response = {}
    response["description"] = "Bad request"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["400"] = response

    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    response = {}
    response["description"] = "Unsupported media type"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["415"] = response

    addCommonResponse(responses)


def addPutResponse(responses):
    response = {}
    response["description"] = "OK"
    responses["200"] = response

    response = {}
    response["description"] = "Bad request"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["400"] = response

    response = {}
    response["description"] = "Not acceptable"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["406"] = response

    response = {}
    response["description"] = "Unsupported media type"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["415"] = response

    addCommonResponse(responses)


def addDeleteResponse(responses):
    response = {}
    response["description"] = "Resource deleted"
    responses["204"] = response

    addCommonResponse(responses)


#
# Pass in chain of parent resources on URI path
#
def genCoreParams(table, parent_plurality, parents, resource_name,
                  is_plural=True):
    depth = len(parent_plurality)
    plural = False

    params = []
    for level in range(depth):
        if parent_plurality[level]:
            param = {}
            param["name"] = "p"*(depth-level) + "id"
            param["in"] = "path"
            param["description"] = normalizeName(parents[level], plural) + " id"
            param["required"] = True
            param["type"] = "string"
            params.append(param)

    if is_plural:
        param = {}
        param["name"] = "id"
        param["in"] = "path"
        param["description"] = normalizeName(resource_name, plural) + " id"
        param["required"] = True
        param["type"] = "string"
        params.append(param)

    return params


def genGetParams(table, is_instance=False):
    params = []

    param = {}
    param["name"] = "depth"
    param["in"] = "query"
    param["description"] = "maximum depth of subresources included in result"
    param["required"] = False
    param["type"] = "string"
    params.append(param)

    if not is_instance:

        param = {}
        param["name"] = "sort"
        param["in"] = "query"
        param["description"] = "comma separated list of columns to sort " + \
                                "results by, add a - (dash) at the beginning " + \
                                "to make sort descending"
        param["required"] = False
        param["type"] = "string"
        params.append(param)

        param = {}
        param["name"] = "offset"
        param["in"] = "query"
        param["description"] = "index of the first element from the result" + \
                                " list to be returned"
        param["required"] = False
        param["type"] = "integer"
        params.append(param)

        param = {}
        param["name"] = "limit"
        param["in"] = "query"
        param["description"] = "number of elements to return from offset"
        param["required"] = False
        param["type"] = "integer"
        params.append(param)

        columns = {}
        columns.update(table.config)
        columns.update(table.stats)
        columns.update(table.status)
        columns.update(table.references)

        for column, data in columns.iteritems():
            if isinstance(data, OVSReference) or not data.is_dict:
                param = {}
                param["name"] = column
                param["in"] = "query"
                param["description"] = "filter '%s' by specified value" % column
                param["required"] = False

                if data.type == types.IntegerType:
                    param["type"] = "integer"
                elif data.type == types.RealType:
                    param["type"] = "real"
                else:
                    param["type"] = "string"

                params.append(param)

    return params


def genGetResource(table, parent_plurality, parents, resource_name, is_plural):
    op = {}
    op["summary"] = "Get operation"
    op["description"] = "Get a list of resources"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, parents,
                           resource_name, is_plural)

    get_params = genGetParams(table)
    if get_params:
        params.extend(get_params)

    if params:
        op["parameters"] = params

    responses = {}
    response = {}
    response["description"] = "OK"
    schema = {}
    schema["type"] = "array"
    item = {}
    item["description"] = "Resource URI"
    item["$ref"] = "#/definitions/Resource"
    schema["items"] = item
    schema["description"] = "A list of URIs"
    response["schema"] = schema
    responses["200"] = response

    addGetResponse(responses)
    op["responses"] = responses

    return op


def genPostResource(table, parent_plurality, parents, resource_name, is_plural):
    op = {}
    op["summary"] = "Post operation"
    op["description"] = "Create a new resource instance"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, parents,
                           resource_name, is_plural)
    param = {}
    param["name"] = "data"
    param["in"] = "body"
    param["description"] = "data"
    param["required"] = True

    if table.parent is None:
        # For referenced resource
        param["schema"] = {'$ref': "#/definitions/"+table.name
                           + "ConfigReferenced"}
    else:
        param["schema"] = {'$ref': "#/definitions/"+table.name+"ConfigOnly"}

    params.append(param)
    op["parameters"] = params

    responses = {}
    addPostResponse(responses)
    op["responses"] = responses

    return op


def genGetInstance(table, parent_plurality, parents, resource_name, is_plural):
    if table.config or table.status or table.stats:
        op = {}
        op["summary"] = "Get operation"
        op["description"] = "Get a set of attributes"
        op["tags"] = [table.name]

        params = genCoreParams(table, parent_plurality, parents,
                               resource_name, is_plural)
        param = {}
        param["name"] = "selector"
        param["in"] = "query"
        param["description"] = "select from config, status or stats, \
                                default to all"
        param["required"] = False
        param["type"] = "string"
        params.append(param)

        get_params = genGetParams(table, True)
        if get_params:
            params.extend(get_params)

        op["parameters"] = params

        responses = {}
        response = {}
        response["description"] = "OK"
        response["schema"] = {'$ref': "#/definitions/"+table.name+"All"}
        responses["200"] = response

        addGetResponse(responses)
        op["responses"] = responses

        return op


def genPutInstance(table, parent_plurality, parents, resource_name, is_plural):
    if table.config:
        op = {}
        op["summary"] = "Put operation"
        op["description"] = "Update configuration"
        op["tags"] = [table.name]

        params = genCoreParams(table, parent_plurality, parents,
                               resource_name, is_plural)
        param = {}
        param["name"] = "data"
        param["in"] = "body"
        param["description"] = "configuration"
        param["required"] = True
        param["schema"] = {'$ref': "#/definitions/"+table.name+"ConfigOnly"}
        params.append(param)
        op["parameters"] = params

        responses = {}
        addPutResponse(responses)
        op["responses"] = responses

        return op


def genDelInstance(table, parent_plurality, parents, resource_name, is_plural):
    op = {}
    op["summary"] = "Delete operation"
    op["description"] = "Delete a resource instance"
    op["tags"] = [table.name]

    params = genCoreParams(table, parent_plurality, parents,
                           resource_name, is_plural)
    if params:
        op["parameters"] = params

    responses = {}
    addDeleteResponse(responses)
    op["responses"] = responses

    return op


# Gets the correlated Swagger representation of primitive data types.
def getDataType(type):
    if type == types.IntegerType:
        return "integer"
    elif type == types.RealType:
        return "real"
    elif type == types.BooleanType:
        return "boolean"
    elif type == types.StringType:
        return "string"
    else:
        raise error.Error("Unexpected attribute type " + type)


# Generate definition for a given base type
def genBaseType(type, min, max, desc):
    item = {}
    item["type"] = getDataType(type)
    item["description"] = desc

    if type != types.BooleanType:
        if type == types.StringType:
            minStr = "minLength"
            maxStr = "maxLength"
        else:
            minStr = "minimum"
            maxStr = "maximum"

        if min is not None and min is not 0:
            item[minStr] = min
        if max is not None and max is not sys.maxint:
            item[maxStr] = max

    return item


# Generate definition for a column in a table
def genDefinition(table_name, col, definitions):
    properties = {}
    if col.is_dict and col.enum:
        # Key-Value type
        for key in col.enum:
            definition = {}
            # keys specified in schema file are all of string type
            definition["type"] = "string"
            properties[key] = definition

    if col.kvs:
        for key, detail in col.kvs.iteritems():
            if 'type' in detail.keys():
                type = detail['type']
            else:
                type = col.type
            if 'rangeMin' in detail.keys():
                min = detail['rangeMin']
            else:
                min = col.rangeMin
            if 'rangeMax' in detail.keys():
                max = detail['rangeMax']
            else:
                max = col.rangeMax
            if 'desc' in detail.keys():
                desc = detail['desc']
            else:
                desc = ""
            properties[key] = genBaseType(type, min, max, desc)

    if not properties and col.is_dict:
        # Some maps in the schema do not have keys defined (i.e. external_ids).
        # If keys are not defined, the type of the key (i.e. "string") should
        # be rendered as the key, and the type of the value (i.e. "string")
        # should be rendered as the value.
        key_type = getDataType(col.type)
        properties[key_type] = genBaseType(col.value_type,
                                           col.valueRangeMin,
                                           col.valueRangeMax,
                                           "Key-Value pair for " + col.name)

    if properties:
        definitions[table_name + "-" + col.name + "-KV"] = {"properties":
                                                            properties}

        sub = {}
        sub["$ref"] = "#/definitions/" + table_name + "-" + col.name + "-KV"
        sub["description"] = "Key-Value pairs for " + col.name
        return sub
    else:
        # simple attributes
        return genBaseType(col.type, col.rangeMin, col.rangeMax, col.desc)


def getDefinition(schema, table, definitions):
    properties = {}
    for colName, col in table.config.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    # references are included in configuration as well
    for col_name in table.references:
        if table.references[col_name].relation == "reference":
            child_name = table.references[col_name].ref_table
            child_table = schema.ovs_tables[child_name]

            sub = {}
            if table.references[col_name].is_plural:
                sub["type"] = "array"
                sub["description"] = "A list of " + child_table.name \
                                     + " references"
                item = {}
                item["$ref"] = "#/definitions/Resource"
                sub["items"] = item
            else:
                sub["$ref"] = "#/definitions/Resource"
                sub["description"] = "Reference of " + child_table.name
            properties[col_name] = sub

    definitions[table.name + "Config"] = {"properties": properties}

    # Construct full configuration definition to include subresources
    for col_name in table.children:
        if col_name in table.references:
            # regular references
            subtable_name = table.references[col_name].ref_table
        else:
            # child added by parent relationship
            subtable_name = col_name
        sub = {}
        sub["$ref"] = "#/definitions/" + subtable_name + "ConfigData"
        sub["description"] = "Referenced resource of " + subtable_name + " instances"
        properties[col_name] = sub

    # Special treat /system resource
    # Include referenced resources at the top level as children
    if table.name is "System":
        for subtable_name, subtable in schema.ovs_tables.iteritems():
            # Skipping those that are not top-level resources
            if subtable.parent is not None:
                continue
            # Skipping those that are not referenced
            if subtable_name not in schema.reference_map.values():
                continue

            sub = {}
            sub["$ref"] = "#/definitions/" + subtable.name + "ConfigData"
            sub["description"] = "Referenced resource of " + subtable.name + " instances"
            properties[subtable_name] = sub

    definitions[table.name + "ConfigFull"] = {"properties": properties}

    properties = {}
    definition = {}
    definition["type"] = "string"
    definition["description"] = table.name + " id"
    properties["id"] = definition
    definition = {}
    definition["$ref"] = "#/definitions/" + table.name + "ConfigFull"
    definition["description"] = "Configuration of " + table.name + " instance"
    properties["configuration"] = definition

    definitions[table.name + "ConfigInstance"] = {"properties": properties}

    properties = {}
    sub = {}
    if table.is_many:
        sub["type"] = "array"
        sub["description"] = "A list of " + table.name + " instances"
        item = {}
        item["$ref"] = "#/definitions/" + table.name + "ConfigInstance"
        sub["items"] = item
    else:
        sub["$ref"] = "#/definitions/" + table.name + "ConfigFull"
        sub["description"] = "Configuration of " + table.name
    properties[table.name] = sub

    definitions[table.name + "ConfigData"] = {"properties": properties}

    properties = {}
    for colName, col in table.status.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    definitions[table.name + "Status"] = {"properties": properties}

    properties = {}
    for colName, col in table.stats.iteritems():
        properties[colName] = genDefinition(table.name, col, definitions)
    definitions[table.name + "Stats"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Status"
    sub["description"] = "Status of " + table.name
    properties["status"] = sub
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Stats"
    sub["description"] = "Statistics of " + table.name
    properties["statistics"] = sub

    definitions[table.name + "All"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub

    definitions[table.name + "ConfigOnly"] = {"properties": properties}

    properties = {}
    sub = {}
    sub["$ref"] = "#/definitions/" + table.name + "Config"
    sub["description"] = "Configuration of " + table.name
    properties["configuration"] = sub

    sub = {}
    sub["type"] = "array"
    sub["description"] = "A list of reference points"
    item = {}
    item["$ref"] = "#/definitions/ReferencedBy"
    sub["items"] = item
    properties["referenced_by"] = sub

    definitions[table.name + "ConfigReferenced"] = {"properties": properties}


def genAPI(paths, definitions, schema, table, resource_name, parent,
           parents, parent_plurality):
    prefix = "/system"
    depth = len(parents)
    for index, ancestor in enumerate(parents):
        prefix = prefix + "/" + ancestor
        if parent_plurality[index]:
            idname = "{" + "p"*(depth - index) + "id}"
            prefix = prefix + "/" + idname

    # Parentless resources always have multiple instances
    if resource_name is None:
        # system table
        is_plural = False
    elif parent is None:
        is_plural = True
    elif resource_name not in parent.references:
        # parent relation always have multiple children
        is_plural = True
    else:
        is_plural = parent.references[resource_name].is_plural

    if resource_name is not None:
        path = prefix + "/" + resource_name
    else:
        path = prefix

    ops = {}
    if is_plural:
        op = genGetResource(table, parent_plurality, parents,
                            resource_name, False)
        if op is not None:
            ops["get"] = op
        op = genPostResource(table, parent_plurality, parents,
                             resource_name, False)
        if op is not None:
            ops["post"] = op
    else:
        op = genGetInstance(table, parent_plurality, parents,
                            resource_name, is_plural)
        if op is not None:
            ops["get"] = op
        op = genPutInstance(table, parent_plurality, parents,
                            resource_name, is_plural)
        if op is not None:
            ops["put"] = op
    paths[path] = ops

    if is_plural:
        path = path + "/{id}"
        ops = {}
        op = genGetInstance(table, parent_plurality, parents,
                            resource_name, is_plural)
        if op is not None:
            ops["get"] = op
        op = genPutInstance(table, parent_plurality, parents,
                            resource_name, is_plural)
        if op is not None:
            ops["put"] = op
        op = genDelInstance(table, parent_plurality, parents,
                            resource_name, is_plural)
        if op is not None:
            ops["delete"] = op
        paths[path] = ops

    getDefinition(schema, table, definitions)

    # Stop for system resource
    if resource_name is None:
        return

    # Recursive into next level resources
    for col_name in table.references:
        child_name = table.references[col_name].ref_table
        child_table = schema.ovs_tables[child_name]
        if col_name in table.children:
            # True child resources
            parents.append(resource_name)
            parent_plurality.append(is_plural)
            genAPI(paths, definitions, schema, child_table, col_name,
                   table, parents, parent_plurality)
            parents.pop()
            parent_plurality.pop()
        elif table.references[col_name].relation == "parent":
            continue
        else:
            # Referenced resources (no operation exposed)
            continue

    # For child resources declared with "parent" relationship
    for col_name in table.children:
        if col_name in table.references:
            # Processed already
            continue

        # Use plural form of the resource name in URI
        child_table = schema.ovs_tables[col_name]
        child_name = normalizeName(col_name)
        parents.append(resource_name)
        parent_plurality.append(is_plural)
        genAPI(paths, definitions, schema, child_table, child_name,
               table, parents, parent_plurality)
        parents.pop()
        parent_plurality.pop()


def getFullConfigDef(schema, definitions):
    properties = {}


    definitions["FullConfig"] = {"properties": properties}


def genFullConfigAPI(paths):
    path = "/system/full-configuration"

    ops = {}
    op = {}
    op["summary"] = "Get full configuration"
    op["description"] = "Fetch full declarative configuration"
    op["tags"] = ["FullConfiguration"]

    params = []
    param = {}
    param["name"] = "type"
    param["in"] = "query"
    param["description"] = "select from running or startup, \
                            default to running"
    param["required"] = False
    param["type"] = "string"
    params.append(param)
    op["parameters"] = params

    responses = {}
    response = {}
    response["description"] = "OK"
    response["schema"] = {'$ref': "#/definitions/SystemConfigFull"}
    responses["200"] = response

    addGetResponse(responses)
    op["responses"] = responses

    ops["get"] = op

    op = {}
    op["summary"] = "Update full configuration"
    op["description"] = "Update full declarative configuration"
    op["tags"] = ["FullConfiguration"]

    params = []
    param = {}
    param["name"] = "type"
    param["in"] = "query"
    param["description"] = "select from running or startup, \
                            default to running"
    param["required"] = False
    param["type"] = "string"
    params.append(param)
    param = {}
    param["name"] = "data"
    param["in"] = "body"
    param["description"] = "declarative configuration"
    param["required"] = True
    param["schema"] = {'$ref': "#/definitions/SystemConfigFull"}
    params.append(param)

    op["parameters"] = params

    responses = {}
    addPutResponse(responses)
    op["responses"] = responses

    ops["put"] = op

    paths[path] = ops


def genUserLogin(paths):
    path = "/login"

    ops = {}
    op = {}
    op["summary"] = "User login"
    op["description"] = "Use username and password to log user in"
    op["tags"] = ["User"]

    params = []
    param = {}
    param["name"] = "username"
    param["in"] = "query"
    param["description"] = "User name"
    param["required"] = True
    param["type"] = "string"
    params.append(param)
    param = {}
    param["name"] = "password"
    param["in"] = "body"
    param["description"] = "Password"
    param["required"] = True
    param["type"] = "string"
    params.append(param)

    op["parameters"] = params

    responses = {}
    response = {}
    response["description"] = "User logged in, cookie set"
    responses["201"] = response

    response = {}
    response["description"] = "Bad request"
    response["schema"] = {'$ref': "#/definitions/Error"}
    responses["400"] = response

    op["responses"] = responses

    ops["post"] = op

    paths[path] = ops


def getFullAPI(schema):
    api = {}
    api["swagger"] = "2.0"

    info = {}
    info["title"] = "OpenSwitch REST API"
    info["description"] = "REST interface for management plane"
    info["version"] = "1.0.0"
    api["info"] = info

    # by default, the REST implementation runs on the same host
    # at the same port as the Swagger UI
    api["host"] = ""
    # Should be changed to use https instead
    api["schemes"] = ["http"]
    api["basePath"] = "/rest/v1"
    api["produces"] = ["application/json"]

    paths = {}
    definitions = {}

    # Special treat /system resource
    systemTable = schema.ovs_tables["System"]
    parents = []
    parent_plurality = []
    genAPI(paths, definitions, schema, systemTable, None, None,
           parents, parent_plurality)

    # Top-level tables exposed in system table
    for col_name in systemTable.references:
        name = systemTable.references[col_name].ref_table
        table = schema.ovs_tables[name]

        if col_name in systemTable.children:
            # True child resources
            parents = []
            parent_plurality = []
            genAPI(paths, definitions, schema, table, col_name,
                   systemTable, parents, parent_plurality)
        else:
            # Referenced resources (no operation exposed)
            continue

    # Put referenced resources at the top level
    for table_name, table in schema.ovs_tables.iteritems():
        # Skipping those that are not top-level resources
        if table.parent is not None:
            continue
        # Skipping those that are not referenced
        if table_name not in schema.reference_map.values():
            continue

        parents = []
        parent_plurality = []
        # Use plural form of the resource name in the URI
        genAPI(paths, definitions, schema, table, table.plural_name,
               None, parents, parent_plurality)

    # Creating the access URL for declarative configuration manipulation
    genFullConfigAPI(paths)

    # Creating the login URL
    genUserLogin(paths)

    api["paths"] = paths

    properties = {}
    properties["message"] = {"type": "string"}
    definitions["Error"] = {"properties": properties}

    definition = {}
    definition["type"] = "string"
    definition["description"] = "Resource URI"
    definitions["Resource"] = definition

    properties = {}
    definition = {}
    definition["type"] = "string"
    definition["description"] = "URI of the resource making the reference"
    properties["uri"] = definition
    definition = {}
    definition["type"] = "array"
    definition["description"] = "A list of reference points, \
                                 can be empty for default"
    items = {}
    items["type"] = "string"
    definition["items"] = items
    properties["attributes"] = definition
    definitions["ReferencedBy"] = {"properties": properties}

    api["definitions"] = definitions

    return api


def docGen(schemaFile, xmlFile, title=None, version=None):
    schema = parseSchema(schemaFile)

    # Special treat System table as /system resource
    schema.ovs_tables["System"] = schema.ovs_tables.pop("System")
    schema.ovs_tables["System"].name = "System"

    api = getFullAPI(schema)
    return json.dumps(api, sort_keys=True, indent=4)


def usage():
    print """\
%(argv0)s: REST API documentation generator
Parse the meta schema file based on OVSDB schema together with its
accompanying XML documentation file to generate REST API YAML file
for rendering through swagger.
usage: %(argv0)s [OPTIONS] SCHEMA XML
where SCHEMA is an extended OVSDB schema in JSON format
  and XML is its accompanying documentation in XML format.

The following options are also available:
  --title=TITLE               use TITLE as title instead of schema name
  --version=VERSION           use VERSION to override
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

        if len(args) != 2:
            sys.stderr.write("Exactly 2 non-option arguments required "
                             "(use --help for help)\n")
            sys.exit(1)

        s = docGen(args[0], args[1], title, version)
        print s

    except error.Error, e:
        sys.stderr.write("%s\n" % e.msg)
        sys.exit(1)

# Local variables:
# mode: python
# End:
