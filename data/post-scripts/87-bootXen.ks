%post --log=/var/log/anaconda/xen_grub_edit.log
# Chaging grub settings so xen will boot first
#!/bin/bash
/usr/bin/grub-bootxen.sh 
%end      
