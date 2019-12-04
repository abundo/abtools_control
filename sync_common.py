#!/usr/bin/env python3 
"""
Common functions for sync utils
"""

import sqlite3

from orderedattrdict import AttrDict


class Element(AttrDict):
    """
    Representation of an element, in NetBox or BECS
    """
    _defaults = {
        "active": True,
        "alarm_destination": [],
        "alarm_timeperiod": "",
        "backup_oxidized": True,
        "comments": "",
        "connection_method": "ssh",
        "role": "",
        "hostname": "",
        "ipv4_addr": "",
        "ipv6_addr": "",
        "interfaces": AttrDict(),
        "manufacturer": "",
        "model": "",
        "monitor_icinga": True,
        "monitor_librenms": True,
        "parents": [],
        "platform": "",
        "site_name": "",
        "tags": [],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for attr, default in self._defaults.items():
            if not hasattr(self, attr):
                setattr(self, attr, default)


class Interface(AttrDict):
    """
    Representation of an interface, in NetBox or BECS
    """
    _defaults = {
        "active": True,
        "name": "",
        "ipv4_prefix": "",
        "ipv6_prefix": "",
        "role": "",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for attr, default in self._defaults.items():
            if not hasattr(self, attr):
                setattr(self, attr, default)


def bool_to_int(b):
    if b:
        return 1
    return 0


def create_db(filename, src=None):
    db = sqlite3.connect(filename)
    cursor = db.cursor()
    cursor.row_factory = sqlite3.Row

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS elements ("\
        "  id INTEGER PRIMARY KEY AUTOINCREMENT" \
        "  ,hostname TEXT" \
        "  ,manufacturer TEXT" \
        "  ,model TEXT" \
        "  ,comments TEXT" \
        "  ,tags TEXT" \
        "  ,parents TEXT" \
        "  ,role TEXT" \
        "  ,site_name TEXT" \
        "  ,platform TEXT" \
        "  ,ipv4_addr TEXT" \
        "  ,ipv6_addr TEXT" \
        "  ,active INTEGER" \
        "  ,alarm_timeperiod TEXT" \
        "  ,alarm_destination TEXT" \
        "  ,connection_method TEXT" \
        "  ,monitor_icinga INTEGER" \
        "  ,monitor_librenms INTEGER" \
        "  ,backup_oxidized INTEGER" \
        "  ,_src TEXT" \
        ")"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS interfaces ("\
        "  id INTEGER PRIMARY KEY AUTOINCREMENT" \
        "  ,elementid INTEGER" \
        "  ,name TEXT" \
        "  ,role TEXT" \
        "  ,ipv4_prefix TEXT" \
        "  ,ipv6_prefix TEXT" \
        "  ,active INTEGER" \
        "  ,_src TEXT" \
        ")"
    )

    # Remove all old elements/interfaces, in a transaction
    cursor.execute("BEGIN")   
    cursor.execute("DELETE FROM elements WHERE _src=?", (src,))
    cursor.execute("DELETE FROM interfaces WHERE _src=?", (src,))
    #cursor.execute("DELETE FROM sqlite_sequence WHERE name='elements'")
    #cursor.execute("DELETE FROM sqlite_sequence WHERE name='interfaces'")

    return db, cursor

def commastr_to_list(hostnames, add_domain=False):
    """
    Return a list of names from a comma separated string
    If add_domain is True, add default domain name if no . (dot) in hostname
    """
    if hostnames:
        tmp = []
        for hostname in hostnames.split(","):
            hostname = hostname.strip()
            if add_domain and "." not in hostname:
                hostname += "." + config.default_domain
            tmp.append(hostname)
        return tmp
    return []
