import logging
from selenium import webdriver

logger = logging.getLogger(__name__)


class DriverFirefox:

    def __init__(self):
        self.profile = webdriver.FirefoxProfile()
        self.last_header_value = None
        self.last_proxy_value = None
        self._create_session()

    def update_header(self, header):
        self.last_header_value.update(header)
        self.set_header(self.last_header_value)

    def set_header(self, header, update_driver=True):
        """
        `update_driver`: Set to false when trying to reload a profile
        """
        self.last_header_value = header

        self.profile.set_preference("general.useragent.override", header.get('User-Agent'))
        self.profile.update_preferences()

        if update_driver is True:
            # Recreate webdriver with new header
            self._update()

    def set_proxy(self, proxy):
        """
        Set proxy for firefox session
        """
        # Did we change proxies?
        update_web_driver = False
        if self.last_proxy_value != proxy:
            update_web_driver = True
            self.last_proxy_value = proxy

        proxy = proxy.split(':')

        self.profile.set_preference("network.proxy.type", 1)
        self.profile.set_preference("network.proxy.http", proxy[0])
        self.profile.set_preference("network.proxy.http_port", proxy[1])
        self.profile.update_preferences()

        # Recreate webdriver with new proxy settings
        if update_web_driver is True:
            self._update()
        logger.warning("Proxies are not supported with the firefox option")

    def _create_session(self):
        """
        Creates a fresh session with no/default headers and proxies
        """
        self.selenium = webdriver.Firefox(firefox_profile=self.profile)
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
        # Clear firefox configs
        self.profile = webdriver.FirefoxProfile()
        # Create new web driver
        self._create_session()

    def quit(self):
        """
        Generic function to close distroy and session data
        """
        if self.selenium is not None:
            self.selenium.quit()
        self.selenium = None
