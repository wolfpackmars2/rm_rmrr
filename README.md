# no updates
There are no plans to maintain these scripts. However, there are some useful bits that can help when working with Proxmox.

# fix locale errors in Ubuntu containers
    if (locale 2>&1 | grep \"locale: Cannot set\"); then" + "\n"
        echo "Fixing Locales"
        echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
        locale-gen
        update-locale LANG=en_US.UTF-8 UTF-8
        dpkg-reconfigure --frontend=noninteractive locales


# rm_rmrr
Remove RMRR check from PVE kernel
-rwxr--r-- dosh.sh       - Do_Shell. notes/actions for setting up a virgin PVE instance
-rw-r--r-- fix-rmrr.sh   - Version 2 of the sh script
-rw-r--r-- notes.txt     - misc notes for reference
-rw-r--r-- rm_rmrr.sh    - Version 1 of the sh script
drwxr-xrwx shared        - shared dir containing heredocs from fix-rmrr.sh. will be removed
