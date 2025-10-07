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


    def connect(self):
        self._auth = HTTPBasicAuth(username=self.username, password=self.password)
        self._headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        self._url = f'https://{self.ip}:{self.port}'
        response = requests.get(url=self._url, auth=self._auth, headers=self._headers, verify=False)
        print(response.status_code)
        print(response.text)