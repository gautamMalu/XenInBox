# XenInBox
Anaconda installer which delives xen 4.4.2 + centos 7 + bridge networking 


## How To
clone this repo

````
git clone https://github.com/gautamMalu/XenInBox
````
Make an update img

````
scripts/makeupdates -t c7-working -k
````

Use the generated updates.img during installation with inst.updates option in anaconda. https://rhinstaller.github.io/anaconda/boot-options.html#inst-updates 

