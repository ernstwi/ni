# -*- coding: utf-8 -*-
"""
Created on 2012-07-04 12:12 PM

@author: lundberg
"""

import sys
import os
from datetime import datetime
import argparse

## Need to change this path depending on where the Django project is
## located.
#path = '/var/norduni/src/niweb/'
path = '/home/lundberg/norduni/src/niweb/'
##
##
sys.path.append(os.path.abspath(path))
import noclook_consumer as nt
import norduni_client as nc
from apps.noclook import helpers as h
from django.db import IntegrityError
from apps.noclook.models import NordunetUniqueId

# This script is used for adding the objects collected with the
# NERDS csv producer from the NORDUnet path spreadsheets.

# "host": {
#     "csv_producer": {
#         "capacity": "",
#         "created": "",
#         "enrs": "",
#         "framing": "",
#         "links": "",
#         "meta_type": "",
#         "name": "",
#         "node_type": ""
#         "provider": ""
#     },
#     "name": "",
#     "version": 1
# }

def depend_on_link(node, link_name):
    """
    Depends the link on supplied equipment and port.
    Port name is in Alcatel-Lucent notation rXsrXslX/port#X.
    """
    link = nt.get_unique_node(link_name, 'Optical Link', 'logical')
    rel = nc.create_relationship(nc.neo4jdb, node, link, 'Depends_on')
    h.set_noclook_auto_manage(nc.neo4jdb, rel, False)


def consume_path_csv(json_list, unique_id_set=None):
    """
    Inserts the data collected with NOCLook csv producer.
    """
    for i in json_list:
        node_type = i['host']['csv_producer']['node_type'].title()
        meta_type = i['host']['csv_producer']['meta_type'].lower()
        path_id = i['host']['name']
        if unique_id_set:
            try:
                unique_id_set.objects.create(unique_id=path_id)
            except IntegrityError:
                print "%s already exists in the database. Please check and add manually" % path_id
                continue
        nh = nt.get_unique_node_handle(nc.neo4jdb, path_id, node_type,
                                       meta_type)
        dt = datetime.strptime(i['host']['csv_producer']['created'], '%Y/%m/%d-%H:%M:%S')
        nh.created = dt
        nh.save()
        node = nh.get_node()
        h.set_noclook_auto_manage(nc.neo4jdb, node, False)
        with nc.neo4jdb.transaction:
            framing = i['host']['csv_producer'].get('framing', None)
            if framing:
                node['framing'] = framing
            capacity = i['host']['csv_producer'].get('capacity', None)
            if capacity:
                node['capacity'] = capacity
            enrs = i['host']['csv_producer'].get('enrs', None)
            if enrs:
                node['enrs'] = nt.normalize_whitespace(enrs).split(',')
            node['nordunet_id'] = node['name']
        h.update_node_search_index(nc.neo4jdb, node)
        # Set provider
        provider_name = i['host']['csv_producer'].get('provider')
        provider = nt.get_unique_node(provider_name, 'Provider', 'relation')
        rel = nc.create_relationship(nc.neo4jdb, provider, node, 'Provides')
        h.set_noclook_auto_manage(nc.neo4jdb, rel, False)
        # Depend on link
        links = i['host']['csv_producer'].get('links', None)
        if links:
            for link in links.split(','):
                link_name = nt.normalize_whitespace(link)
                depend_on_link(node, link_name)


def main():
    # User friendly usage output
    parser = argparse.ArgumentParser()
    parser.add_argument('-D', nargs='?',
                        help='Path to the json data.')

    args = parser.parse_args()
    # Start time
    start = datetime.now()
    timestamp_start = datetime.strftime(start, '%b %d %H:%M:%S')
    print '%s noclook_consumer.py was started.' % timestamp_start
    # Insert data from known data sources if option -I was used
    if args.D:
        print 'Loading data...'
        data = nt.load_json(args.D)
        print 'Inserting data...'
        consume_path_csv(data, NordunetUniqueId)
        print 'noclook consume done.'
    else:
        print 'Use -D to provide the path to the JSON files.'
        sys.exit(1)
        # end time
    end = datetime.now()
    timestamp_end = datetime.strftime(end, '%b %d %H:%M:%S')
    print '%s noclook_consumer.py ran successfully.' % timestamp_end
    timedelta = end - start
    print 'Total time: %s' % timedelta
    return 0

if __name__ == '__main__':
    main()
