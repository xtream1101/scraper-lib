import time
import queue
import tinys3
import logging
import threading
from scrapers import Web
import custom_utils as cutil

logger = logging.getLogger(__name__)


class Scraper:

    def __init__(self, platform, process_queue=2):
        self.platform = platform
        self.name = cutil.get_script_name(ext=False)
        self.uid = cutil.create_uid()

        logger.info("Scraper ID: {}".format(self.uid))
        # Setup global threading queue
        self.q = queue.Queue()
        for i in range(process_queue):
            t = threading.Thread(target=self._process_queue)
            t.daemon = True
            t.start()

    def cleanup(self):
        # Finish anything in the queue
        self.q.join()

    def _process_queue(self):
        while True:
            item = self.q.get()
            try:
                cb = item[0]
                args = item[1]
                kwargs = item[2]
                cb(*args, **kwargs)
            except Exception:
                logger.exception("Error processing queued item {}".format(item))
            self.q.task_done()

    def process(self, cb, *args, **kwargs):
        self.q.put((cb, args, kwargs))

    ###########################################################################
    #
    # Other Functions
    #
    ###########################################################################
    def thread_profile(self, num_threads, driver_type, data, cb_run, *args, **kwargs):
        """
        Create a new Profile for each thread created.

        Parameters
        ----------
        driver_type : str
            Either 'selenium' | 'requests' currently.
        """
        q = queue.Queue()
        item_list = []

        def _thread_run(web):
            while True:
                item = q.get()
                try:
                    item_list.append(cb_run(web, item, *args, **kwargs))
                except Exception:
                    logger.exception("Scraper()._thread_run")
                q.task_done()

        threads = []
        web_instances = []
        for i in range(num_threads):
            web = Web(self, driver_type)
            web_instances.append(web)
            t = threading.Thread(target=_thread_run, args=(web,))
            t.daemon = True
            t.start()
            threads.append(t)
            # Give the thread a second to get set up
            # Needed so all the threads do not grab the same api key
            time.sleep(1)

        # Fill the Queue with the data to process
        for item in data:
            q.put(item)

        # Start processing the data
        q.join()

        # Kill all web drivers
        for web_instance in web_instances:
            if web_instance.driver is not None:
                web_instance.driver.quit()

        return item_list

    def rotate_proxy(self, iso_country_code=None):
        """
        Get a new proxy to use

        :param iso_country_code: String - 2 char country code, case-insensitive, ISO 3166 standard
            Must return a proxy string to be used
        """
        if iso_country_code is None:
            iso_country_code = 'US'
        iso_country_code = iso_country_code.upper()

        proxy = None
        # Get new proxy

        return proxy

    def rotate_apikey(self):
        """
        Return new proxy key and log that the current one is used
        """
        # Get new apikey
        apikey = None

        return apikey
