# __init__.py
# Entry point for anaconda's software management module.
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#                    Chris Lumens <clumens@redhat.com>
#

"""
    TODO
        - error handling!!!
        - document all methods

"""

import os, sys
from urlgrabber.grabber import URLGrabber
from urlgrabber.grabber import URLGrabError
import ConfigParser
import shutil
import time
import threading

if __name__ == "__main__":
    from pyanaconda import anaconda_log
    anaconda_log.init()

from pyanaconda.constants import DRACUT_ISODIR, DRACUT_REPODIR, DD_ALL, DD_FIRMWARE, DD_RPMS, INSTALL_TREE, ISO_DIR, ROOT_PATH, \
                                 THREAD_STORAGE, THREAD_WAIT_FOR_CONNECTING_NM, THREAD_PAYLOAD, \
                                 THREAD_PAYLOAD_RESTART
from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_

from pyanaconda import iutil
from pyanaconda import isys
from pyanaconda.iutil import ProxyString, ProxyStringError

from pykickstart.constants import GROUP_ALL, GROUP_DEFAULT, GROUP_REQUIRED

from pyanaconda.threads import threadMgr, AnacondaThread

from pykickstart.parser import Group

import logging
log = logging.getLogger("packaging")

from blivet.errors import StorageError
import blivet.util
import blivet.arch
from blivet.platform import platform

from pyanaconda.product import productName, productVersion
import urlgrabber
urlgrabber.grabber.default_grabber.opts.user_agent = "%s (anaconda)/%s" %(productName, productVersion)

###
### ERROR HANDLING
###
class PayloadError(Exception):
    pass

class MetadataError(PayloadError):
    pass

class NoNetworkError(PayloadError):
    pass

# setup
class PayloadSetupError(PayloadError):
    pass

class ImageMissingError(PayloadSetupError):
    pass

class ImageDirectoryMountError(PayloadSetupError):
    pass

# software selection
class NoSuchGroup(PayloadError):
    pass

class NoSuchPackage(PayloadError):
    pass

class DependencyError(PayloadError):
    pass

# installation
class PayloadInstallError(PayloadError):
    pass

class Payload(object):
    """ Payload is an abstract class for OS install delivery methods. """
    def __init__(self, data):
        """ data is a kickstart.AnacondaKSHandler class
        """
        self.data = data
        self.storage = None
        self._kernelVersionList = []
        self._createdInitrds = False

    def setup(self, storage):
        """ Do any payload-specific setup. """
        self.storage = storage

    def preStorage(self):
        """ Do any payload-specific work necessary before writing the storage
            configuration.  This method need not be provided by all payloads.
        """
        pass

    def release(self):
        """ Release any resources in use by this object, but do not do final
            cleanup.  This is useful for dealing with payload backends that do
            not get along well with multithreaded programs.
        """
        pass

    def reset(self, root=None, releasever=None):
        """ Reset the instance, not including ksdata. """
        pass

    def prepareMountTargets(self, storage):
        """Run when physical storage is mounted, but other mount points may
        not exist.  Used by the RPMOSTreePayload subclass.
        """
        pass

    ###
    ### METHODS FOR WORKING WITH REPOSITORIES
    ###
    @property
    def repos(self):
        """A list of repo identifiers, not objects themselves."""
        raise NotImplementedError()

    @property
    def addOns(self):
        """ A list of addon repo identifiers. """
        return [r.name for r in self.data.repo.dataList()]

    @property
    def baseRepo(self):
        """ The identifier of the current base repo. """
        return None

    @property
    def mirrorEnabled(self):
        """Is the closest/fastest mirror option enabled?  This does not make
           sense for those payloads that do not support this concept.
        """
        return True

    def getRepo(self, repo_id):
        """ Return the package repo object. """
        raise NotImplementedError()

    def isRepoEnabled(self, repo_id):
        """ Return True if repo is enabled. """
        repo = self.getAddOnRepo(repo_id)
        if repo:
            return repo.enabled
        else:
            return False

    def getAddOnRepo(self, repo_id):
        """ Return a ksdata Repo instance matching the specified repo id. """
        repo = None
        for r in self.data.repo.dataList():
            if r.name == repo_id:
                repo = r
                break

        return repo

    def _repoNeedsNetwork(self, repo):
        """ Returns True if the ksdata repo requires networking. """
        urls = [repo.baseurl]
        if repo.mirrorlist:
            urls.extend(repo.mirrorlist)
        network_protocols = ["http:", "ftp:", "nfs:", "nfsiso:"]
        for url in urls:
            if any(url.startswith(p) for p in network_protocols):
                return True

        return False

    @property
    def needsNetwork(self):
        return any(self._repoNeedsNetwork(r) for r in self.data.repo.dataList())

    def _resetMethod(self):
        self.data.method.method = ""
        self.data.method.url = None
        self.data.method.server = None
        self.data.method.dir = None
        self.data.method.partition = None
        self.data.method.biospart = None
        self.data.method.noverifyssl = False
        self.data.method.proxy = ""
        self.data.method.opts = None

    def updateBaseRepo(self, fallback=True, root=None, checkmount=True):
        """ Update the base repository from ksdata.method. """
        pass

    def configureAddOnRepo(self, repo):
        """ Set up an addon repo as defined in ksdata Repo repo. """
        pass

    def gatherRepoMetadata(self):
        pass

    def addRepo(self, newrepo):
        """Add the repo given by the pykickstart Repo object newrepo to the
           system.  The repo will be automatically enabled and its metadata
           fetched.

           Duplicate repos will not raise an error.  They should just silently
           take the place of the previous value.
        """
        # Add the repo to the ksdata so it'll appear in the output ks file.
        self.data.repo.dataList().append(newrepo)

    def removeRepo(self, repo_id):
        repos = self.data.repo.dataList()
        try:
            idx = [repo.name for repo in repos].index(repo_id)
        except ValueError:
            log.error("failed to remove repo %s: not found", repo_id)
        else:
            repos.pop(idx)

    def enableRepo(self, repo_id):
        repo = self.getAddOnRepo(repo_id)
        if repo:
            repo.enabled = True

    def disableRepo(self, repo_id):
        repo = self.getAddOnRepo(repo_id)
        if repo:
            repo.enabled = False

    ###
    ### METHODS FOR WORKING WITH ENVIRONMENTS
    ###
    @property
    def environments(self):
        raise NotImplementedError()

    def environmentSelected(self, environmentid):
        raise NotImplementedError()

    def environmentHasOption(self, environmentid, grpid):
        raise NotImplementedError()

    def environmentOptionIsDefault(self, environmentid, grpid):
        raise NotImplementedError()

    def environmentDescription(self, environmentid):
        raise NotImplementedError()

    def selectEnvironment(self, environmentid):
        raise NotImplementedError()

    def deselectEnvironment(self, environmentid):
        raise NotImplementedError()

    def environmentGroups(self, environmentid):
        raise NotImplementedError()

    ###
    ### METHODS FOR WORKING WITH GROUPS
    ###
    @property
    def groups(self):
        raise NotImplementedError()

    def languageGroups(self):
        return []

    def groupDescription(self, groupid):
        raise NotImplementedError()

    def groupSelected(self, groupid):
        return Group(groupid) in self.data.packages.groupList

    def selectGroup(self, groupid, default=True, optional=False):
        if optional:
            include = GROUP_ALL
        elif default:
            include = GROUP_DEFAULT
        else:
            include = GROUP_REQUIRED

        grp = Group(groupid, include=include)

        if grp in self.data.packages.groupList:
            # I'm not sure this would ever happen, but ensure that re-selecting
            # a group with a different types set works as expected.
            if grp.include != include:
                grp.include = include

            return

        if grp in self.data.packages.excludedGroupList:
            self.data.packages.excludedGroupList.remove(grp)

        self.data.packages.groupList.append(grp)

    def deselectGroup(self, groupid):
        grp = Group(groupid)

        if grp in self.data.packages.excludedGroupList:
            return

        if grp in self.data.packages.groupList:
            self.data.packages.groupList.remove(grp)

        self.data.packages.excludedGroupList.append(grp)

    ###
    ### METHODS FOR WORKING WITH PACKAGES
    ###
    @property
    def packages(self):
        raise NotImplementedError()

    def packageSelected(self, pkgid):
        return pkgid in self.data.packages.packageList

    def selectPackage(self, pkgid):
        """Mark a package for installation.

           pkgid - The name of a package to be installed.  This could include
                   a version or architecture component.
        """
        if pkgid in self.data.packages.packageList:
            return

        if pkgid in self.data.packages.excludedList:
            self.data.packages.excludedList.remove(pkgid)

        self.data.packages.packageList.append(pkgid)

    def deselectPackage(self, pkgid):
        """Mark a package to be excluded from installation.

           pkgid - The name of a package to be excluded.  This could include
                   a version or architecture component.
        """
        if pkgid in self.data.packages.excludedList:
            return

        if pkgid in self.data.packages.packageList:
            self.data.packages.packageList.remove(pkgid)

        self.data.packages.excludedList.append(pkgid)

    ###
    ### METHODS FOR QUERYING STATE
    ###
    @property
    def spaceRequired(self):
        raise NotImplementedError()

    @property
    def kernelVersionList(self):
        if not self._kernelVersionList:
            import glob
            try:
                import yum
            except ImportError:
                cmpfunc = cmp
            else:
                cmpfunc = yum.rpmUtils.miscutils.compareVerOnly

            files = glob.glob(iutil.getSysroot() + "/boot/vmlinuz-*")
            files.extend(glob.glob(iutil.getSysroot() + "/boot/efi/EFI/redhat/vmlinuz-*"))
            # strip off everything up to and including vmlinuz- to get versions
            # Ignore rescue kernels
            versions = [f.split("/")[-1][8:] for f in files if os.path.isfile(f) \
                        and "-rescue-" not in f]
            versions.sort(cmp=cmpfunc)
            log.debug("kernel versions: %s", versions)
            self._kernelVersionList = versions

        return self._kernelVersionList

    ##
    ## METHODS FOR TREE VERIFICATION
    ##
    def _getTreeInfo(self, url, proxy_url, sslverify):
        """ Retrieve treeinfo and return the path to the local file.

            :param baseurl: url of the repo
            :type baseurl: string
            :param proxy_url: Optional full proxy URL of or ""
            :type proxy_url: string
            :param sslverify: True if SSL certificate should be varified
            :type sslverify: bool
            :returns: Path to retrieved .treeinfo file or None
            :rtype: string or None
        """
        if not url:
            return None

        log.debug("retrieving treeinfo from %s (proxy: %s ; sslverify: %s)",
                  url, proxy_url, sslverify)

        ugopts = {"ssl_verify_peer": sslverify,
                  "ssl_verify_host": sslverify}

        proxies = {}
        if proxy_url:
            try:
                proxy = ProxyString(proxy_url)
                proxies = {"http": proxy.url,
                           "https": proxy.url}
            except ProxyStringError as e:
                log.info("Failed to parse proxy for _getTreeInfo %s: %s",
                         proxy_url, e)

        ug = URLGrabber()
        try:
            treeinfo = ug.urlgrab("%s/.treeinfo" % url,
                                  "/tmp/.treeinfo", copy_local=True,
                                  proxies=proxies, **ugopts)
        except URLGrabError as e:
            try:
                treeinfo = ug.urlgrab("%s/treeinfo" % url,
                                      "/tmp/.treeinfo", copy_local=True,
                                      proxies=proxies, **ugopts)
            except URLGrabError as e:
                log.info("Error downloading treeinfo: %s", e)
                treeinfo = None

        return treeinfo

    def _getReleaseVersion(self, url):
        """ Return the release version of the tree at the specified URL. """
        version = productVersion.split("-")[0]

        log.debug("getting release version from tree at %s (%s)", url, version)

        if hasattr(self.data.method, "proxy"):
            proxy = self.data.method.proxy
        else:
            proxy = None
        treeinfo = self._getTreeInfo(url, proxy, not flags.noverifyssl)
        if treeinfo:
            c = ConfigParser.ConfigParser()
            c.read(treeinfo)
            try:
                # Trim off any -Alpha or -Beta
                version = c.get("general", "version").split("-")[0]
            except ConfigParser.Error:
                pass

        if version.startswith(time.strftime("%Y")):
            version = "rawhide"

        log.debug("got a release version of %s", version)
        return version

    ##
    ## METHODS FOR MEDIA MANAGEMENT (XXX should these go in another module?)
    ##
    def _setupDevice(self, device, mountpoint):
        """ Prepare an install CD/DVD for use as a package source. """
        log.info("setting up device %s and mounting on %s", device.name, mountpoint)
        # Is there a symlink involved?  If so, let's get the actual path.
        # This is to catch /run/install/isodir vs. /mnt/install/isodir, for
        # instance.
        realMountpoint = os.path.realpath(mountpoint)

        if os.path.ismount(realMountpoint):
            mdev = blivet.util.get_mount_device(realMountpoint)
            if mdev:
                log.warning("%s is already mounted on %s", mdev, mountpoint)

            if mdev == device.path:
                return
            else:
                try:
                    blivet.util.umount(realMountpoint)
                except OSError as e:
                    log.error(str(e))
                    log.info("umount failed -- mounting on top of it")

        try:
            device.setup()
            device.format.setup(mountpoint=mountpoint)
        except StorageError as e:
            log.error("mount failed: %s", e)
            device.teardown(recursive=True)
            raise PayloadSetupError(str(e))

    def _setupNFS(self, mountpoint, server, path, options):
        """ Prepare an NFS directory for use as a package source. """
        log.info("mounting %s:%s:%s on %s", server, path, options, mountpoint)
        if os.path.ismount(mountpoint):
            dev = blivet.util.get_mount_device(mountpoint)
            _server, colon, _path = dev.partition(":")
            if colon == ":" and server == _server and path == _path:
                log.debug("%s:%s already mounted on %s", server, path, mountpoint)
                return
            else:
                log.debug("%s already has something mounted on it", mountpoint)
                try:
                    blivet.util.umount(mountpoint)
                except OSError as e:
                    log.error(str(e))
                    log.info("umount failed -- mounting on top of it")

        # mount the specified directory
        url = "%s:%s" % (server, path)

        if not options:
            options = "nolock"
        elif "nolock" not in options:
            options += ",nolock"

        try:
            blivet.util.mount(url, mountpoint, fstype="nfs", options=options)
        except OSError as e:
            raise PayloadSetupError(str(e))

    ###
    ### METHODS FOR INSTALLING THE PAYLOAD
    ###
    def preInstall(self, packages=None, groups=None):
        """ Perform pre-installation tasks. """
        iutil.mkdirChain(iutil.getSysroot() + "/root")

        self._writeModuleBlacklist()

    def install(self):
        """ Install the payload. """
        raise NotImplementedError()

    def _writeModuleBlacklist(self):
        """ Copy modules from modprobe.blacklist=<module> on cmdline to
            /etc/modprobe.d/anaconda-blacklist.conf so that modules will
            continue to be blacklisted when the system boots.
        """
        if "modprobe.blacklist" not in flags.cmdline:
            return

        iutil.mkdirChain(iutil.getSysroot() + "/etc/modprobe.d")
        with open(iutil.getSysroot() + "/etc/modprobe.d/anaconda-blacklist.conf", "w") as f:
            f.write("# Module blacklists written by anaconda\n")
            for module in flags.cmdline["modprobe.blacklist"].split():
                f.write("blacklist %s\n" % module)

    def _copyDriverDiskFiles(self):
        import glob

        # Multiple driver disks may be loaded, so we need to glob for all
        # the firmware files in the common DD firmware directory
        for f in glob.glob(DD_FIRMWARE+"/*"):
            try:
                shutil.copyfile(f, "%s/lib/firmware/" % iutil.getSysroot())
            except IOError as e:
                log.error("Could not copy firmware file %s: %s", f, e.strerror)

        #copy RPMS
        for d in glob.glob(DD_RPMS):
            shutil.copytree(d, iutil.getSysroot() + "/root/" + os.path.basename(d))

        #copy modules and firmware into root's home directory
        if os.path.exists(DD_ALL):
            try:
                shutil.copytree(DD_ALL, iutil.getSysroot() + "/root/DD")
            except IOError as e:
                log.error("failed to copy driver disk files: %s", e.strerror)
                # XXX TODO: real error handling, as this is probably going to
                #           prevent boot on some systems

    def recreateInitrds(self, force=False):
        """ Recreate the initrds by calling new-kernel-pkg

            This needs to be done after all configuration files have been
            written, since dracut depends on some of them.

            :param force: Always recreate, default is to only do it on first call
            :type force: bool
            :returns: None
        """
        if not force and self._createdInitrds:
            return

        for kernel in self.kernelVersionList:
            log.info("recreating initrd for %s", kernel)
            if not flags.imageInstall:
                iutil.execInSysroot("new-kernel-pkg",
                                    ["--mkinitrd", "--dracut",
                                    "--depmod", "--update", kernel])
            else:
                # hostonly is not sensible for disk image installations
                # using /dev/disk/by-uuid/ is necessary due to disk image naming
                iutil.execInSysroot("dracut",
                                    ["-N",
                                     "--persistent-policy", "by-uuid",
                                     "-f", "/boot/initramfs-%s.img" % kernel,
                                    kernel])

        self._createdInitrds = True


    def _setDefaultBootTarget(self):
        """ Set the default systemd target for the system. """
        if not os.path.exists(iutil.getSysroot() + "/etc/systemd/system"):
            log.error("systemd is not installed -- can't set default target")
            return

        # If X was already requested we don't have to continue
        if self.data.xconfig.startX:
            return

        try:
            import rpm
        except ImportError:
            log.info("failed to import rpm -- not adjusting default runlevel")
        else:
            ts = rpm.TransactionSet(iutil.getSysroot())

            # XXX one day this might need to account for anaconda's display mode
            if ts.dbMatch("provides", 'service(graphical-login)').count() and \
               ts.dbMatch('provides', 'xorg-x11-server-Xorg').count() and \
               not flags.usevnc:
                # We only manipulate the ksdata.  The symlink is made later
                # during the config write out.
                self.data.xconfig.startX = True

    def dracutSetupArgs(self):
        args = []
        try:
            import rpm
        except ImportError:
            pass
        else:
            iutil.resetRpmDb()
            ts = rpm.TransactionSet(iutil.getSysroot())

            # Only add "rhgb quiet" on non-s390, non-serial installs
            if iutil.isConsoleOnVirtualTerminal() and \
               (ts.dbMatch('provides', 'rhgb').count() or \
                ts.dbMatch('provides', 'plymouth').count()):
                args.extend(["rhgb", "quiet"])

        return args

    def postInstall(self):
        """ Perform post-installation tasks. """

        # set default systemd target
        self._setDefaultBootTarget()

        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here

        self._copyDriverDiskFiles()

# Inherit abstract methods from Payload
# pylint: disable=W0223
class ImagePayload(Payload):
    """ An ImagePayload installs an OS image to the target system. """
    pass

# Inherit abstract methods from ImagePayload
# pylint: disable=W0223
class ArchivePayload(ImagePayload):
    """ An ArchivePayload unpacks source archives onto the target system. """
    pass

# Inherit abstract methods from Payload
# pylint: disable=W0223
class PackagePayload(Payload):
    """ A PackagePayload installs a set of packages onto the target system. """

    def preInstall(self, packages=None, groups=None):
        super(PackagePayload, self).preInstall()

        # Add platform specific group
        groupid = iutil.get_platform_groupid()
        if groupid and groupid in self.groups:
            if isinstance(groups, list):
                log.info("Adding platform group %s", groupid)
                groups.append(groupid)
            else:
                log.warning("Could not add %s to groups, not a list.", groupid)
        elif groupid:
            log.warning("Platform group %s not available.", groupid)

        # Set rpm-specific options

        # nofsync speeds things up at the risk of rpmdb data loss in a crash.
        # But if we crash mid-install you're boned anyway, so who cares?
        self.rpmMacros.append(('__dbi_htconfig', 'hash nofsync %{__dbi_other} %{__dbi_perms}'))

        if self.data.packages.excludeDocs:
            self.rpmMacros.append(('_excludedocs', '1'))

        if self.data.packages.instLangs is not None:
            # Use nil if instLangs is empty
            self.rpmMacros.append(('_install_langs', self.data.packages.instLangs or '%{nil}'))

        if flags.selinux:
            for d in ["/tmp/updates",
                      "/etc/selinux/targeted/contexts/files",
                      "/etc/security/selinux/src/policy",
                      "/etc/security/selinux"]:
                f = d + "/file_contexts"
                if os.access(f, os.R_OK):
                    self.rpmMacros.append(('__file_context_path', f))
                    break
        else:
            self.rpmMacros.append(('__file_context_path', '%{nil}'))

    def __init__(self, data):
        if self.__class__ is PackagePayload:
            raise TypeError("PackagePayload is an abstract class")

        super(PackagePayload, self).__init__(data)
        self.install_device = None
        self._rpm_macros = []

    @property
    def kernelPackages(self):
        if "kernel" in self.data.packages.excludedList:
            return []

        kernels = ["kernel"]

        if isys.isPaeAvailable():
            kernels.insert(0, "kernel-PAE")

        # most ARM systems use platform-specific kernels
        if blivet.arch.isARM():
            if platform.armMachine is not None:
                kernels = ["kernel-%s" % platform.armMachine]

        return kernels

    @property
    def rpmMacros(self):
        """A list of (name, value) pairs to define as macros in the rpm transaction."""
        return self._rpm_macros

    @rpmMacros.setter
    def rpmMacros(self, value):
        self._rpm_macros = value

class PayloadManager(object):
    """Framework for starting and watching the payload thread.

       This class defines several states, and events can be triggered upon
       reaching a state. Depending on whether a state has already been reached
       when a listener is added, the event code may be run in either the
       calling thread or the payload thread. The event code will block the
       payload thread regardless, so try not to run anything that takes a long
       time.

       All states except STATE_ERROR are expected to happen linearly, and adding
       a listener for a state that has already been reached or passed will
       immediately trigger that listener. For example, if the payload thread is
       currently in STATE_GROUP_MD, adding a listener for STATE_NETWORK will
       immediately run the code being added for STATE_NETWORK.

       The payload thread data should be accessed using the payloadMgr object,
       and the running thread can be accessed using threadMgr with the
       THREAD_PAYLOAD constant, if you need to wait for it or something. The
       thread should be started using payloadMgr.restartThread.
    """

    STATE_START = 0
    # Waiting on storage
    STATE_STORAGE = 1
    # Waiting on network
    STATE_NETWORK = 2
    # Downloading package metadata
    STATE_PACKAGE_MD = 3
    # Downloading group metadata
    STATE_GROUP_MD = 4
    # All done
    STATE_FINISHED = 5

    # Error
    STATE_ERROR = -1

    # Error strings
    ERROR_SETUP = N_("Failed to set up installation source")
    ERROR_MD = N_("Error downloading package metadata")
    ERROR_SOURCE = N_("No installation source available")

    def __init__(self):
        self._event_lock = threading.Lock()
        self._event_listeners = {}
        self._thread_state = self.STATE_START
        self._error = None

        # Initialize a list for each event state
        for event_id in range(self.STATE_ERROR, self.STATE_FINISHED + 1):
            self._event_listeners[event_id] = []

    @property
    def error(self):
        return _(self._error)

    def addListener(self, event_id, func):
        """Add a listener for an event.

           :param int event_id: The event to listen for, one of the EVENT_* constants
           :param function func: An object to call when the event is reached
        """

        # Check that the event_id is valid
        assert isinstance(event_id, int)
        assert event_id <= self.STATE_FINISHED
        assert event_id >= self.STATE_ERROR

        # Add the listener inside the lock in case we need to run immediately,
        # to make sure the listener isn't triggered twice
        with self._event_lock:
            self._event_listeners[event_id].append(func)

            # If an error event was requested, run it if currently in an error state
            if event_id == self.STATE_ERROR:
                if event_id == self._thread_state:
                    func()
            # Otherwise, run if the requested event has already occurred
            elif event_id <= self._thread_state:
                func()

    def restartThread(self, storage, ksdata, payload, fallback=False, checkmount=True):
        """Start or restart the payload thread.

           This method starts a new thread to restart the payload thread, so
           this method's return is not blocked by waiting on the previous payload
           thread. If there is already a payload thread restart pending, this method
           has no effect.

           :param blivet.Blivet storage: The blivet storage instance
           :param kickstart.AnacondaKSHandler ksdata: The kickstart data instance
           :param packaging.Payload payload: The payload instance
           :param bool fallback: Whether to fall back to the default repo in case of error
           :param bool checkmount: Whether to check for valid mounted media
        """

        log.debug("Restarting payload thread")

        # If a restart thread is already running, don't start a new one
        if threadMgr.get(THREAD_PAYLOAD_RESTART):
            return

        # Launch a new thread so that this method can return immediately
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD_RESTART, target=self._restartThread,
            args=(storage, ksdata, payload, fallback, checkmount)))

    def _restartThread(self, storage, ksdata, payload, fallback, checkmount):
        # Wait for the old thread to finish
        threadMgr.wait(THREAD_PAYLOAD)

        # Start a new payload thread
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD, target=self._runThread,
            args=(storage, ksdata, payload, fallback, checkmount)))

    def _setState(self, event_id):
        # Update the current state
        log.debug("Updating payload thread state: %d", event_id)
        with self._event_lock:
            # Update the state within the lock to avoid a race with listeners
            # currently being added
            self._thread_state = event_id

            # Run any listeners for the new state
            for func in self._event_listeners[event_id]:
                func()

    def _runThread(self, storage, ksdata, payload, fallback, checkmount):
        # This is the thread entry
        # Set the initial state
        self._error = None
        self._setState(self.STATE_START)

        # Wait for storage
        self._setState(self.STATE_STORAGE)
        threadMgr.wait(THREAD_STORAGE)

        # Wait for network
        self._setState(self.STATE_NETWORK)
        # FIXME: condition for cases where we don't want network
        # (set and use payload.needsNetwork ?)
        threadMgr.wait(THREAD_WAIT_FOR_CONNECTING_NM)

        self._setState(self.STATE_PACKAGE_MD)
        payload.setup(storage)

        # If this is a non-package Payload, we're done
        if not isinstance(payload, PackagePayload):
            self._setState(self.STATE_FINISHED)
            return

        # Keep setting up package-based repositories
        # Download package metadata
        try:
            payload.updateBaseRepo(fallback=fallback, checkmount=checkmount)
        except (OSError, PayloadError) as e:
            log.error("PayloadError: %s", e)
            self._error = self.ERROR_SETUP
            self._setState(self.STATE_ERROR)
            return

        # Gather the group data
        self._setState(self.STATE_GROUP_MD)
        payload.gatherRepoMetadata()
        payload.release()

        # Check if that failed
        if not payload.baseRepo:
            log.error("No base repo configured")
            self._error = self.ERROR_MD
            self._setState(self.STATE_ERROR)
            return

        try:
            # Grabbing the list of groups could potentially take a long time the
            # first time (yum does a lot of magic property stuff, some of which
            # involves side effects like network access) so go ahead and grab
            # them now. These are properties with side-effects, just accessing
            # them will trigger yum.
            # pylint: disable=pointless-statement
            payload.environments
            # pylint: disable=pointless-statement
            payload.groups
        except MetadataError as e:
            log.error("MetadataError: %s", e)
            self._error = self.ERROR_SOURCE
            self._setState(self.STATE_ERROR)
            return

        self._setState(self.STATE_FINISHED)

# Initialize the PayloadManager instance
payloadMgr = PayloadManager()

def show_groups(payload):
    #repo = ksdata.RepoData(name="anaconda", baseurl="http://cannonball/install/rawhide/os/")
    #obj.addRepo(repo)

    desktops = []
    addons = []

    for grp in payload.groups:
        if grp.endswith("-desktop"):
            desktops.append(payload.description(grp))
        elif not grp.endswith("-support"):
            addons.append(payload.description(grp))

    import pprint

    print "==== DESKTOPS ===="
    pprint.pprint(desktops)
    print "==== ADDONS ===="
    pprint.pprint(addons)

    print payload.groups

def print_txmbrs(payload, f=None):
    if f is None:
        f = sys.stdout

    print >> f, "###########"
    for txmbr in payload._yum.tsInfo.getMembers():
        print >> f, txmbr
    print >> f, "###########"

def write_txmbrs(payload, filename):
    if os.path.exists(filename):
        os.unlink(filename)

    f = open(filename, 'w')
    print_txmbrs(payload, f)
    f.close()
