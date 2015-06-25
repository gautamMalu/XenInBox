%post --log=/var/log/xen_grub_edit.log
# Chaging grub settings so xen will boot first
#!/bin/bash
/usr/bin/grub-bootxen.sh 
%end      
