#
# rhel.py
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from pyanaconda.installclass import BaseInstallClass
from pyanaconda.constants import *
from pyanaconda.product import *
from pyanaconda import network
from pyanaconda import nm
import types


from blivet.partspec import PartSpec
from blivet.devicelibs import swap
from blivet.platform import platform
from blivet.size import Size
from pyanaconda.kickstart import getAvailableDiskSpace



class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "centos"
    name = N_("CentOS Linux")
    sortPriority = 25000
    if productName.startswith("Red Hat ") or productName.startswith("Fedora "):
        hidden = 1

    defaultFS = "xfs"

    bootloaderTimeoutDefault = 5
    bootloaderExtraArgs = []

    ignoredPackages = ["ntfsprogs", "reiserfs-utils"]

    # As both xen repo and core repo has kernel package, installer get stuck
    # durin kernel choice with updates option enabled, it will use the latest
    # available kernel i.e. 3.18
    installUpdates = True

    _l10n_domain = "comps"

    efi_dir = "centos"

    # Setting 4GB for dom0, so that rest of the space will be availbe for domUs.    
    def setDefaultPartitioning(self,storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.defaultFSType,
                                 size=Size("1GiB"),
                                 maxSize=Size("4GiB"),
                                 grow=True,
                                 btr=True, lv=True, thin=True, encrypted=True),
                        PartSpec(mountpoint="/home",
                                 fstype=storage.defaultFSType,
                                 size=Size("500MiB"), grow=True,
                                 requiredSpace=Size("50GiB"),
                                 btr=True, lv=True, thin=True, encrypted=True)]

        bootreqs = platform.setDefaultPartitioning()
        if bootreqs:
            autorequests.extend(bootreqs)


        disk_space = getAvailableDiskSpace(storage)
        swp = swap.swapSuggestion(disk_space=disk_space)
        autorequests.append(PartSpec(fstype="swap", size=swp, grow=False,
                                     lv=True, encrypted=True))

        for autoreq in autorequests:
            if autoreq.fstype is None:
                if autoreq.mountpoint == "/boot":
                    autoreq.fstype = storage.defaultBootFSType
                else:
                    autoreq.fstype = storage.defaultFSType

        storage.autoPartitionRequests = autorequests


    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)
        self.setDefaultPartitioning(anaconda.storage)

    # Set first boot policy regarding ONBOOT value
    # (i.e. which network devices should be activated automatically after reboot)
    # After switch root we set ONBOOT=no as default for all devices not activatedi
    # in initramfs. Here, at the end of installation, we check and modify it eventually.

    def setNetworkOnbootDefault(self, ksdata):
        # if there is no device to be autoactivated after reboot
        for devName in nm.nm_devices():
            if nm.nm_device_type_is_wifi(devName):
                continue
            try:
                onboot = nm.nm_device_setting_value(devName, "connection", "autoconnect")
            except nm.SettingsNotFoundError:
                continue
            if not onboot == False:
                return

        # set ONBOOT=yes for the device used during installation
        # (ie for majority of cases the one having the default route)
        devName = network.default_route_device()
        if not devName:
            return
        if nm.nm_device_type_is_wifi(devName):
            return
        ifcfg_path = network.find_ifcfg_file_of_device(devName, root_path=ROOT_PATH)
        if not ifcfg_path:
            return
        ifcfg = network.IfcfgFile(ifcfg_path)
        ifcfg.read()
    #    ifcfg.set(('ONBOOT', 'yes'))
        ifcfg.write()
        for nd in ksdata.network.network:
            if nd.device == devName:
     #           nd.onboot = True
                break

    def __init__(self):
        BaseInstallClass.__init__(self)
