import unittest
from unittest.mock import MagicMock, patch


class TestCase(unittest.TestCase):

    @patch('lib.connectors.rest_con.get')
    def test_get_interfaces(self, requests_mock):
        requests_mock.return_value = MagicMock(json=MagicMock(return_value={"hardwareName": 'Ethernet3'}))
        from lib.connectors.rest_con import RESTConnector
        conn = RESTConnector('10.10.10.10', 8888, 'user1', 'password')
        conn.connect()
        self.assertEqual({"hardwareName": 'Ethernet3'}, conn.get_interface('Ethernet3'))

    @patch('lib.connectors.rest_conn.get')
    def test_get_restconf_capabilities(self, requests_mock):
        requests_mock.return_value = MagicMock(json=MagicMock(return_value={
            'ietf-yang-library:modules-state': {
                'module': [{
                    'schema': 'http://myserver.com/myapiendpoint'
                }]
            }
        }))
        from lib.connectors.rest_con import RESTConnector
        conn = RESTConnector('10.10.10.10', 8888, 'user1', 'password')
        conn.connect()
        self.assertEqual(['http://myserver.com/myapiendpoint'], conn.get_restconf_capabilities())

    @patch('lib.connectors.rest_con.get')
    def testget_netconf_capabilities(self, requests_mock):
        requests_mock.return_value = MagicMock(json=MagicMock(return_value={
            'ietf-netconf-monitoring:capabilities': {
                'capability': [
                    'http://myserver.com/myapiendpoint',
                    'http://myserver.com/myapiendpoint1'
                ]
            }
        }))
        from lib.connectors.rest_con import RESTConnector
        conn = RESTConnector('10.10.10.10', 8888, 'user1', 'password')
        conn.connect()
        self.assertEqual(['http://myserver.com/myapiendpoint', 'http://myserver.com/myapiendpoint1'],
                         conn.get_netconf_capabilities())
