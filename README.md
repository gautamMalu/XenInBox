# XenInBox
Anaconda installer which delives xen 4.4.2 + centos 7 + bridge networking 

## How To
clone this repo

````
git clone https://github.com/gautamMalu/XenInBox
````
Make an update img

````
scripts/makeupdates -t c7-working
````

Use the generated updates.img during installation with inst.updates option in anaconda. https://rhinstaller.github.io/anaconda/boot-options.html#inst-updates 

press Esc at boot selection screen during installation http://goo.gl/57GAMD you will be redirected to boot: prompt
````
boot: linux inst.updates=<path to updates.img>
````

Or you can use this wrapper repo https://github.com/gautamMalu/centos-xen
