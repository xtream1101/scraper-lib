import queue
import tinys3
import logging
import datetime
import threading
import traceback
# CustomLogger is used for the logger, do not remove it



logger = logging.getLogger(__name__)


class Scraper:

    # TODO: remove proxies and apikeys params
    def __init__(self, cutil):
        self.cutil = cutil

        self.name = self.cutil.get_script_name(ext=False)

        self.uid = self.cutil.create_uid()
        logger.info("Scraper ID: {}".format(self.uid))

        # Setup global threading queue
        self.q = queue.Queue()
        for i in range(2):
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

    def proxy_setup(self, iso_country_code):
        # Set up custom proxy callback
        self._used_proxy_list = []
        self.cutil.custom_proxy_setup(self.custom_rotate_proxy, iso_country_code)

    ###########################################################################
    #
    # Other Functions
    #
    ###########################################################################

    ###########################################################################
    #
    # Proxy switcher callback
    #
    ###########################################################################
    def custom_rotate_proxy(self, iso_country_code):
        """
        :iso_country_code: String - 2 char country code, case-insensitive, ISO 3166 standard
        Must return a proxy string to be used
        """
        iso_country_code = iso_country_code.upper()
        
        # Return custom http proxy
        return None
