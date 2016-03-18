import sys
import logging
import requests
import datetime

logger = logging.getLogger(__name__)


class ScraperMonitor(logging.Logger):

    def __init__(self, name):
        super().__init__(name)
        self.config = None

    def start(self, scraper_name, host, apikey, scraper_key, scraper_run):
        # requests needs the host to start with http(s)
        if not host.startswith('http'):
            host = 'http://' + host

        self.config = {}
        self.config['scraper_name'] = scraper_name
        self.config['host'] = host
        self.config['apikey'] = apikey
        self.config['scraper_key'] = scraper_key
        self.config['scraper_run'] = scraper_run

        # Tell the server we started the scraper
        scraper_data = {'startTime': str(datetime.datetime.utcnow())}
        self._send('/data/start', scraper_data)

    def stop(self):
        # Tell the leter we finished
        scraper_data = {'stopTime': str(datetime.datetime.utcnow())}
        self._send('/data/stop', scraper_data)

    def _send(self, endpoint, data={}):
        if self.config is None:
            return

        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        if not self.config['host'].endswith('/'):
            self.config['host'] += '/'

        server_url = "{}api/v1{}?apikey={}&scraperKey={}&scraperRun={}"\
                     .format(self.config['host'],
                             endpoint,
                             self.config['apikey'],
                             self.config['scraper_key'],
                             self.config['scraper_run'],
                             )
        try:
            r = requests.post(server_url, json=data, timeout=10.00).json()
            if r['success'] is not True:
                print("Error: " + r['message'])
        except KeyError:
            print("Error: " + r['message'])
        except requests.exceptions.Timeout:
            logger.exception("Request timeout while sending scraper data")
        except Exception:
            logger.exception("Something broke in sending scraper data")
