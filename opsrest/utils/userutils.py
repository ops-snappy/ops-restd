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

# Third party imports
import pwd
import grp

from subprocess import PIPE, Popen


def get_group_id(group_name):
    group = grp.getgrnam(group_name)
    return group.gr_gid


def check_user_group(username, group):
    try:
        user_groups = Popen(["groups", username],
                            stdout=PIPE).communicate()[0]
        user_groups = user_groups.rstrip("\n").replace(" :", "").split(" ")

        if group in user_groups:
            return True
        else:
            return False

    except KeyError:
        return False


def user_exists(username):
    try:
        return pwd.getpwnam(username) is not None
    except KeyError:
        return False


def get_user_id(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        return None


def get_group_members(group_name):
    all_users = pwd.getpwall()
    all_users_group = []
    group_id = get_group_id(group_name)
    for user in all_users:
        if user.pw_gid == group_id:
            all_users_group.append(user)
    return all_users_group


def get_group_user_count(group_name):
    return len(get_group_members(group_name))
