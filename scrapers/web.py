import sys
import time
import json
import socket
import logging
import datetime
import requests
import threading
from PIL import Image  # pip install pillow
from io import BytesIO
from pprint import pprint
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from scraper_monitor import scraper_monitor
from selenium import webdriver

logger = logging.getLogger(__name__)

"""
Things to add for selenium
    - Scroll to load page
    - check if elem is on view and clickable
    - screenshot
"""


class Web:
    """
    Web related functions
    Need to be on its own that way each profile can have its own instance of it for proxy support
    """
    def __init__(self, scraper, driver_type):
        self.ua = UserAgent()
        self.scraper = scraper
        self.driver_type = driver_type.lower()

        # Create a requests session to use throughout
        self.req = requests.Session()

        self.driver = None
        self.is_selenium_enabled = False
        if self.driver_type == 'selenium':
            self.is_selenium_enabled = True

        self.apikey = None
        self.get_apikey()

        # Generate new profile settings
        self.new_profile()

    def new_profile(self, api=False):
        # TODO: Set "Referer" here as well? Would be set to the site you are scraping
        new_ua = self.ua.random
        new_header = {'User-Agent': new_ua,
                      'Accept-Encoding': 'gzip',
                      }

        # Reset the selenium driver
        if self.driver is not None:
            self.driver.quit()
            self.driver = None

        # Create a new profile to use
        self.set_header(new_header)
        self.set_proxy(self.scraper.rotate_proxy())
        # Only get a new apikey if that is what was blocked
        if api is True:
            # Means that the api key was rate limited
            self.apikey_rate_limited()  # Must be before we create a new apikey
            self.get_apikey()

        # TODO Change to info when done debuging
        logger.warning("Created new profile:\n\tIP: {}\n\tHeader: {}\n\tAPI Key: {}"
                       .format(self.get_external_ip(),
                               new_ua,
                               self.apikey))

        # Need to be create after so the headers and proxies take affect
        if self.is_selenium_enabled is True:
            self.driver = webdriver.PhantomJS()
            self.driver.set_window_size(1024, 768)

    def get_apikey(self):
        self.apikey = self.scraper.rotate_apikey()

    def apikey_rate_limited(self):
        """
        apikey has been banned/blocked or is incorrect
        We need a new one
        """

        with self.scraper.db.getcursor() as cur:
            # Update the apikey table that this key was 401'd
            cur.execute("""SELECT times_rate_limited
                        FROM """ + self.scraper.platform + """.apikey
                        WHERE key=%s""", (self.apikey,))
            result = cur.fetchone()
            times_rate_limited = result[0]

            # Update apikey data
            timestamp = datetime.datetime.utcnow()
            cur.execute("""UPDATE """ + self.scraper.platform + """.apikey
                        SET last_rate_limited=%s, times_rate_limited=%s
                        WHERE key=%s""",
                        (timestamp, times_rate_limited+1, self.apikey))

            # Add apikey_log that this key was rate limited
            cur.execute("""UPDATE """ + self.scraper.platform + """.apikey_log
                        SET was_rate_limited=%s
                        WHERE apikey_key=%s AND scrape_id=%s AND thread_name=%s""",
                        (True,
                         self.apikey,
                         self.scraper.uid,
                         threading.currentThread().name))

    def set_proxy(self, proxy):
        # Set proxy for requests
        self.req.proxies = {'http': proxy,
                            'https': proxy
                            }

        # Set proxy for PhantomJS
        if self.is_selenium_enabled is True:
            pass

    def set_header(self, headers):
        # Set headers for requests
        self.req.headers.update(headers)

        # Set headers for PhantomJS
        if self.is_selenium_enabled is True:
            pass
            webdriver.DesiredCapabilities.PHANTOMJS["phantomjs.page.settings.userAgent"] = headers['User-Agent']
            webdriver.DesiredCapabilities.PHANTOMJS["phantomjs.page.settings.acceptEncoding"] = headers['Accept-Encoding']

    def get_external_ip(self):
        json = self.get_site_requests('https://api.ipify.org/?format=json', page_format='json')
        ip = json.get('ip')
        return ip

    def get_internal_ip():
        return socket.gethostbyname(socket.gethostname())

    def get_image_dimension(self, url):
        w_h = (None, None)
        try:
            if url.startswith('//'):
                url = "http:" + url
            data = requests.get(url).content
            im = Image.open(BytesIO(data))

            w_h = im.size
        except Exception:
            logger.warning("Error getting image size {}".format(url), exc_info=True)

        return w_h

    def get_soup(self, raw_content, input_type='html'):
        rdata = None
        if input_type == 'html':
            rdata = BeautifulSoup(raw_content, "html.parser")  # html5lib
        elif input_type == 'xml':
            rdata = BeautifulSoup(raw_content, "lxml")
        return rdata

    def get_selenium_header(self):
        javaScript = """
                     function parseResponseHeaders( headerStr ){
                       var headers = {};
                       if( !headerStr ){
                         return headers;
                       }
                       var headerPairs = headerStr.split('\\u000d\\u000a');
                       for( var i = 0; i < headerPairs.length; i++ ){
                         var headerPair = headerPairs[i];
                         var index = headerPair.indexOf('\\u003a\\u0020');
                         if( index > 0 ){
                           var key = headerPair.substring(0, index);
                           var val = headerPair.substring(index + 2);
                           headers[key] = val;
                         }
                       }
                       return headers;
                     }
                     var req = new XMLHttpRequest();
                     req.open('GET', document.location, false);
                     req.send(null);
                     var header = parseResponseHeaders(req.getAllResponseHeaders().toLowerCase());
                     header['status-code'] = req.status;
                     header['status-text'] = req.statusText;
                     return header;
                     """
        return self.driver.execute_script(javaScript)

    def get_site(self, *args, **kwargs):
        if self.driver is not None:
            return self.get_site_selenium(*args, **kwargs)
        else:
            return self.get_site_requests(*args, **kwargs)

    def get_site_selenium(self, url_raw, cookies={}, page_format='html', return_on_error=[],
                          num_tries=0, headers={}, api=False):
        num_tries += 1
        url = url_raw

        # Add apikey to url if needed
        # TODO: might be different for each platform, figure that out
        if api is True:
            split_char = '?'
            if '?' in url:
                split_char = '&'
            url += split_char + 'apiKey=' + self.apikey

        try:
            self.driver.get(url)
            header_data = self.get_selenium_header()
        except Exception:
            logger.exception("Error in get_site_selenium() on url {}".format(url))
        else:
            response_code = header_data['status-code']
            if response_code < 400:
                # If the http status code is not an error
                if page_format == 'html':
                    data = self.get_soup(self.driver.page_source, input_type='html')
                elif page_format == 'json':
                    data = json.loads(self.driver.find_element_by_tag_name('body').text)
                elif page_format == 'xml':
                    data = self.get_soup(self.driver.page_source, input_type='xml')
                elif page_format == 'raw':
                    # Return unparsed html
                    # In this case just use selenium's built in find/parsing
                    data = True
                else:
                    data = False

                return data
            else:
                # If http status code is 400 or greater
                print(":(")

                # If the client wants to handle the error
                # TODO: Handle this for selenium
                # Issue because this is not in an exception
                # if int(response_code) in return_on_error:
                #     raise e.with_traceback(sys.exc_info()[2])

                if self._get_site_response_code(url, response_code, api, num_tries) is True:
                    # If True then try request again
                    return self.get_site_selenium(url_raw, headers=headers, page_format=page_format,
                                                  cookies=cookies, num_tries=num_tries, api=api)

    def get_site_requests(self, url_raw, cookies={}, page_format='html', return_on_error=[],
                          num_tries=0, headers={}, api=False):
        """
        Try and return soup or json content, if not throw a RequestsError
        """
        # Timeout in seconds
        timeout = 30
        num_tries += 1
        url = url_raw
        if not url.startswith('http'):
            url = "http://" + url

        # Add apikey to url if needed
        # TODO: might be different for each platform, figure that out
        if api is True:
            split_char = '?'
            if '?' in url:
                split_char = '&'
            url += split_char + 'apiKey=' + self.apikey

        try:
            response = self.req.get(url, headers=headers, cookies=cookies, timeout=timeout)
            if response.status_code == requests.codes.ok:
                # Return the correct format
                if page_format == 'html':
                    data = self.get_soup(response.text, input_type='html')
                elif page_format == 'json':
                    data = response.json()
                elif page_format == 'xml':
                    data = self.get_soup(response.text, input_type='xml')
                elif page_format == 'raw':
                    # Return unparsed html
                    data = response.text

                return data

            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            response_code = str(e.response.status_code)

            # If the client wants to handle the error
            if int(response_code) in return_on_error:
                raise e.with_traceback(sys.exc_info()[2])

            if self._get_site_response_code(url, response_code, api, num_tries) is True:
                # If True then try request again
                return self.get_site_requests(url_raw, headers=headers, page_format=page_format,
                                              cookies=cookies, num_tries=num_tries, api=api)

        # Custom errors from requests module
        except requests.exceptions.ConnectionError as e:
            if num_tries < 4:
                logger.info("ConnectionError [get_site_requests] try #{} on {} Error {}".format(num_tries, url, e))
                time.sleep(5)
                return self.get_site_requests(url_raw, headers=headers, page_format=page_format,
                                              cookies=cookies, num_tries=num_tries, api=api)
            else:
                logger.warning("ConnectionError [get_site_requests]: {}".format(url))

        except requests.exceptions.Timeout as e:
            if num_tries < 4:
                logger.info("Request timeout [get_site_requests] try #{} on {} Error {}".format(num_tries, url, e))
                time.sleep(5)
                return self.get_site_requests(url_raw, headers=headers, page_format=page_format,
                                              cookies=cookies, num_tries=num_tries, api=api)
            else:
                logger.warning("Request timeout [get_site_requests]: {}".format(url))
        except requests.exceptions.TooManyRedirects:
            logger.exception("TooManyRedirects [get_site_requests]: {}".format(url))
        except Exception:
            logger.exception("Exception [get_site_requests]: {}".format(url))

    def _get_site_response_code(self, url, response_code, api, num_tries):
        """
        Check the http status code and num_tries to see if it should try again or not
        Log any data needed
        """
        try:
            scraper_monitor.failed_url(url, 'HTTP Status', status_code=response_code, num_tries=num_tries)
        except AttributeError:
            print("\nfailed_url not found\n")
            # Happens when 'logger' object has no attribute 'failed_url'
            pass

        if response_code == '401' and num_tries < 4:
            # Fail after 3 tries
            logger.info("HTTP 401 error, try #{} on url: {}".format(num_tries, url))
            self.new_profile(api)
            logger.warning("401: Created a new profile to use")
            return True
        elif response_code == '403' and num_tries < 4:
            # Fail after 3 tries
            logger.info("HTTP 403 error, try #{} on url: {}".format(num_tries, url))
            self.new_profile(api)
            logger.warning("403: Created a new profile to use")
            return True
        elif response_code == '503' and num_tries < 4:
            # Wait a second and try again, fail after 3 tries
            logger.info("HTTP 503 error, try #{} on url: {}".format(num_tries, url))
            time.sleep(2)
            return True
        elif response_code == '504' and num_tries < 4:
            # Wait a second and try again, fail after 3 tries
            logger.info("HTTP 504 error, try #{} on url: {}".format(num_tries, url))
            time.sleep(1)
            return True
        elif response_code == '520' and num_tries < 4:
            # Wait a second and try again, fail after 3 tries
            logger.info("HTTP 520 error, try #{} on url: {}".format(num_tries, url))
            time.sleep(1)
            return True
        else:
            logger.warning("HTTPError [get_site]\n\t# of Tries: {}\n\tCode: {} - {}"
                           .format(num_tries, response_code, url))

