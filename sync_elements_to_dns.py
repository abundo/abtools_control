#!/usr/bin/env python3

"""
- Get list of elements from "element API", with their management IP address
- Go through all element configuration files, and parse out interface addresses
- Write records file for dnsmgr and update DNS

"""

# ----- Start of configuration items -----

CONFIG_FILE="/etc/abtools/abtools_control.yaml"
CONFIG_OXIDIZED_FILE ="/etc/abtools/abtools_oxidized.yaml"

# ----- End of configuration items -----

import os
import sys
import requests
import subprocess
import ipaddress

from orderedattrdict import AttrDict

sys.path.insert(0, "/opt")
import ablib.utils as utils
from ablib.elements import Elements_Mgr
from ablib.oxidized import Oxidized_Mgr

print("----- Loading configuration -----")
config = utils.load_config(CONFIG_FILE)
config_oxidized = utils.load_config(CONFIG_OXIDIZED_FILE)

def ifname_to_dnsname(hostname, ifname):
    hostname = hostname.split(".")[0]
    name = "%s.%s" % (hostname, ifname)
    name = name.replace("/", "-").replace(" ", "")
    return name

class Config_Parser:
    """
    Parse a router/switch config
    Try to handle different vendors syntax; cisco, huawei etc
    Extract all interfaces and their IP addresses
    returns an dict, key is interfacename value is {hostname, type, value}
    """
  
    def parse(self, records, hostname, conf):
        intf = None
        ix = 0
        while ix < len(conf):
            line = conf[ix]
            ix += 1
            if not line.startswith("interface "):
                continue
            ifname = line[10:].lower()

            # Shorten interface name if needed, and replace forward slash
            name = ifname_to_dnsname(hostname, ifname)

            # Loop through all config lines for this interface
            while ix < len(conf):
                line =  conf[ix].rstrip()
                ix += 1
                if line == "" or line[0] == "!" or line[0] == "#":
                    break # end if this interface config
                line = line.strip()
                if line.startswith("ip address "):
                    addr = line[11:].split()[0]
                    try:
                        tmp = ipaddress.IPv4Address(addr)
                        record = AttrDict(hostname=name, type="A", value=addr, host=False)
                        if name not in records:
                            records[name] = record
                    except ipaddress.AddressValueError:
                        print("Error: hostname '%s', ipv4_addr '%s' incorrect" % (name, addr))

                elif line.startswith("ipv4 address "):
                    addr = line[12:].split()[0]
                    try:
                        tmp = ipaddress.IPv4Address(addr)
                        record = AttrDict(hostname=name, type="A", value=addr, host=False)
                        if name not in records:
                            records[name] = record
                    except ipaddress.AddressValueError:
                        print("Error: hostname '%s', ipv4_addr '%s' incorrect" % (name, addr))

                elif line.startswith("ipv6 address "):
                    addr = line[13:].split("/")[0]
                    try:
                        tmp = ipaddress.IPv6Address(addr)
                        record = AttrDict(hostname=name, type="AAAA", value=addr, host=False)
                        if name not in records:
                            records[name] = record
                    except ipaddress.AddressValueError:
                        print("Error: hostname '%s', ipv6_addr '%s' incorrect" % (name, addr))
                
        return records


def add_elements_api_hosts(elements=None, records=None):
    """
    Go through all elements from element API
    - Create record from hostname and management IP address
    - Adds record to records{}
    """
    print()
    print("----- Adding elements API host addresses")
    for name, element in elements.items():
        if element["ipv4_addr"]:
            if name.endswith(config.default_domain):
                name = name[:-len(config.default_domain)-1]
            if name in records:
                continue
            addr = element["ipv4_addr"].split("/")[0]    # Remove prefixlen
            record = AttrDict(hostname=name, type="A", value=addr, host=True)
            records[name] = record


def add_elements_api_interfaces(elements=None, records=None):
    """
    Go through all elements and interfaces from element API
    - Convert interface name to something that can be put in DNS
    - Adds record to records{}
    """
    print()
    print("----- Adding elements API interface addresses")
    for hostname, element in elements.items():
        if "interfaces" in element:
            for ifname, interface in element["interfaces"].items():
                if "ipv4_prefix" in interface and interface["ipv4_prefix"]:
                    name = ifname_to_dnsname(hostname, ifname)
                    addr = interface["ipv4_prefix"].split("/")[0]    # Remove prefixlen
                    record = AttrDict(hostname=name, type="A", value=addr, host=False)
                    if name not in records:
                        records[name] = record
                    else:
                        print("Error, name conflict, name %s already exist" % name)


def parse_element_config(oxidized_mgr=None, elements=None, records=None):
    """
    Go through all elements from element API
    - fetch last running-configuration file
    - parse each config file for interface addresses
    - Convert interface name to something that can be put in DNS
    - Adds record to records{}
    """
    print()
    print("----- Parsing all element configuration, searching for IP addresses")
    parser = Config_Parser()
    for hostname, element in elements.items():
        if "backup_oxidized" in element and element["backup_oxidized"] == False:
            # print("  Ignoring backup_oxidized' is False, hostname '%s'" % hostname)
            continue
        if "platform" in element and element["platform"] in config.sync_dns.ignore_platforms:
            # print("  Ignoring platform '%s', hostname '%s'" % (element["platform"], hostname))
            continue
        if "model" in element and element["model"] in config.sync_dns.ignore_models:
            # print("  Ignoring model '%s', hostname '%s'" % (element["model"], hostname))
            continue

        element_conf = oxidized_mgr.get_element_config(hostname)
        if element_conf is not None:
            tmp_records = parser.parse(records, hostname, element_conf.split("\n"))
        else:
            print("Warning: Missing configuration backup for %s" % hostname)


def write_dnsmgr_records(elements, records):
    """
    Write a DnsMgr records file, and ask DnsMgr to update nameserver
    """
    print()
    print("----- Writing dnsmgr records -----")
    ipv4_addr = {}

    with open(config.sync_dns.dest_record_file, "w") as f:
        f.write(";\n")
        f.write("; Autogenerated from elements management address\n")
        f.write(";\n")
        f.write("$DOMAIN %s\n" % config.default_domain)

        # Write forward entries, hostname
        f.write(";\n")
        f.write("; Forward entries, hostname\n")
        f.write(";\n")
        f.write("\n")
        f.write("$FORWARD 1\n")
        f.write("$REVERSE 1\n")
        f.write("\n")
        for record in records.values():
            if record.host:
                ipv4_addr[record.value] = 1
                f.write("%-40s  %-4s   %s\n" % (record.hostname, record.type, record.value))

        # Write forward entries, names that should not have reverse DNS
        # typically loopbacks, which already have hostname entry
        f.write(";\n")
        f.write("; Forward entries, interfaces\n")
        f.write(";\n")
        f.write("\n")
        f.write("$FORWARD 1\n")
        f.write("$REVERSE 0\n")
        f.write("\n")
        for record in records.values():
            if not record.host:
                if record.value in ipv4_addr:
                    f.write("%-40s  %-4s   %s\n" % (record.hostname, record.type, record.value))

        # Write reverse entries
        f.write(";\n")
        f.write("; Reverse entries, interfaces\n")
        f.write(";\n")
        f.write("\n")
        f.write("$FORWARD 1\n")
        f.write("$REVERSE 1\n")
        f.write("\n")
        f.write(";\n")
        for record in records.values():
            if not record.host:
                if record.value not in ipv4_addr:
                    f.write("%-40s  %-4s   %s\n" % (record.hostname, record.type, record.value))

    print()
    print("----- Request dnsmgr to update DNS/bind -----")
    os.system("/opt/dnsmgr/dnsmgr.py update")


def main():
    records = AttrDict()

    oxidized_mgr = Oxidized_Mgr(config=config_oxidized.oxidized)

    print("----- Get elements from Elements API -----")
    elements_mgr = Elements_Mgr(config=config.elements)
    elements = elements_mgr.get_elements()
    
    add_elements_api_hosts(elements=elements, records=records)
    add_elements_api_interfaces(elements=elements, records=records)
    parse_element_config(oxidized_mgr=oxidized_mgr, elements=elements, records=records)
    write_dnsmgr_records(elements, records)


if __name__ == "__main__":
    try:
        main()
    except:
        # Error in script, send traceback to developer
        utils.send_traceback()
