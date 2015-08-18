%post --log=/var/log/anaconda/bridge_setting.log
#!/bin/bash

#get the default device
dev=`ip route show | grep 'default' | awk '{print $5}'`

if [[ ! "$dev" ]]; then
    echo "Couldn't find any active network devices during installation to configure."
    exit 0
else
    default_con_uuid=`/usr/bin/nmcli -t --fields UUID,DEVICE con show | grep $dev | awk -F: '{print $1}'`

    slave_mac=`/usr/bin/nmcli dev show $dev | grep HWADDR | awk '{print $2}'`

    slave_type=`/usr/bin/nmcli -t --fields TYPE,DEVICE con show | grep $dev | awk -F: '{print $1}'`

    /usr/bin/nmcli con add type bridge con-name xenbr0 ifname xenbr0
    echo "adding $dev to bridge xenbr0"
    /usr/bin/nmcli con add type bridge-slave con-name xenbr0-slave_$dev ifname $dev master xenbr0
    /usr/bin/nmcli con modify xenbr0-slave_$dev $slave_type.mac-address $slave_mac

    #stopping the default connection to get hold of default device
    /usr/bin/nmcli con modify $default_con_uuid connection.autoconnect no
fi
%end
