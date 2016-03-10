# Copyright 2016 Cloudbase Solutions Srl
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

import re

from oslo_log import log as logging

from os_win._i18n import _
from os_win import _utils
from os_win import exceptions
from os_win.utils import baseutils

LOG = logging.getLogger(__name__)


class DiskUtils(baseutils.BaseUtils):

    _wmi_namespace = 'root/microsoft/windows/storage'

    def __init__(self):
        self._conn_storage = self._get_wmi_conn(self._wmi_namespace)

        # Physical device names look like \\.\PHYSICALDRIVE1
        self._phys_dev_name_regex = re.compile(r'\\\\.*\\[a-zA-Z]*([\d]+)')

    def _get_disk(self, disk_number):
        disk = self._conn_storage.Msft_Disk(Number=disk_number)
        if not disk:
            err_msg = _("Could not find the disk number %s")
            raise exceptions.DiskNotFound(err_msg % disk_number)
        return disk[0]

    def get_disk_uid_and_uid_type(self, disk_number):
        disk = self._get_disk(disk_number)
        return disk.UniqueId, disk.UniqueIdFormat

    def refresh_disk(self, disk_number):
        disk = self._get_disk(disk_number)
        disk.Refresh()

    def get_device_number_from_device_name(self, device_name):
        matches = self._phys_dev_name_regex.findall(device_name)
        if matches:
            return matches[0]

        err_msg = _("Could not find device number for device: %s")
        raise exceptions.DiskNotFound(err_msg % device_name)

    def rescan_disks(self):
        # TODO(lpetrut): find a better way to do this.
        cmd = ("cmd", "/c", "echo", "rescan", "|", "diskpart.exe")
        _utils.execute(*cmd)