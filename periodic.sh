#!/bin/bash
#

cd /opt/abtools_control

echo ###########################################################################
echo ! Get all elements, IP addresses from BECS, store in local db
echo ###########################################################################
./sync_becs_to_db.py

echo ###########################################################################
echo ! Get all elements, IP addresses from NetBox, store in local db
echo ###########################################################################
./sync_netbox_to_db.py

echo ###########################################################################
echo !  Update DNS
echo ###########################################################################
./sync_elements_to_dns.py
