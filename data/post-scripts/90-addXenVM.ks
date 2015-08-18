%post --nochroot --log=/mnt/sysimage/var/log/anaconda/addXenVM.log
#!/bin/bash
c7_xlConfig="/run/install/repo/CentOS-7-demoVm.cfg"
c7_VmImage="/run/install/repo/CentOS-7-x86_64-XenCloud.qcow2.xz"
c6_xlConfig="/run/install/repo/CentOS-6-demoVm.cfg"
c6_VmImage="/run/install/repo/CentOS-6-x86_64-XenCloud.qcow2.xz"
mkdir -p $ANA_INSTALL_PATH/srv/xen
cp $c6_VmImage $c7_VmImage $ANA_INSTALL_PATH/srv/xen/
echo "copied $c6_VmImage"
echo "copied $c7_vmImage"
cp $c6_xlConfig $c7_xlConfig $ANA_INSTALL_PATH/root/
echo "copied xl config files in /root directory"
%end
