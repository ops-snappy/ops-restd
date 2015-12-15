#!/usr/bin/env python
#
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from opsrest.utils import utils
from opsrest import resource
from opslib import restparser
import declarativeconfig
import ovs
import json
import sys
import time
import traceback

import ovs.db.idl
import ovs.db.types
import types
import uuid


class RunConfigUtil():
    def __init__(self, idl, restschema):
        self.idl = idl
        self.restschema = restschema

    def get_config(self):
        return declarativeconfig.read(self.restschema, self.idl)

    def get_running_config(self):
        return declarativeconfig.read(self.restschema, self.idl)

    def write_config_to_db(self, data):
        return declarativeconfig.write_config_to_db(self.restschema,
                                                    self.idl, data)
