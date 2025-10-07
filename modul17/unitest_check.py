import unittest
from unittest import TestCase
from rest_con import RESTConnector
from unittest.mock import MagicMock, patch

class TestCase(unittest.TestCase):

    @patch('rest_con.get')
    def test_get_interfaces(self, requests_mock):
        requests_mock.return_value = MagicMock(json=MagicMock(return_value={"hardwareName": 'Ethernet3'}))
        from rest_con import RESTConnector
        conn = RESTConnector('10.10.10.10', 8888, 'user1', 'password')
        conn.connect()
        self.assertEqual({"hardwareName": 'Ethernet3'}, conn.get_interface('Ethernet3'))

    @patch('rest_con.get')
    def testget_netconf_capabilities(self, requests_mock):
        requests_mock.return_value = MagicMock(json=MagicMock(return_value={
            'ietf-netconf-monitoring:capabilities': {
                'capability': [
                    'http://myserver.com/myapiendpoint',
                    'http://myserver.com/myapiendpoint1'
                ]
            }
        }))
        from rest_con import RESTConnector
        conn = RESTConnector('10.10.10.10', 8888, 'user1', 'password')
        conn.connect()
        self.assertEqual(['http://myserver.com/myapiendpoint', 'http://myserver.com/myapiendpoint1'],
                         conn.get_netconf_capabilities())
