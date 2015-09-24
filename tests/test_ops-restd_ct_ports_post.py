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


import pytest

from opsvsi.docker import *
from opsvsi.opsvsitest import *

import json
import httplib
import urllib

import request_test_utils
import port_test_utils

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

class myTopo(Topo):
    def build (self, hsts=0, sws=1, **_opts):
        self.hsts = hsts
        self.sws = sws
        switch = self.addSwitch("s1")


class CreatePortTest (OpsVsiTest):
    def setupNet (self):
        self.SWITCH_IP = ""
        self.PATH = "/rest/v1/system/ports"
        self.PORT_PATH = self.PATH + "/Port1"

        self.net = Mininet(topo=myTopo(hsts=NUM_HOSTS_PER_SWITCH,
                                       sws=NUM_OF_SWITCHES,
                                       hopts=self.getHostOpts(),
                                       sopts=self.getSwitchOpts()),
                                       switch=VsiOpenSwitch,
                                       host=None,
                                       link=None,
                                       controller=None,
                                       build=True)

    def setup_switch_ip(self):
        s1 = self.net.switches[0]
        self.SWITCH_IP = port_test_utils.get_switch_ip(s1)

    def create_port (self):
        info("\n########## Test to Validate Create Port ##########\n")
        status_code, response_data = request_test_utils.execute_request(self.PATH, "POST", json.dumps(port_test_utils.test_data), self.SWITCH_IP)
        assert status_code == httplib.CREATED, "Error creating a Port. Status code: %s Response data: %s " % (status_code, response_data)
        info("### Port Created. Status code is 201 CREATED  ###\n")

        # Verify data
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "GET", None, self.SWITCH_IP)
        assert status_code == httplib.OK, "Failed to query added Port"
        json_data = {}
        try:
            json_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"

        assert json_data["configuration"] == port_test_utils.test_data["configuration"], "Configuration data is not equal that posted data"
        info("### Configuration data validated ###\n")

        info("\n########## End Test to Validate Create Port ##########\n")

    def create_same_port (self):
        info("\n########## Test create same port ##########\n")
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "POST", json.dumps(port_test_utils.test_data), self.SWITCH_IP)
        assert status_code == httplib.BAD_REQUEST, "Validation failed, is not sending Bad Request error. Status code: %s" % status_code
        info("### Port not modified. Status code is 400 Bad Request  ###\n")

        info("\n########## End Test create same Port ##########\n")

class Test_CreatePort:
    def setup (self):
        pass

    def teardown (self):
        pass

    def setup_class (cls):
        Test_CreatePort.test_var = CreatePortTest()
        Test_CreatePort.test_var.setup_switch_ip()

    def teardown_class (cls):
        Test_CreatePort.test_var.net.stop()

    def setup_method (self, method):
        pass

    def teardown_method (self, method):
        pass

    def __del__ (self):
        del self.test_var

    def test_run (self):
        self.test_var.create_port()
        self.test_var.create_same_port()
