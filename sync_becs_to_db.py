#!/usr/bin/env python3 
"""
Fetch all elements of type iBOS from BECS

For each element, fetch all interfaces and their ipv4 addresses.
Write this to a sqlite3 database, protected by a transaction
Columns in database uses the netbox names

dependencies:
    sudo pip3 install zeep
"""

import sys
import time
import argparse
import sqlite3

import zeep

import sync_common as common

sys.path.insert(0, "/opt")
import ablib.utils as utils
from ablib.becs import BECS

# ----- Start of configuration items ----------------------------------------

CONFIG_FILE="/etc/abtools/abtools_control.yaml"

# ----- End of configuration items ------------------------------------------

# Load configuration
config = utils.load_config(CONFIG_FILE)


def store_elements_in_db(becs):
    """
    Get all elements (element-attach) from BECS and store in
    local sqlite3 database
    """
    print("----- Get elements from BECS -----")
    becs.get_elements()

    db, cursor = common.create_db(config.sync_db, src="becs")

    print("----- Save elements in local database -----")
    element_count = 0
    interface_count = 0
    for oid, element in becs.elements_oid.items():
        if element["elementtype"] != "ibos":
            continue
        print(element["name"])
        #print(element)

        flags = element["flags"]
        if flags is None:
            active = True   # Default
        else:
            active = flags.find("disable") < 0

        # Get interfaces and their IP addresses for this element-attach
        interfaces = becs.get_interface(oid)

        # Get management IPv4 address, default is to use loopback interface
        for interface in interfaces:
            if interface.name == "loopback0" and interface.prefix:
                element.ipv4_addr = interface.prefix
                break

        if element.ipv4_addr == "":
            # No loopback found or no prefix on loopback, pick first interface with an interface address
            for interface in interfaces:
                if interface.prefix:
                    print("No loopback ip address found, using interface %s, %s" % (interface.name, interface.ipv4_addr))
                    element.ipv4_addr = interface.ipv4_prefix
                    break

        if element.ipv4_addr:
            if "/" in element.ipv4_addr:
                element.ipv4_addr = element.ipv4_addr.split("/")[0]
        else:
            print("No management ip address found, ignoring")
            continue
        element.ipv6_addr = ""   # Todo

        element_count += 1

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

        # todo        element["elementrole"],       # 
        # todo        element["role"],              # 'access.layer3'
        cursor.execute(sql, (
            element["name"],
            "Waystream",           # element.manufacturer
            "",                    # element.model
            "",                    # element.comments
            "",                    # element.tags
            element["_parents"],   # element.parents
            "Access nod",          # element.role     parameters[x]["name"] == "model", parameters[x]["values"][0] = 'ASR5124'
            "",                    # element.site_name
            element.elementtype,   # ibos
            element.ipv4_addr,
            element.ipv6_addr,
            common.bool_to_int(active),
            element["_alarm_timeperiod"],
            element["_alarm_destination"],
            "telnet",              # element.connection_method,
            1,                     # element.monitor_icinga
            1,                     # element.monitor_librenms
            0,                     # element.backup_oxidized
            "becs",                # _src
            )
        )
        element_id = cursor.lastrowid

        for interface in interfaces:
            if interface.prefix:
                print("   ", interface.name, interface.role, interface.prefix)
            prefix = interface.prefix
            if not prefix:
                prefix = ""
            interface_count += 1
            cursor.execute(
                "INSERT INTO interfaces (elementid,name,role,ipv4_prefix,ipv6_prefix,active,_src) values (?,?,?,?,?,?,?)", (
                element_id,
                interface.name,
                interface.role,
                prefix,
                "",    # todo ipv6_prefix
                interface.active,
                "becs",
                )
            )
    
    cursor.execute("COMMIT")
    cursor.close()
    db.close()
    print("Summary")
    print("   Total elements :", len(becs.elements_oid))
    print("   Saved elements :", element_count)
    print("   Interfaces     :", interface_count)


def main():
    becs = BECS(config.becs.eapi, config.becs.username, config.becs.password)
    store_elements_in_db(becs)
    becs.logout()


if __name__ == "__main__":
    try:
        main()
    except:
        utils.send_traceback()
