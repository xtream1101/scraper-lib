import requests


class DriverRequests:

    def __init__(self):
        self._create_session()

    def set_header(self, header):
        self.req.headers = header

    def update_header(self, header):
        self.req.headers.update(header)

    def set_proxy(self, proxy_parts):
        """
        Set proxy for requests session
        """
        if proxy_parts is None:
            proxy_parts = {}

        proxy = proxy_parts.get('curl')
        if proxy is None:
            self.req.proxies = {'http': None,
                                'https': None
                                }
        else:
            self.req.proxies = {'http': proxy,
                                'https': proxy
                                }

    def _create_session(self):
        """
        Creates a fresh session with no/default headers and proxies
        """
        self.req = requests.Session()

    def reset(self):
        """
        Kills old session and creates a new one with no proxies or headers
        """
        self.req = None
        self._create_session()

    def quit(self):
        """
        Generic function to close distroy and session data
        """
        self.req = None
