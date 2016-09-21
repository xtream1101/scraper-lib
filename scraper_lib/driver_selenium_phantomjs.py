from selenium import webdriver


class DriverPhantomjs:

    def __init__(self):
        self.phantomjs_service_args = []
        self.last_header_value = None
        self.last_proxy_value = None
        self._create_session()

    def update_header(self, header):
        self.last_header_value.update(header)
        self.set_header(self.last_header_value)

    def set_header(self, header):
        self.last_header_value = header
        user_agent = "phantomjs.page.settings.userAgent"
        accept_encoding = "phantomjs.page.settings.acceptEncoding"
        webdriver.DesiredCapabilities.PHANTOMJS[user_agent] = header.get('User-Agent')
        webdriver.DesiredCapabilities.PHANTOMJS[accept_encoding] = header.get('Accept-Encoding')

        # Recreate webdriver with new header
        self._update()

    def set_proxy(self, proxy_parts):
        """
        Set proxy for requests session
        """
        if proxy_parts is None:
            proxy_parts = {}

        proxy = proxy = proxy_parts.get('curl')
        # Did we change proxies?
        update_web_driver = False
        if self.last_proxy_value != proxy:
            update_web_driver = True
            self.last_proxy_value = proxy

        self.last_proxy_value = proxy
        if proxy is None:
            self.phantomjs_service_args = []
        else:
            self.phantomjs_service_args = ['--proxy={}'.format(proxy),
                                           '--proxy-type=http',
                                           ]

        # Recreate webdriver with new proxy settings
        if update_web_driver is True:
            self._update()

    def _create_session(self):
        """
        Creates a fresh session with no/default headers and proxies
        """
        self.selenium = webdriver.PhantomJS(service_args=self.phantomjs_service_args)
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
        # Clear proxy data
        self.phantomjs_service_args = []
        # Clear headers
        webdriver.DesiredCapabilities.PHANTOMJS = {}
        # Create new web driver
        self._create_session()

    def quit(self):
        """
        Generic function to close distroy and session data
        """
        if self.selenium is not None:
            self.selenium.quit()
        self.selenium = None
