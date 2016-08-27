import os
import sys
import logging
import argparse
import configparser
import logging.handlers
import custom_utils as cutil

from scrapers.driver_requests import DriverRequests  # Must be above Web import
from scrapers.driver_selenium_chrome import DriverChrome  # Must be above Web import
from scrapers.driver_selenium_firefox import DriverFirefox  # Must be above Web import
from scrapers.driver_selenium_phantomjs import DriverPhantomjs  # Must be above Web import

from scrapers.web import Web, SeleniumHTTPError


# ALWAYS use UTC time for your scraper. That way all data is consistent no matter where it is running from
os.environ['TZ'] = 'UTC'

parser = argparse.ArgumentParser(description='Scraper')
parser.add_argument('-e', '--environment', help='Environment to run in: PROD | DEV (default).',
                    nargs='?', default='DEV')
parser.add_argument('-c', '--config', help='Config file. Default `~/.config/scraper-dev.conf`',
                    nargs='?', default=None)
args = parser.parse_args()

RUN_SCRAPER_AS = args.environment.upper()
SCRAPER_NAME = cutil.get_script_name(ext=False)
SCRAPE_ID = cutil.create_uid()

if RUN_SCRAPER_AS not in ['DEV', 'PROD']:
    print("You must set the env var RUN_SCRAPER_AS to DEV or PROD")
    sys.exit(1)

if args.config is None:
    if RUN_SCRAPER_AS == 'PROD':
        args.config = '~/.config/scraper.conf'
    else:
        args.config = '~/.config/scraper-dev.conf'

args.config = os.path.expanduser(args.config)
args.config = os.path.expandvars(args.config)

raw_config = configparser.ConfigParser()
raw_config.read(args.config)

# Convert raw_config to a dict of only the sections the scraper needs
config = {'global': dict(raw_config['global'].items())}
config.update({'scraper': dict(raw_config[SCRAPER_NAME].items())})

# Check required fileds in config
# TODO....

# Set global logging settings
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Set logs to rotate every day
# By defaut logs will be in a `logs` folder in the users home directoy, edit to move elsewhere
# Also, inside the logs folder, they will be split up by `DEV` and `PROD` so the log messages do not get mixed
log_file = cutil.create_path('{base_log_dir}/{env}/{scraper_name}.log'
                             .format(base_log_dir=config['global'].get('base_log_dir'),
                                     env=RUN_SCRAPER_AS,
                                     scraper_name=SCRAPER_NAME))
# New log files will be created every day to make checking logs simple
rotate_logs = logging.handlers.TimedRotatingFileHandler(log_file,
                                                        when="d",
                                                        interval=1,
                                                        backupCount=0)

# Create formatter for the rotating log files
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
rotate_logs.setFormatter(formatter)
logger.addHandler(rotate_logs)

if raw_config.getboolean('scraper-monitor', 'enabled') is True:
    from scraper_monitor import scraper_monitor
    url = "api/v1/logs?apikey={apikey}&scraperKey={scraper_key}&scraperRun={scrape_id}&environment={env}"\
          .format(apikey=raw_config['scraper-monitor']['apikey'],
                  scraper_key=config['scraper']['scraper_key'],
                  scrape_id=SCRAPE_ID,
                  env=RUN_SCRAPER_AS)

    # Start/configure the scraper monitoring
    scraper_monitor.start(SCRAPER_NAME,
                          raw_config.get('scraper-monitor', 'host'),
                          raw_config.get('scraper-monitor', 'apikey'),
                          config['scraper']['scraper_key'],
                          SCRAPE_ID,
                          RUN_SCRAPER_AS)

    # Send logs to scraper monitor
    http_handler = logging.handlers.HTTPHandler(raw_config.get('scraper-monitor', 'host'), url, method='POST')
    http_handler.setLevel(logging.WARNING)
    logger.addHandler(http_handler)

# Set up S3 bucket if enabled in the config
s3 = None
if raw_config.getboolean('s3', 'enabled') is True:
    from minio import Minio
    from minio.policy import Policy
    from minio.error import ResponseError

    is_s3_secure = False
    if raw_config.get('s3', 'schema') == 'https':
        is_s3_secure = True

    s3 = Minio(raw_config.get('s3', 'host'),
               access_key=raw_config.get('s3', 'access_key'),
               secret_key=raw_config.get('s3', 'secret_key'),
               secure=is_s3_secure)

    # Check if bucket exists, if not create it
    if s3.bucket_exists(SCRAPER_NAME) is False:
        s3.make_bucket(SCRAPER_NAME, location="us-east-1")

    # Set access permissions, default to `private`
    if raw_config.get('s3', 'bucket_policy') == 'read_only':
        bucket_policy = Policy.READ_ONLY
    elif raw_config.get('s3', 'bucket_policy') == 'private':
        bucket_policy = Policy.PRIVATE
    else:
        logger.error('Invalid s3 bucket_policy, setting to private')
        bucket_policy = Policy.PRIVATE

    # TODO: bugs with current version of minio, uncomment when resolved
    # s3.set_bucket_policy(bucket_policy,
    #                      SCRAPER_NAME,
    #                      'data')

# Must be at the bottom so scraper.py has access to all of these settings/vars
from scrapers.scraper import Scraper
