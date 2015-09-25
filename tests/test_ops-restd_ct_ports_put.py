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


class ModifyPortTest (OpsVsiTest):
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

    def modify_port (self):
        info("\n########## Test to Validate Modify Port ##########\n")

        # 1 - Query port
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "GET", None, self.SWITCH_IP)
        assert status_code == httplib.OK, "Port %s doesn't exists" % self.PORT_PATH

        pre_put_get_data = {}
        try:
            pre_put_get_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"
        info("### Query Port %s  ###\n" % response_data)

        # 2 - Modify data
        put_data = pre_put_get_data["configuration"]
        put_data["interfaces"] = ["/rest/v1/system/interfaces/1", "/rest/v1/system/interfaces/2"]
        put_data["trunks"] = [400]
        put_data["ip4_address_secondary"] = ["192.168.0.2"]
        put_data["lacp"] = "passive"
        put_data["bond_mode"] = "l3-src-dst-hash"
        put_data["tag"] = 600
        put_data["vlan_mode"] = "access"
        put_data["ip6_address"] = "2001:0db8:85a3:0000:0000:8a2e:0370:8225"
        put_data["external_ids"] = {"extid2key": "extid2value"}
        put_data["bond_options"] = {"key2": "value2"}
        put_data["mac"] = "01:23:45:63:90:ab"
        put_data["other_config"] = {"cfg-2key": "cfg2val"}
        put_data["bond_active_slave"] = "slave1"
        put_data["ip6_address_secondary"] = ["2001:0db8:85a3:0000:0000:8a2e:0370:7224"]
        put_data["vlan_options"] = {"opt1key": "opt3val"}
        put_data["ip4_address"] = "192.168.1.2"

        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "PUT", json.dumps({'configuration': put_data}), self.SWITCH_IP)
        assert status_code == httplib.OK, "Error modifying a Port. Status code: %s Response data: %s " % (status_code, response_data)
        info("### Port Modified. Status code 200 OK  ###\n")

        # 3 - Verify Modified data
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "GET", None, self.SWITCH_IP)
        assert status_code == httplib.OK, "Port %s doesn't exists" % self.PORT_PATH
        post_put_data = {}
        try:
            post_put_get_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"

        post_put_data = post_put_get_data["configuration"]

        assert port_test_utils.compare_dict(post_put_data, put_data), "Configuration data is not equal that posted data"
        info("### Configuration data validated %s ###\n" % response_data)

        info("\n########## End Test to Validate Modify Port ##########\n")

    def verify_port_name_modification_not_applied (self):
        info("\n########## Test to Validate: Port name modification not applied ##########\n")

        # 1 - Query port
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "GET", None, self.SWITCH_IP)
        assert status_code == httplib.OK, "Port %s doesn't exists" % self.PORT_PATH

        pre_put_get_data = {}
        try:
            pre_put_get_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"
        info("### Query Port %s  ###\n" % response_data)

        # 2 - Modify data
        put_data = pre_put_get_data["configuration"]
        expected_value = put_data["name"]
        put_data["name"] = "Port2"

        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "PUT", json.dumps({'configuration': put_data}) , self.SWITCH_IP)
        assert status_code == httplib.OK, "Error modifying a Port. Status code: %s Response data: %s " % (status_code, response_data)
        info("### Port Modified. Status code 200 OK  ###\n")

        # 3 - Verify Port name is not modified
        status_code, response_data = request_test_utils.execute_request(self.PORT_PATH, "GET", None, self.SWITCH_IP)
        assert status_code == httplib.OK, "Port %s doesn't exists" % self.PORT_PATH
        post_put_get_data = {}
        try:
            post_put_get_data = json.loads(response_data)
        except:
            assert False, "Malformed JSON"

        post_put_data = post_put_get_data["configuration"]

        assert expected_value == post_put_data["name"], "Port name was modified"
        info("### Configuration data validated %s ###\n" % response_data)

        info("\n########## End Test to Validate: Port name modification not applied ##########\n")


class Test_ModifyPort:
    def setup (self):
        pass

    def teardown (self):
        pass

    def setup_class (cls):
        Test_ModifyPort.test_var = ModifyPortTest()
        Test_ModifyPort.test_var.setup_switch_ip()
        # Add a test port
        port_test_utils.create_test_port(Test_ModifyPort.test_var.SWITCH_IP)

    def teardown_class (cls):
        Test_ModifyPort.test_var.net.stop()

    def setup_method (self, method):
        pass

    def teardown_method (self, method):
        pass

    def __del__ (self):
        del self.test_var

    def test_run (self):
        self.test_var.modify_port()
        self.test_var.verify_port_name_modification_not_applied()
