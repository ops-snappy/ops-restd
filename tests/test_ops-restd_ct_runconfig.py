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

import os
import sys
import time
import pytest
import subprocess
import shutil
from halonvsi.docker import *
from halonvsi.halon import *
from halonutils.halonutil import *
from restdconfig import *

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

SWITCH_PREFIX = "s"

class myTopo(Topo):
    def build (self, hsts=0, sws=1, **_opts):

        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)


class configTest (HalonTest):
    def setupNet (self):
        self.net = Mininet(topo=myTopo(hsts = NUM_HOSTS_PER_SWITCH,
                                       sws = NUM_OF_SWITCHES,
                                       hopts = self.getHostOpts(),
                                       sopts = self.getSwitchOpts()),
                                       switch = SWITCH_TYPE,
                                       host = HalonHost,
                                       link = HalonLink,
                                       controller = None,
                                       build = True)

    def copy_to_docker (self):
        info("\n########## Copying required files to docker ##########\n")
        switch = self.net.switches[0]
        testid = switch.testid
        script_shared_local = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared/runconfig_test_in_docker.py'
        script_shared_local_runconfig = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared/runconfig.py'
        script_shared_test_file1 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/config_test1'
        script_shared_test_file2 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/config_test2'
        script_shared_test_file3 = '/tmp/halon-test/' + testid +'/'+switch.name+'/shared' + '/empty_config.db'

        shutil.copy2("runconfig_test_in_docker.py", script_shared_local)
        shutil.copy2("config_test1.db", script_shared_test_file1)
        #shutil.copy2("config_test2.db", script_shared_test_file2)
        shutil.copy2("config_test3.db", script_shared_test_file2)
        shutil.copy2("empty_config.db", script_shared_test_file3)

    def verify_runconfig(self):
        info("\n########## Verify config writes for empty config and full config ##########\n")
        switch = self.net.switches[0]
        script_shared_docker = '/shared/runconfig_test_in_docker.py'
        out = switch.cmd('python ' + script_shared_docker)
        info(out)
        res = out.find("Test Failure")
        assert res == -1, "\n### Write was not successful ###\n"
        info("\n### Write was successful ###\n")

@pytest.mark.skipif(True, reason="Does not cleanup dockers fully")
class Test_config:
    def setup (self):
        pass

    def teardown (self):
        pass

    def setup_class (cls):
        Test_config.test_var = configTest()

    def teardown_class (cls):
        Test_config.test_var.net.stop()

    def setup_method (self, method):
        pass

    def teardown_method (self, method):
        pass

    def __del__ (self):
        del self.test_var

    def test_run (self):
        self.test_var.copy_to_docker()
        self.test_var.verify_runconfig()
