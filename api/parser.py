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
import json

import ovs.dirs
from ovs.db import error
from ovs.db import types
import ovs.util
import ovs.daemon
import ovs.db.idl
import ovs.unixctl
import ovs.unixctl.server
import ovs.vlog


class OVSColumn(object):
    """__init__() functions as the class constructor"""
    def __init__(self, type, can_update = True):
        # Possible values
        self.enum = set([])

        # For type Integer only
        self.minInteger = None
        self.maxInteger = None

        # For type Real only
        self.minReal = None
        self.maxReal = None

        # For type string only
        self.minLength = None
        self.maxLength = None

        # The number of instances
        self.is_list = False


class OVSReference(object):
    """__init__() functions as the class constructor"""
    def __init__(self, table, relation = 'reference'):
        # Name of the table being referenced
        self.table = table

        # Relationship of the referenced to the current table
        # one of child, parent or reference
        self.relation = relation

        # The number of instances
        self.is_plural = False


class OVSTable(object):
    """__init__() functions as the class constructor"""
    def __init__(self, index = 'name', is_many = True):
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

        # List of table referenced
        # table name to OVSReference object mapping
        self.references = {}


# A doctionary of table name to OVSTable object mappings
ovs_tables = {}
