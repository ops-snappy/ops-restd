# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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

from opsrest.handlers import login, ovsdbapi, config, customrest
from custom import usercontroller

REGEX_RESOURCE_ID = '?(?P<resource_id>[A-Za-z0-9-_]+[$]?)?/?'

url_patterns = [(r'/login', login.LoginHandler),
                (r'/rest/v1/system/full-configuration', config.ConfigHandler),
                (r'/.*', ovsdbapi.OVSDBAPIHandler),
                ]

custom_url_patterns = [(r'/rest/v1/system/users/%s' % REGEX_RESOURCE_ID,
                        customrest.CustomRESTHandler,
                        usercontroller.UserController),
                       ]
