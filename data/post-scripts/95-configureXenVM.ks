%post --log=/var/log/anaconda/configureXenVM.log
#!/bin/bash
echo "VmImages copied now unzipping VmImages"
vg_name=`/sbin/vgs --noheadings -o vg_name,vg_free | awk '{print $1}'`
vg_free=`/sbin/vgs --noheadings -o vg_name,vg_free | awk '{print $2}'`
vg_free=`echo $vg_free | awk -F. '{print $1}'`
if [ $vg_free -lt 4 ]; then
    echo "no enough space left of system for Demo VMs, so not creating demo VMs"

elif [ $vg_free -lt 8 ]; then
    echo "Only space for 1 VM so creating CentOS-7 VM"
    /sbin/lvcreate -L 4G -n CentOS-7-demo $vg_name --yes

    /usr/bin/unxz -k /srv/xen/CentOS-7-x86_64-XenCloud.qcow2.xz
    echo "unzipped CentOS-7 vmImage now converting it to raw format"
    /usr/bin/qemu-img convert -f qcow2 -O raw /srv/xen/CentOS-7-x86_64-XenCloud.qcow2 /srv/xen/CentOS-7-x86_64-XenCloud.raw
    echo "Converted CentOS-7 vmImage from qcow2 to raw"
    /bin/dd if=/srv/xen/CentOS-7-x86_64-XenCloud.raw of=/dev/$vg_name/CentOS-7-demo

    path_to_lv="/dev/$vg_name/CentOS-7-demo"
    echo "copied CentOS-7 VmImage to lv"
    /usr/bin/sed -i -e "s#path_to_lv#$path_to_lv#g" /root/CentOS-7-demoVm.cfg

    XenBridge=`/sbin/ip addr| grep xenbr0`
    if [[ ! "$XenBridge" ]];then
        /usr/bin/sed/ -i '/vif/d' /root/CentOS-7-demoVm.cfg
    fi

    chmod u+w /root/CentOS-7-demoVm.cfg

    echo "configured xl config script for CentOS-7 VM"
    rm -f /srv/xen/CentOS-7-x86_64-XenCloud.qcow2 /srv/xen/CentOS-7-x86_64-XenCloud.raw

else
    echo "enough space availbe for both VMs"
    /sbin/lvcreate -L 4G -n CentOS-7-demo $vg_name --yes
    /sbin/lvcreate -L 4G -n CentOS-6-demo $vg_name --yes
    
    /usr/bin/unxz -k /srv/xen/CentOS-7-x86_64-XenCloud.qcow2.xz
    echo "unzipped CentOS-7 vmImage now converting it to raw format"
    /usr/bin/qemu-img convert -f qcow2 -O raw /srv/xen/CentOS-7-x86_64-XenCloud.qcow2 /srv/xen/CentOS-7-x86_64-XenCloud.raw
    echo "Converted CentOS-7 vmImage from qcow2 to raw"

    /bin/dd if=/srv/xen/CentOS-7-x86_64-XenCloud.raw of=/dev/$vg_name/CentOS-7-demo
    echo "copied CentOS-7 VmImage to lv"
    rm -f /srv/xen/CentOS-7-x86_64-XenCloud.qcow2 /srv/xen/CentOS-7-x86_64-XenCloud.raw
    
    path_to_lv="/dev/$vg_name/CentOS-7-demo"
    /usr/bin/sed -i -e "s#path_to_lv#$path_to_lv#g" /root/CentOS-7-demoVm.cfg   
    
    /usr/bin/unxz -k /srv/xen/CentOS-6-x86_64-XenCloud.qcow2.xz
    echo "unzipped CentOS-6 vmImage now converting these to raw format"
    /usr/bin/qemu-img convert -f qcow2 -O raw /srv/xen/CentOS-6-x86_64-XenCloud.qcow2 /srv/xen/CentOS-6-x86_64-XenCloud.raw
    echo "Converted CentOS-6 vmImage from qcow2 to raw"

    /bin/dd if=/srv/xen/CentOS-6-x86_64-XenCloud.raw of=/dev/$vg_name/CentOS-6-demo
    echo "copied CentOS-7 VmImage to lv"
    rm -f /srv/xen/CentOS-6-x86_64-XenCloud.qcow2 /srv/xen/CentOS-6-x86_64-XenCloud.raw
    echo "copied CentOS-6 VmImage to lv"

    path_to_lv="/dev/$vg_name/CentOS-6-demo"
    /usr/bin/sed -i -e "s#path_to_lv#$path_to_lv#g" /root/CentOS-6-demoVm.cfg

    XenBridge=`/sbin/ip addr| grep xenbr0`
    if [[ ! "$XenBridge" ]];then
        /usr/bin/sed/ -i '/vif/d' /root/CentOS-7-demoVm.cfg
        /usr/bin/sed/ -i '/vif/d' /root/CentOS-6-demoVm.cfg
    fi

    chmod u+w /root/CentOS-7-demoVm.cfg
    chmod u+w /root/CentOS-6-demoVm.cfg
    echo "configured xl config script for both CentOS-6 and CentOS-7 VMs"
fi

%end
