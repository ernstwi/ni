# -*- coding: utf-8 -*-
from .neo4j_base import NeoTestCase
from apps.noclook import helpers
from actstream.models import actor_stream
from norduniclient.exceptions import UniqueNodeError


class Neo4jHelpersTest(NeoTestCase):

    def test_delete_node_utf8(self):
        nh = self.create_node(u'æøå-ftw', 'site')
        node = nh.get_node()

        self.assertEqual(u'æøå-ftw', nh.node_name)
        self.assertEqual(u'æøå-ftw', node.data.get('name'))

        helpers.delete_node(self.user, nh.handle_id)
        activities = actor_stream(self.user)
        self.assertEqual(1, len(activities))
        self.assertEqual(u'Site æøå-ftw', activities[0].data.get('noclook', {}).get('object_name'))

    def test_create_unique_node_handle_case_insensitive(self):
        helpers.create_unique_node_handle(
            self.user,
            'awesomeness',
            'host',
            'Physical')
        with self.assertRaises(UniqueNodeError):
            helpers.create_unique_node_handle(
                self.user,
                'AwesomeNess',
                'host',
                'Physical')
