%post
# Chaging grub settings so xen will boot first
#!/bin/bash
/usr/bin/grub-bootxen.sh > /dev/null 2>&1 
%end      
