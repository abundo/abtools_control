#!/usr/bin/env python3
"""
sudo apt-get install libapache2-mod-wsgi-py3
sudo pip3 install pynetbox
"""

import sys
import yaml
import requests
import sqlite3

from orderedattrdict import AttrDict
import pynetbox
from flask import Flask,jsonify

sys.path.insert(0, "/opt")
import abtools_control.sync_common as common
import ablib.utils as utils

# ----- Start of configuration items -----

CONFIG_FILE="/etc/abtools/abtools_control.yaml"

# ----- End of configuration items -----


# Load configuration
config = utils.load_config(CONFIG_FILE)

app = Flask(__name__)


def get_elements_db(elements, hostname=None):
    """
    Read one or all elements from local database
    Local database content is updated/synced from NetBox periodically by a separate program
    """
    db = sqlite3.connect(config.sync_db)
    ce = db.cursor()
    ce.row_factory = sqlite3.Row
    ci = None
    if hostname:
        ce.execute("SELECT * FROM elements WHERE hostname=?", (hostname,))
    else:
        ce.execute("SELECT * FROM elements")

    for element_row in ce:
        element = common.Element()
        element.hostname = element_row["hostname"]
        element.manufacturer = element_row["manufacturer"]
        element.model = element_row["model"]
        element.comments = element_row["comments"]
        element.tags = common.commastr_to_list(element_row["tags"], add_domain=False)
        element.parents = common.commastr_to_list(element_row["parents"], add_domain=True)
        element.role = element_row["role"]
        element.site_name = element_row["site_name"]
        element.platform = element_row["platform"]
        element.ipv4_addr = element_row["ipv4_addr"]
        element.ipv6_addr = element_row["ipv6_addr"]
        element.active = element_row["active"] == 1  # to boolean

        element.alarm_timeperiod = element_row["alarm_timeperiod"]
        element.alarm_destination = common.commastr_to_list(element_row["alarm_destination"], add_domain=False)
        element.connection_method = element_row["connection_method"]
        element.monitor_icinga = element_row["monitor_icinga"] == 1  # to boolean
        element.monitor_librenms = element_row["monitor_librenms"] == 1  # to boolean 
        element.backup_oxidized = element_row["backup_oxidized"] == 1  # to boolean

        # Get all element interfaces
        interfaces = AttrDict()
        ci = db.cursor()
        ci.row_factory = sqlite3.Row
        ci.execute("SELECT * FROM interfaces WHERE elementid=?", (element_row["id"],))
        for interface_row in ci:
            interface = common.Interface()
            interface.name = interface_row["name"]
            interface.role = interface_row["role"]
            interface.ipv4_prefix = interface_row["ipv4_prefix"]
            interface.ipv6_prefix = interface_row["ipv6_prefix"]
            interface.active = interface_row["active"] == 1  # to boolean
            interfaces[interface.name] = interface

        element.interfaces = interfaces
        elements[element.hostname] = element

    if ci:
        ci.close()
    ce.close()
    db.close()


@app.route("/")
def hello_world():
    return "elements API!\n"


@app.route("/elements")
@app.route("/elements/<hostname>")
def get_elements(hostname=None):
    if hostname and "." not in hostname:
        hostname += "." + config.default_domain
    print(hostname)    
    elements = AttrDict()

    get_elements_db(elements, hostname=hostname)

    return jsonify(elements)
