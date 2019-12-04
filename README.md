# abtools_control

## Overview

abtools_control is the center of all abtools functionality.


## Installation

Add depencencies

    apt-get install libapache2-mod-wsgi-py3 python3-flask

checkout code

    cd /opt
    git clone https://github.com/abundo/abtools_control.git


create config directory and copy example file there

    mkdir /etc/abtools_control
    cd /etc/abtools_control
    cp /opt/abtools_control/abtools_control-example.yaml abtools_control.yaml

Edit /etc/abtools_control/abtools_control.yaml and adjust accordingly


Enable apache virtual host

    cp /opt/abtools_control/api/control.conf /etc/apache2/sites-available
    a2ensite control
    systemctl restart apache2


Add control to hosts file, to make sure DNS always works when fetching through 'elements API'.
This avoids problems due to script errors, and DNS not working 100% so script cannot contact API

    emacs /etc/hosts

        127.0.0.1 control.net.example.com.

Setup dnsmgr

todo


## API

Implements the "elements API"

All data is read from a local sqlite3 database, which is populated by 
separate scripts.

| file             | description                                          |
| ---------------- | -----------------------------------------------------|
| api/control.conf | apache2 sites configuration                          |
| api/control.wsgi | apache2 mod_wsgi target                              |
| api/api.py       | Implements the "element API", as a python3 flask application |
| api/run_api.py   | Starts the API as a standalode flask debug server    |


## scripts

### sync_elements_to_dns.py

- Fetch all elements through the "elements API"
- Fetch all configuration files from oxidized using REST API
- Parses all configuration files, extracting all interfaces and ip addresses, generating
  DNS records
- Writes a dnsmgr records file
- Asks dnsmgr to update DNS

### sync_becs_to_db.py

- Fetch all elements from BECS (element-attach) of type ibos
- Stores elements in a local sqlite3 database

### sync_netbox_to_db.py

- Fetch all elements and virtual machines from NetBox.
- Stores elements and virtual machines in a local sqlite3 database
