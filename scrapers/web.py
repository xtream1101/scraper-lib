import os
import sys
import time
import json
import urllib
import logging
import requests
import tempfile
from PIL import Image  # pip install pillow
from io import BytesIO
from bs4 import BeautifulSoup
from selenium import webdriver
import custom_utils as cutil
from fake_useragent import UserAgent
from minio.error import ResponseError
from scraper_monitor import scraper_monitor
from selenium.common.exceptions import TimeoutException, WebDriverException

from scrapers import DriverChrome, DriverFirefox, DriverRequests, DriverPhantomjs

logger = logging.getLogger(__name__)

"""
Things to add:
    - (selenium) Scroll to load page
    - (selenium) check if elem is on view and clickable
    - (requests) screenshot
"""


class SeleniumHTTPError(IOError):
    """
    An HTTP error occurred in Selenium
    Mimic requests.exceptions.HTTPError for status_code
    """

    def __init__(self, *args, **kwargs):
        self.response = type('', (), {})()

        # Match how the status code is formatted in requests.exceptions.HTTPError
        self.response.status_code = kwargs.get('status_code')


class Web:
    """
    Web related functions
    Need to be on its own that way each profile can have its own instance of it for proxy support
    """

    def __init__(self, scraper, driver_type):
        self.ua = UserAgent()
        self.scraper = scraper
        self.driver_type = driver_type.lower()

        # Number of times to re-try a url
        self._num_retries = 3

        # Create a requests session to use throughout
        if self.driver_type == 'requests':
            self.driver = DriverRequests()

        elif self.driver_type == 'selenium_phantomjs' or self.driver_type == 'selenium':
            self.driver = DriverPhantomjs()

        elif self.driver_type == 'selenium_chrome':
            self.driver = DriverChrome()

        elif self.driver_type == 'selenium_firefox':
            self.driver = DriverFirefox()

        else:
            self.driver = None

        self.header = None
        self.proxy = None

        self.apikey = self.get_apikey()

        # Default proxy locale
        self._current_proxy_locale = None

        # Generate new profile settings
        self.new_profile()

    def new_profile(self, api=False):
        """
        Create a new profile with new proxy and header info
        *Firefox does not support auto switching of proxies
        """

        # Set headers for requests and selenium if needed
        self.set_header(self._get_new_header())
        # self.update_header(new_header)

        # Force to change proxy for locale
        self.set_proxy(locale=None, force_new=True)

        # Only get a new apikey if that is what was blocked
        if api is True:
            # Need to make api key jey as ratelimited.
            self.apikey_rate_limited()  # Must be before we create a new apikey
            self.apikey = self.get_apikey()

        # TODO Change to info when done debuging
        logger.warning("Created new profile:\n\tHeader: {}\n\tAPI Key: {}"
                       .format(self.header.get('User-Agent'),
                               self.apikey))

    def get_apikey(self):
        return self.scraper.get_new_apikey()

    def set_header(self, header):
        """
        This is here so the client can set this as well
        """
        self.header = header
        self.driver.set_header(self.header)

    def update_header(self, header):
        """
        Update the headers for the driver that is currently in use
        """
        self.driver.update_header(header)

    def _get_new_header(self):
        # TODO: Set "Referer" here as well? Would be set to the site you are scraping
        new_header = {'User-Agent': self.ua.random,
                      'Accept-Encoding': 'gzip',
                      }
        return new_header

    def set_proxy(self, locale=None, force_new=False):
        """
        This is here so the client can set this as well
        """
        self.proxy = self._get_proxy(locale=locale, force_new=force_new)
        self.driver.set_proxy(self.proxy)

    def _get_proxy(self, locale=None, force_new=False):
        """
        Check `util.proxy_servers` database table and get a proxy from `locale`
        Only get a new proxy if forced to or a different locale is requested
        :force_new: Default `False`. If `True` no matter what locale is requested a new proxy will be used
        """
        proxy_parts = None

        if locale is not None:
            # locale should always be upper case
            locale = locale.upper()

        if locale is None:
            logger.warning("Setting proxy to None")

        elif force_new is True or (locale != self._current_proxy_locale and locale != 'ANY'):
            # Check before changing proxy to see if it is even necessary
            # Set proxy if forced or if the current proxy locale is different then the locale requested
            proxy_parts = self.scraper.get_new_proxy(iso_country_code=locale)
            if proxy_parts is None:
                # This way we can still use .get() with out things breaking
                proxy_parts = {}

            logger.warning("Setting proxy for locale {} to ip {}".format(locale, proxy_parts.get('address')))

        # Store what locale was last used
        self._current_proxy_locale = locale

        return proxy_parts

    def get_image_dimension(self, url):
        """
        Return a tuple that contains (width, height)
        Pass in a url to an image and find out its size without loading the whole file
        If the image wxh could not be found, the tuple will contain `None` values
        """
        w_h = (None, None)
        try:
            if url.startswith('//'):
                url = 'http:' + url
            data = requests.get(url).content
            im = Image.open(BytesIO(data))

            w_h = im.size
        except Exception:
            logger.warning("Error getting image size {}".format(url), exc_info=True)

        return w_h

    def get_soup(self, raw_content, input_type='html'):
        rdata = None
        if input_type == 'html':
            rdata = BeautifulSoup(raw_content, 'html.parser')  # Other option: html5lib
        elif input_type == 'xml':
            rdata = BeautifulSoup(raw_content, 'lxml')
        return rdata

    ###########################################################################
    # Selenium Actions
    ###########################################################################
    def hover(self, element):
        """
        In selenium, move cursor over an element
        :element: Object found using driver.find_...("element_class/id/etc")
        """
        javascript = """var evObj = document.createEvent('MouseEvents');
                        evObj.initMouseEvent(\"mouseover\", true, false, window, 0, 0, 0, 0, 0, \
                        false, false, false, false, 0, null);
                        arguments[0].dispatchEvent(evObj);"""

        if self.driver.selenium is not None:
            self.driver.selenium.execute_script(javascript, element)

    def reload_page(self):
        logger.info("Refreshing page...")
        if self.driver.selenium is not None:
            try:
                # Stop the current loading action before refreshing
                self.driver.selenium.send_keys(webdriver.common.keys.Keys.ESCAPE)
                self.driver.selenium.refresh()
            except Exception:
                logger.exception("Exception when reloading the page")

    def scroll_to_bottom(self):
        """
        Scoll to the very bottom of the page
        TODO: add increment & delay options to scoll slowly down the whole page to let each section load in
        """
        if self.driver.selenium is not None:
            try:
                self.driver.selenium.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except WebDriverException:
                self.driver.selenium.execute_script("window.scrollTo(0, 50000);")
            except Exception:
                logger.exception("Unknown error scrolling page")

    def chrome_fullpage_screenshot(self, file, delay=0):
        """
        Fullscreen workaround for chrome
        Source: http://seleniumpythonqa.blogspot.com/2015/08/generate-full-page-screenshot-in-chrome.html
        """
        total_width = self.driver.selenium.execute_script("return document.body.offsetWidth")
        total_height = self.driver.selenium.execute_script("return document.body.parentNode.scrollHeight")
        viewport_width = self.driver.selenium.execute_script("return document.body.clientWidth")
        viewport_height = self.driver.selenium.execute_script("return window.innerHeight")
        logger.info("Starting chrome full page screenshot workaround. Total: ({0}, {1}), Viewport: ({2},{3})"
                    .format(total_width, total_height, viewport_width, viewport_height))
        rectangles = []

        i = 0
        while i < total_height:
            ii = 0
            top_height = i + viewport_height

            if top_height > total_height:
                top_height = total_height

            while ii < total_width:
                top_width = ii + viewport_width

                if top_width > total_width:
                    top_width = total_width

                logger.debug("Appending rectangle ({0},{1},{2},{3})".format(ii, i, top_width, top_height))
                rectangles.append((ii, i, top_width, top_height))

                ii = ii + viewport_width

            i = i + viewport_height

        stitched_image = Image.new('RGB', (total_width, total_height))
        previous = None
        part = 0

        for rectangle in rectangles:
            if previous is not None:
                self.driver.selenium.execute_script("window.scrollTo({0}, {1})".format(rectangle[0], rectangle[1]))
                logger.debug("Scrolled To ({0},{1})".format(rectangle[0], rectangle[1]))
                time.sleep(delay)

            file_name = "part_{0}.png".format(part)
            logger.debug("Capturing {0} ...".format(file_name))

            self.driver.selenium.get_screenshot_as_file(file_name)
            screenshot = Image.open(file_name)

            if rectangle[1] + viewport_height > total_height:
                offset = (rectangle[0], total_height - viewport_height)
            else:
                offset = (rectangle[0], rectangle[1])

            logger.debug("Adding to stitched image with offset ({0}, {1})".format(offset[0], offset[1]))
            stitched_image.paste(screenshot, offset)

            del screenshot
            os.remove(file_name)
            part = part + 1
            previous = rectangle

        stitched_image.save(file)
        logger.info("Finishing chrome full page screenshot workaround...")
        return True

    def screenshot(self, filename, element=None, delay=0):
        """
        This can be used no matter what driver that is being used
        * ^ Soon requests support will be added

        Save screenshot to local dir with uuid as filename
        then move the file to `filename` (path must be part of the file name)

        Return the filepath of the image
        """
        return_name = None

        if self.driver.selenium is None:
            # If no selenium driver then we are done here
            # TODO: create a self.driver_for_requests if one does not exists for use with requests as a primary
            return None

        # Generate tmp filename
        tmp_filename = {'full': './tmp_screenshots/{}.png'.format(cutil.create_uid()),
                        }
        cutil.create_path(tmp_filename['full'], is_dir=False)
        # The file stored in `save_image` will be the one the user gets
        tmp_filename['save_image'] = tmp_filename['full']

        # If a background color does need to be set
        # self.driver.selenium.execute_script('document.body.style.background = "{}"'.format('white'))

        # Take screenshot
        # Give the page some extra time to load
        time.sleep(delay)
        if self.driver_type == 'selenium_chrome':
            # Need to do this for chrome to get a fullpage screenshot
            self.chrome_fullpage_screenshot(tmp_filename['full'], delay)
        else:
            self.driver.selenium.get_screenshot_as_file(tmp_filename['full'])

        # Use .png extenstion for users save file
        if not filename.endswith('.png'):
            filename += '.png'

        # If an element was passed, just get that element so crop the screenshot
        if element is not None:
            # Create tmp file to save cropped image to
            tmp_filename['cropped'] = './tmp_screenshots/{}.png'.format(cutil.create_uid())
            cutil.create_path(tmp_filename['cropped'], is_dir=False)
            tmp_filename['save_image'] = tmp_filename['cropped']
            # Crop the image
            el_location = element.location
            el_size = element.size
            try:
                cutil.crop_image(tmp_filename['full'],
                                 output_file=tmp_filename['cropped'],
                                 width=int(el_size['width']),
                                 height=int(el_size['height']),
                                 x=int(el_location['x']),
                                 y=int(el_location['y']),
                                 )
            except Exception as e:
                raise e.with_traceback(sys.exc_info()[2])

        # Save to local file system
        # First make sure the correct directories are set up
        cutil.create_path(filename, is_dir=False)
        # Move the file
        os.rename(tmp_filename['save_image'], filename)
        # Always return the absolute path to the saved file
        return_name = os.path.abspath(filename)

        # Now remove any tmp files
        for key in tmp_filename:
            try:
                os.remove(tmp_filename[key])
            except Exception:
                # Try and remove if it can
                pass

        return return_name

    ###########################################################################
    # Get/load page
    ###########################################################################
    def get_selenium_header(self):
        """
        Return server response headers from selenium request
        Also includes the keys `status-code` and `status-text`
        """
        javascript = """
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

        if self.driver.selenium is not None:
            return self.driver.selenium.execute_script(javascript)

    def get_site(self, url, cookies={}, page_format='html', return_on_error=[], retry_enabled=True,
                 num_tries=0, num_apikey_tries=0, headers={}, api=False, track_stat=True, timeout=30,
                 force_requests=False):

        num_tries += 1
        # Save args and kwargs so they can be used for trying the function again
        tmp_args = locals().copy()
        get_site_args = [tmp_args['url']]
        # remove keys that dont belong to the keywords passed in
        del tmp_args['url']
        del tmp_args['self']
        get_site_kwargs = tmp_args

        # Check if a url is being passed in
        if url is None:
            logger.error("Url cannot be None")
            return None

        ##
        # url must start with http....
        ##
        prepend = ''
        if url.startswith('//'):
            prepend = 'http:'

        elif not url.startswith('http'):
            prepend = 'http://'

        url = prepend + url

        ##
        # Add api key to url
        # TODO: might be different for each platform, figure that out
        ##
        if self.apikey is not None and api is True:
            split_char = '?'
            if '?' in url:
                split_char = '&'

            url += split_char + 'apiKey=' + self.apikey

        ##
        # Try and get the page
        ##
        start_time = time.time()  # Stat tracking
        # Log page stats
        if track_stat is True:
            stat_to_track = 'get_site_html'
            if page_format in ('json', 'xml'):
                stat_to_track = 'get_site_not_html'

        rdata = None
        try:
            # Get /parse site data here
            if (self.driver_type.startswith('selenium') and self.driver.selenium is not None)\
                    and force_requests is False:
                rdata = self.get_site_selenium(url,
                                               page_format=page_format,
                                               headers=headers,
                                               cookies=cookies,
                                               timeout=timeout)
            else:
                rdata = self.get_site_requests(url,
                                               page_format=page_format,
                                               headers=headers,
                                               cookies=cookies,
                                               timeout=timeout)

            # This is here to track a successful page load, it is also in each exception to
            #   track stats of error page loads.
            # Cannot use 'finally' since the returns are in the exceptions for trying again
            if track_stat is True:
                self.scraper.track_stat('total_urls', 1)
                self.scraper.track_stat(stat_to_track, time.time() - start_time)  # Stat tracking

        ##
        # Exceptions from Selenium
        ##
        # Nothing yet

        ##
        # Exceptions from Requests
        ##
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            """
            Try again with a new profile (do not get new apikey)
            Wait n seconds before trying again
            """
            if track_stat is True:
                self.scraper.track_stat(stat_to_track, time.time() - start_time)  # Stat tracking

            e_name = type(e).__name__
            if num_tries < self._num_retries and retry_enabled is True:
                logger.info("{} [get_site]: try #{} on {} Error {}".format(e_name, num_tries, url, e))
                # Could be a bad proxy, try again with a new one
                logger.info("{}: Create a new profile to use".format(e_name))
                time.sleep(2)
                # A bad api key would not give this error, no need to get a new one
                self.new_profile(api=False)
                return self.get_site(*get_site_args, **get_site_kwargs)

            else:
                logger.error("{} [get_site]: try #{} on{}".format(e_name, num_tries, url))

        except requests.exceptions.TooManyRedirects as e:
            logger.exception("TooManyRedirects [get_site]: {}".format(url))

        ##
        # Exceptions shared by Selenium and Requests
        ##
        except (requests.exceptions.HTTPError, SeleniumHTTPError) as e:
            """
            Check the status code returned to see what should be done
            """
            if track_stat is True:
                self.scraper.track_stat(stat_to_track, time.time() - start_time)  # Stat tracking

            status_code = str(e.response.status_code)
            # If the client wants to handle the error send it to them
            if int(status_code) in return_on_error:
                raise e.with_traceback(sys.exc_info()[2])

            try_again = self._get_site_status_code(url, status_code, api, num_tries, num_apikey_tries)
            if try_again is True and retry_enabled is True:
                # If True then try request again
                return self.get_site(*get_site_args, **get_site_kwargs)

        # Every other exceptions that were not caught
        except Exception:
            if track_stat is True:
                self.scraper.track_stat(stat_to_track, time.time() - start_time)  # Stat tracking

            logger.exception("Unknown Exception [get_site]: {}".format(url))

        return rdata

    def get_site_selenium(self, url, page_format='html', headers={}, cookies={}, timeout=30):
        """
        Try and return page content in the requested format using selenium
        """
        try:
            # **TODO**: Find what exception this will throw and catch it and call
            #   self.cweb.driver.execute_script("window.stop()")
            # Then still try and get the source from the page
            self.driver.selenium.set_page_load_timeout(timeout)

            self.driver.selenium.get(url)
            header_data = self.get_selenium_header()

        except TimeoutException:
            logger.warning("Page timeout: {}".format(url))
            try:
                scraper_monitor.failed_url(url, 'Timeout')
            except (NameError, AttributeError):
                # Happens when scraper_monitor is not being used/setup
                pass
            except Exception:
                logger.exception("Unknown problem with scraper_monitor sending a failed url")

        except Exception as e:
            raise e.with_traceback(sys.exc_info()[2])

        else:
            # If an exception was not thrown then check the http status code
            status_code = header_data['status-code']
            if status_code < 400:
                # If the http status code is not an error
                rdata = None
                if page_format == 'html':
                    rdata = self.get_soup(self.driver.selenium.page_source, input_type='html')

                elif page_format == 'json':
                    rdata = json.loads(self.driver.selenium.find_element_by_tag_name('body').text)

                elif page_format == 'xml':
                    rdata = self.get_soup(self.driver.selenium.page_source, input_type='xml')

                elif page_format == 'raw':
                    # Return unparsed html
                    # In this case just use selenium's built in find/parsing
                    rdata = True

                else:
                    rdata = False

                return rdata
            else:
                # If http status code is 400 or greater
                raise SeleniumHTTPError("Status code >= 400", status_code=status_code)

    def get_site_requests(self, url, page_format='html', headers={}, cookies={}, timeout=30):
        """
        Try and return page content in the requested format using requests
        """
        try:
            # Headers and cookies are combined to the ones stored in the requests session
            #  Ones passed in here will override the ones in the session if they are the same key
            response = self.driver.req.get(url, headers=headers, cookies=cookies, timeout=timeout)

            if response.status_code == requests.codes.ok:
                # Return the correct format
                rdata = None
                if page_format == 'html':
                    rdata = self.get_soup(response.text, input_type='html')

                elif page_format == 'json':
                    rdata = response.json()

                elif page_format == 'xml':
                    rdata = self.get_soup(response.text, input_type='xml')

                elif page_format == 'raw':
                    # Return unparsed html
                    rdata = response.text

                else:
                    rdata = None

                return rdata

            response.raise_for_status()

        except Exception as e:
            raise e.with_traceback(sys.exc_info()[2])

    def _get_site_status_code(self, url, status_code, api, num_tries, num_apikey_tries):
        """
        Check the http status code and num_tries/num_apikey_tries to see if it should try again or not
        Log any data as needed
        """
        try:
            scraper_monitor.failed_url(url, 'HTTP Status', status_code=status_code, num_tries=num_tries)
        except (NameError, AttributeError):
            # Happens when scraper_monitor is not being used/setup
            pass
        except Exception:
            logger.exception("Unknown problem with scraper_monitor sending a failed url")

        # Make status code an int
        try:
            status_code = int(status_code)
        except ValueError:
            logger.exception("Incorrect status code passed in")
            return None
        # TODO: Try with the same api key 3 times, then try with with a new apikey the same way for 3 times as well
        # try_profile_again = False
        # if api is True and num_apikey_tries < self._num_retries:
        #     # Try with the same apikey/profile again after a short wait
        #     try_profile_again = True

        # status_codes are in a list so we can have any code handled using any code block
        # If we were to do `if status_code < 500` to get all 400 codes, that means we cannot handle
        #   a non 400 code the same way if need be
        # In each list status_codes should be in number order for ease of finding them
        if status_code in [400, 401, 403] and num_tries < self._num_retries:
            # Fail after 3 tries
            logger.info("HTTP {} error, try #{} on url: {}".format(status_code, num_tries, url))
            logger.warning("{}: Create a new profile to use".format(status_code))
            time.sleep(.5)
            self.new_profile(api)
            return True

        elif status_code in [500, 503, 504, 520] and num_tries < self._num_retries:
            # Wait a second and try again, fail after 3 tries
            logger.info("HTTP {} error, try #{} on url: {}".format(status_code, num_tries, url))
            time.sleep(1)
            return True

        else:
            logger.warning("HTTPError [get_site]\n\t# of Tries: {}\n\tCode: {} - {}"
                           .format(num_tries, status_code, url))

        return None

    def download(self, url, filename, header={}, redownload=False):
        """
        Currently does not use the proxied driver
        TODO: Use self.driver.* to download the file. This way we are behind the same proxy and headers
        :return: the path of the file that was saved
        """
        logger.info("Download {url} to {filename}".format(url=url, filename=filename))
        if self.scraper.raw_config.getboolean('s3', 'enabled') is True:
            save_location = os.path.join(tempfile.gettempdir(), cutil.create_uid())

        else:
            save_location = os.path.join(self.scraper.raw_config.get('global', 'base_data_dir'),
                                         self.scraper.SCRAPER_NAME,
                                         filename)
            save_location = cutil.norm_path(save_location)
            if redownload is False:
                # See if we already have the file
                if os.path.isfile(save_location):
                    logger.info("File {save_location} already exists".format(save_location=save_location))
                    return save_location



        # Create the path on disk (excluding the file)
        cutil.create_path(save_location)

        if url.startswith('//'):
            url = "http:" + url
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=header)) as response,\
            open(save_location, 'wb') as out_file:
                data = response.read()
                out_file.write(data)

        except urllib.error.HTTPError as e:
            save_location = None
            # We do not need to show the user 404 errors
            if e.code != 404:
                logger.exception("Download Http Error {url}".format(url=url))

        except Exception:
            save_location = None
            logger.exception("Download Error: {url}".format(url=url))

        if self.scraper.raw_config.getboolean('s3', 'enabled') is True:
            # Upload to s3
            local_file = save_location
            save_location = self.upload_s3(filename, local_file)
            os.remove(local_file)

        return save_location

    def upload_s3(self, filename, local_file):
        """
        Upload file to an s3 service and return the url for that object
        """
        logger.info("Upload {filename} to s3".format(filename=filename))
        return_name = None

        if self.scraper.raw_config.getboolean('s3', 'enabled') is True:
            try:
                upload_path = '{env}/{filename}'.format(env=self.scraper.RUN_SCRAPER_AS, filename=filename)
                self.scraper.s3.fput_object(self.scraper.SCRAPER_NAME, upload_path, local_file)
                return_name = '{schema}://{host}/{bucket}/{file_location}'\
                              .format(schema=self.scraper.raw_config.get('s3', 'schema'),
                                      host=self.scraper.raw_config.get('s3', 'host'),
                                      bucket=self.scraper.SCRAPER_NAME,
                                      file_location=upload_path)

            except ResponseError as error:
                logger.exception("Error uploading file `{filename}` to bucket `{bucket}`"
                                 .format(filename=filename, bucket=self.scraper.SCRAPER_NAME))

        else:
            logger.error("S3 is not enabled")

        return return_name
