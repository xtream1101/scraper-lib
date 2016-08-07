import time
import queue
import numbers
import logging
import threading
import configparser
from scrapers import Web
from custom_utils import Database
import custom_utils as cutil

logger = logging.getLogger(__name__)


class Scraper:

    def __init__(self, platform, scrape_id, run_scraper_as='DEV', config_file=None):
        self.platform = platform
        self.RUN_SCRAPER_AS = run_scraper_as.upper()
        self.name = cutil.get_script_name(ext=False)
        self.scrape_id = scrape_id

        self._used_proxy_list = []

        if config_file is not None:
            logger.debug("Using config: " + config_file)
            self.config = configparser.ConfigParser()
            self.config.read(config_file)

        logger.info("Scraper ID: {}".format(self.scrape_id))

        # Track the time it takes to do these things
        # Average is a rolling average [<total_amount>, <num_times>]
        #   Calc average by taking <total_amount>/<num_times>
        stats_to_track = ['get_site_html', 'get_site_not_html', 'parse_html_page']
        self.stats = {}
        for stat in stats_to_track:
            self.stats[stat] = {'average': {'total_time': 0,
                                            'total_runs': 0,
                                            },
                                'min': None,
                                'max': None,
                                }

        self.stats['total_urls'] = 0
        self.stats['ref_data_count'] = 0
        self.stats['ref_data_success_count'] = 0
        self.stats['rows_added_to_db'] = 0

        # Create a stats tracking queue.
        # Having a single queue with a single thread makes adding to the stats "thread safe"
        self.stat_queue = queue.Queue()
        stat_thread = threading.Thread(target=self._process_stat_queue)
        stat_thread.daemon = True
        stat_thread.start()

        # Setup global threading queue
        self.q = queue.Queue()
        for i in range(5):
            t = threading.Thread(target=self._process_queue)
            t.daemon = True
            t.start()

    def db_setup(self, db_config):
        self.db = Database(db_config)

    def cleanup(self):
        # Finish anything in the queue
        self.q.join()
        self.stat_queue.join()

    def _process_stat_queue(self):
        while True:
            data = self.stat_queue.get()
            try:
                stat_to_track = data[0]
                value = data[1]
                if stat_to_track not in self.stats:
                    logger.error("Cannot track {}".format(stat_to_track))
                    continue

                # Check what type of data it is
                if isinstance(self.stats[stat_to_track], numbers.Number) is True:
                    # Its is just a number we want to change
                    self.stats[stat_to_track] += value

                else:
                    # Add data for average/min/max

                    # Update max value
                    if self.stats[stat_to_track]['max'] is None:
                        self.stats[stat_to_track]['max'] = value
                    if value > self.stats[stat_to_track]['max']:
                        self.stats[stat_to_track]['max'] = value

                    # Update min value
                    if self.stats[stat_to_track]['min'] is None:
                        self.stats[stat_to_track]['min'] = value
                    if value < self.stats[stat_to_track]['min']:
                        self.stats[stat_to_track]['min'] = value

                    # Update average values
                    self.stats[stat_to_track]['average']['total_time'] += value
                    self.stats[stat_to_track]['average']['total_runs'] += 1

            except Exception:
                logger.exception("Error processing tracking data {}".format(data))

            self.stat_queue.task_done()

    def _process_queue(self):
        while True:
            item = self.q.get()
            try:
                callback = item[0]
                args = item[1]
                kwargs = item[2]
                callback(*args, **kwargs)
            except Exception:
                logger.exception("Error processing queued item {}".format(item))
            self.q.task_done()

    def process(self, callback, *args, **kwargs):
        self.q.put((callback, args, kwargs))

    ###########################################################################
    #
    # Other Functions
    #
    ###########################################################################
    def track_stat(self, stat_to_track, value):
        self.stat_queue.put([stat_to_track, value])

    def thread_profile(self, num_threads, driver_type, data, callback, *args, **kwargs):
        """
        Create a new Profile for each thread created.

        Parameters
        ----------
        driver_type : str
            Either 'selenium' | 'requests' currently.

        """
        if num_threads <= 0:
            logger.error("Must have at least 1 thread for thread_profile, not {}".format(num_threads))
            return []

        q = queue.Queue()
        item_list = []

        def _thread_run():
            web = Web(self, driver_type)
            web_instances.append(web)
            while True:
                item = q.get()
                try:
                    item_list.append(callback(web, item, *args, **kwargs))
                except Exception:
                    logger.exception("Scraper()._thread_run")
                q.task_done()

        threads = []
        web_instances = []
        for i in range(num_threads):
            t = threading.Thread(target=_thread_run, args=())
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
                try:
                    web_instance.driver.quit()
                except AttributeError:
                    # Requests has no .quit(), so this will be thrown
                    pass

        return item_list

    ###########################################################################
    #
    # Proxy/apikey switcher callback
    # Currently being called from Web()
    #
    ###########################################################################
    def get_new_proxy(self, iso_country_code='US'):
        """
        if iso_country_code is None, a random proxy will be choosen from a pool of all locales
        :param iso_country_code: String - 2 char country code, case-insensitive, ISO 3166 standard
        :return: a dict with the parts 'protocol', 'username', 'password', 'address', 'port'
        """
        selected_proxy = {'protocol': None,
                          'username': None,
                          'password': None,
                          'address': None,
                          'port': None,
                          }

        # TODO

        return selected_proxy

    def get_new_apikey(self):
        """
        :returns: A string that is a new api key to be used. `None` if no api keys are found
        """
        # Store the api to be returned
        apikey = None

        # TODO

        return apikey
