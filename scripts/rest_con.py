import urllib3
from requests.auth import HTTPBasicAuth
import requests


class RESTConnector:

    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self._auth = None
        self._session = None
        self._headers = None
        self._url = None
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def connect(self):
        self._auth = HTTPBasicAuth(username=self.username, password=self.password)
        self._headers = {
            'Content-Type': 'application/yang-data+json',
            'Accept': 'application/yang-data+json',
        }
        self._url = f'https://{self.ip}:{self.port}'

    def get_interface(self, name: str):
        endpoint = f'/restconf/data/ietf-interfaces:interfaces/interface={name}'
        url = self._url + endpoint
        response = requests.get(url=url, auth=self._auth, headers=self._headers, verify=False)
        return response.json()


    def get_restconf_capabilities(self):
        restconf = f'/restconf/data/ietf-yang-library:modules-state'
        url = self._url + restconf
        response = requests.get(url, auth=self._auth, headers=self._headers, verify=False)
        json_response = response.json()
        all_yang_endpoints = list(
            map(
                lambda value: value.get('schema', None),
                json_response['ietf-yang-library:modules-state']['module']
            )
        )
        return all_yang_endpoints

    def get_netconf_capabilities(self):
        netconf = f'/restconf/data/netconf-state/capabilities'
        url = self._url + netconf
        response = requests.get(url, auth=self._auth, headers=self._headers, verify=False)
        json_response = response.json()
        all_netconf_endpoints = list(
            filter(
                lambda value: re.findall(r'^http', value),
                json_response['ietf-netconf-monitoring:capabilities']['capability']
            )
        )
        return all_netconf_endpoints