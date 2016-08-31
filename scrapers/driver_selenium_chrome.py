from selenium import webdriver


class DriverChrome:

    def __init__(self):
        self.opts = webdriver.ChromeOptions()
        self.last_header_value = None
        self.last_proxy_value = None
        self._create_session()

    def update_header(self, header):
        self.last_header_value.update(header)
        self.set_header(self.last_header_value)

    def set_header(self, header):
        self.last_header_value = header

        for key, value in header.items():
            self.opts.add_argument("{}={}".format(key, value))

        # Recreate webdriver with new header
        self._update()

    def set_proxy(self, proxy_parts):
        """
        Set proxy for chrome session
        """
        if proxy_parts is None:
            proxy_parts = {}

        proxy = proxy_parts.get('curl')
        # Did we change proxies?
        update_web_driver = False
        if self.last_proxy_value != proxy:
            update_web_driver = True
            self.last_proxy_value = proxy

        self.opts.add_argument('--proxy-server={}'.format(proxy))

        # Recreate webdriver with new proxy settings
        if update_web_driver is True:
            self._update()

    def _create_session(self):
        """
        Creates a fresh session with no/default headers and proxies
        """
        self.selenium = webdriver.Chrome(chrome_options=self.opts)
        self.selenium.set_window_size(1920, 1080)

    def _update(self):
        """
        Re create the web driver with the new proxy or header settings
        """
        self.quit()
        self._create_session()

    def reset(self):
        """
        Kills old session and creates a new one with no proxies or headers
        """
        # Kill old connection
        self.quit()
        # Clear chrome configs
        self.opts = webdriver.ChromeOptions()
        # Create new web driver
        self._create_session()

    def quit(self):
        """
        Generic function to close distroy and session data
        """
        if self.selenium is not None:
            self.selenium.quit()
        self.selenium = None
