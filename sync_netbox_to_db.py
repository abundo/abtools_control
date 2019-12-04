#!/usr/bin/env python3 
"""
Fetch all elements from NetBox

For each element, fetch all interfaces and their ipv4 addresses.
Write this to a sqlite3 database, protected by a transaction
Columns in database uses the netbox names

dependencies:
    sudo pip3 install orderedattrdict
"""

import sys
import time
import argparse
import sqlite3

from orderedattrdict import AttrDict
import pynetbox

import sync_common as common

sys.path.insert(0, "/opt")
import ablib.utils as utils

# ----- Start of configuration items ----------------------------------------

CONFIG_FILE="/etc/abtools/abtools_control.yaml"

# ----- End of configuration items ------------------------------------------

# Load configuration
config = utils.load_config(CONFIG_FILE)

def parse_netbox_api_response(device):
    """
    """
    try:
        hostname = device.name
        if not hostname:
            return None  # No name, ignore device
    except (AttributeError, NameError):
        # No name, ignore device
        return None

    element = common.Element()
    hostname = hostname.lower()
    if "." not in hostname:
        hostname = "%s.%s" % (hostname, config.default_domain)
    element.hostname = hostname
    
    try:
        element.manufacturer = device.device_type.manufacturer.name
    except (AttributeError, NameError):
        pass

    try:
        element.model = device.device_type.model
    except (AttributeError, NameError):
        pass

    element.comments = device.comments
    element.tags = device.tags

    try:
        parents = device.custom_fields["parents"]
        element.parents = common.commastr_to_list(parents, add_domain=True)
    except (AttributeError, NameError):
        pass

    try:
        element.role = device.role.name
    except (AttributeError, NameError):
        pass

    if not element.role:
        # Try old name, netbox is (slowly) changing device_role -> role
        try:
            element.role = device.device_role.name
        except (AttributeError, NameError):
            pass

    try:
        element.site_name = device.site.name
        if element.site_name == "Default":
            element.site_name = ""
    except (AttributeError, NameError):
        pass
    
    try:
        element.platform = device.platform.name
    except (AttributeError, NameError):
        pass

    try:
        element.ipv4_addr = device.primary_ip4.address.split("/")[0]
    except (AttributeError, NameError, KeyError, TypeError):
        pass
    
    # 'status': {'value': 1, 'label': 'Active'}, 
    try:
        label = device.status.label
        if label != "Active":
            element.active = False
    except (AttributeError, NameError):
        pass

    try:
        tmp = device.custom_fields["alarm_timeperiod"]["label"].split()
        if tmp: 
            tmp = tmp[0]
        else:
            tmp = ""
        element.alarm_timeperiod = tmp
    except (AttributeError, NameError, TypeError):
        pass

    try:
        tmp = device.custom_fields["alarm_destination"]["label"]
        element.alarm_destination = common.commastr_to_list(tmp)
    except (AttributeError, NameError):
        pass

    try:
        tmp = device.custom_fields["connection_method"]["label"]
        element.connection_method = tmp
    except (AttributeError, NameError):
        pass

    try:
        element.monitor_icinga = device.custom_fields["monitor_icinga"]
        if element.monitor_icinga is None: element.monitor_icinga = True
    except (AttributeError, NameError):
        pass

    try:
        element.monitor_librenms = device.custom_fields["monitor_librenms"]
        if element.monitor_librenms == None: element.monitor_librenms = True
    except (AttributeError, NameError):
        pass

    try:
        element.backup_oxidized = device.custom_fields["backup_oxidized"]
        if element.backup_oxidized is None: element.backup_oxidized = True
    except (AttributeError, NameError):
        pass

    return element


def get_from_netbox(elements, hostname=None, interfaces=False):
    """
    Get one or all elements from NetBox, devices and virtual machines
    No interfaces are included
    """

    netbox = pynetbox.api(url=config.netbox.url, token=config.netbox.token)

    print("----- Get virtual machines from NetBox -----")
    if hostname:
        # Get one element
        if "." in hostname:
            hostname = hostname.split(".", 1)[0]
        data = [ netbox.virtualization.virtual_machines.get(name=hostname) ]
    else:
        # Get all elements
        data = netbox.virtualization.virtual_machines.all()

    for device in data:
        # utils.pretty_print("device", device)
        element = parse_netbox_api_response(device)
        if element:
            # utils.pretty_print("element", element)
            elements[element.hostname] = element


    print("----- Get elements from NetBox -----")
    if hostname:
        # Get one element
        if "." in hostname:
            hostname = hostname.split(".", 1)[0]
        data = [ netbox.dcim.devices.get(name=hostname) ]
    else:
        # Get all elements
        data = netbox.dcim.devices.all()

    for device in data:
        #utils.pretty_print("device", device)
        element = parse_netbox_api_response(device)
        if element:
            # utils.pretty_print("element", element)
            elements[element.hostname] = element


"""
{   'api': <pynetbox.api.Api object at 0x7f2f77383208>,
    'cluster': Pite Kommun,
    'comments': '',
    'config_context': {},
    'created': '2019-12-03',
    'custom_fields': {},
    'default_ret': <class 'pynetbox.core.response.Record'>,
    'disk': None,
    'endpoint': <pynetbox.core.endpoint.Endpoint object at 0x7f2f753447f0>,
    'has_details': False,
    'id': 7,
    'last_updated': '2019-12-03T14:21:10.349867Z',
    'local_context_data': None,
    'memory': None,
    'name': 'infra12',
    'platform': linux,
    'primary_ip': 1.1.1.2/24,
    'primary_ip4': 1.1.1.2/24,
    'primary_ip6': None,
    'role': Server,
    'site': None,
    'status': Active,
    'tags': [],
    'tenant': None,
    'vcpus': None}
"""


def store_elements_in_db(elements, interfaces=False):
    """
    Get all elements (devices) from NetBox and store in
    local sqlite3 database
    """
    print("----- Save elements in local database -----")
    db, cursor = common.create_db(config.sync_db, src="netbox")

    for hostname, element in elements.items():
        sql = "INSERT INTO elements ("
        sql += "  hostname"
        sql += " ,manufacturer"
        sql += " ,model"
        sql += " ,comments"
        sql += " ,tags"
        sql += " ,parents"
        sql += " ,role"
        sql += " ,site_name"
        sql += " ,platform"
        sql += " ,ipv4_addr"
        sql += " ,ipv6_addr"
        sql += " ,active"
        sql += " ,alarm_timeperiod"
        sql += " ,alarm_destination"
        sql += " ,connection_method"
        sql += " ,monitor_icinga"
        sql += " ,monitor_librenms"
        sql += " ,backup_oxidized"
        sql += " ,_src"
        sql += ") values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"

        cursor.execute(sql, (
            element.hostname,
            element.manufacturer,
            element.model,
            element.comments,
            ",".join(element.tags),
            ",".join(element.parents),
            element.role,
            element.site_name,
            element.platform,
            element.ipv4_addr,
            element.ipv6_addr,
            common.bool_to_int(element.active),
            element.alarm_timeperiod,
            ",".join(element.alarm_destination),
            element.connection_method,
            common.bool_to_int(element.monitor_icinga),
            common.bool_to_int(element.monitor_librenms),
            common.bool_to_int(element.backup_oxidized),
            "netbox",
            )
        )

        element_id = cursor.lastrowid
        if interfaces:
            # Todo, fix for netbox, below code is for BECS

            # Get interfaces and their IP addresses for this element-attach
            interface_data = self.client.service.objectTreeFind(
                {
                    "oid": oid,
                    "classmask": "interface,resource-inet",
                    "walkdown": 2,
                } , 
                _soapheaders = self._soapheaders
            )

            # Get IP address for each interface
            for interface in interface_data["objects"]:
                if interface["class"] == "interface":
                    flags = interface["flags"]
                    if flags is None:
                        active = True
                    else:
                        active = flags.find("disable") < 0
                    # search for the resource-inet in response
                    prefix = None
                    for resource_inet in interface_data["objects"]:
                        if resource_inet["class"] == "resource-inet" and resource_inet["parentoid"] == interface["oid"]:
                            prefix = "%s/%d" % (resource_inet["resource"]["address"], resource_inet["resource"]["prefixlen"])
                            break

                    if prefix:
                        print("   ", interface["name"], interface["role"], prefix)
                    cursor.execute(
                        "INSERT INTO interfaces (elementid,name,role,ipv4_prefix,ipv6_prefix,active) values (?,?,?,?,?,?)", (
                        element_id,
                        interface["name"],
                        interface["role"],
                        prefix,
                        "",
                        active,
                        )
                    )
    
    cursor.execute("COMMIT")
    cursor.close()
    db.close()
    print("Total number of elements:", len(elements))


def main():
    elements = AttrDict()
    get_from_netbox(elements)
    # utils.pretty_print("elements", elements)
    store_elements_in_db(elements)


if __name__ == "__main__":
    try:
        main()
    except:
        # Error in script, send traceback to developer
        utils.send_traceback()
