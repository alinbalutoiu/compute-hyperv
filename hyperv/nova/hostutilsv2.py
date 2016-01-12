# Copyright 2015 Cloudbase Solutions Srl
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

import sys

if sys.platform == 'win32':
    import wmi

from oslo_log import log as logging

from hyperv.i18n import _LW
from hyperv.nova import hostutils

LOG = logging.getLogger(__name__)


class HostUtilsV2(hostutils.HostUtils):

    _MSVM_PROCESSOR = 'Msvm_Processor'
    _MSVM_MEMORY = 'Msvm_Memory'
    _MSVM_NUMA_NODE = 'Msvm_NumaNode'

    _CENTRAL_PROCESSOR = 'Central Processor'

    def __init__(self):
        super(HostUtilsV2, self).__init__()
        self._init_wmi_virt_conn()

    def _init_wmi_virt_conn(self):
        if sys.platform == 'win32':
            self._conn_virt = wmi.WMI(moniker='//./root/virtualization/v2')

    def get_numa_nodes(self):
        numa_nodes = self._conn_virt.Msvm_NumaNode()
        nodes_info = []
        for node in numa_nodes:
            numa_assoc_query = ("SELECT * FROM Msvm_HostedDependency "
                                "WHERE Antecedent = '%s'" % node.path_())
            numa_assoc = self._conn_virt.query(numa_assoc_query)
            numa_node_paths = [item.Dependent for item in numa_assoc]

            system_memories = self._conn_virt.Msvm_Memory()
            memory_info = self._get_numa_memory_info(numa_node_paths,
                                                     system_memories)
            if not memory_info:
                LOG.warning(_LW("Could not find memory information for NUMA "
                                "node. Skipping node measurements."))
                continue

            # Due to a bug in vmms, getting Msvm_Processor for the numa
            # node associators resulted in a vmms crash.
            # As an alternative to using associators we have to manually get
            # the related Msvm_Processor classes.
            # Msvm_HostedDependency is the association class between
            # Msvm_NumaNode and Msvm_Processor. We need to use this class to
            # relate the two because using associators on Msvm_Processor
            # will also result in a crash.
            processors = self._conn_virt.Msvm_Processor(['DeviceID'])
            cpu_info = self._get_numa_cpu_info(numa_node_paths, processors)
            if not cpu_info:
                LOG.warning(_LW("Could not find CPU information for NUMA "
                                "node. Skipping node measurements."))
                continue

            node_info = {
                # NodeID has the format: Microsoft:PhysicalNode\<NODE_ID>
                'id': node.NodeID.split('\\')[-1],

                # memory block size is 1MB.
                'memory': memory_info.NumberOfBlocks,
                'memory_usage': node.CurrentlyConsumableMemoryBlocks,

                # DeviceID has the format: Microsoft:UUID\0\<DEV_ID>
                'cpuset': set([c.DeviceID.split('\\')[-1] for c in cpu_info]),
                # cpu_usage can be set, each CPU has a "LoadPercentage"
                'cpu_usage': 0,
            }

            nodes_info.append(node_info)

        return nodes_info

    def _get_numa_memory_info(self, numa_node_paths, system_memories):
        memory_info = []
        paths = [x.upper() for x in numa_node_paths]
        for memory in system_memories:
            if memory.path_().upper() in paths:
                memory_info.append(memory)

        if memory_info:
            return memory_info[0]

    def _get_numa_cpu_info(self, numa_node_paths, processors):
        cpu_info = []
        paths = [x.upper() for x in numa_node_paths]
        for proc in processors:
            if proc.path_().upper() in paths:
                cpu_info.append(proc)

        if cpu_info:
            return cpu_info

    def get_remotefx_gpu_info(self):
        gpus = []
        all_gpus = self._conn_virt.Msvm_Physical3dGraphicsProcessor(
            EnabledForVirtualization=True)
        for gpu in all_gpus:
            gpus.append({'name': gpu.Name,
                         'driver_version': gpu.DriverVersion,
                         'total_video_ram': gpu.TotalVideoMemory,
                         'available_video_ram': gpu.AvailableVideoMemory,
                         'directx_version': gpu.DirectXVersion})
        return gpus
