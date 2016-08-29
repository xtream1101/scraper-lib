# Scraper Library

Developed using Python 3.5 (use at least 3.4.2+)

**TODO: Update functions in Readme **

## Install
- Use pip `pip3 install -e git+https://git.eddyhintze.com/xtream1101/scraper-lib.git@master#egg=scraper_lib`
- Download/clone the repo and run `python3 setup.py install`

When running a scraper, a config file must be passed in that has this content (the same config can be used for all scrapers):
```python
[global]
# All scrapers have access to global
base_log_dir = ~/log/
base_data_dir = ~/scraper-data/

[database]
# http://docs.sqlalchemy.org/en/latest/core/engines.html
uri =


[scraper-monitor]
enabled = false
# Do not have http in host
host =
apikey =

[s3]
enabled = false
# `schema` either http or https
schema = https
host =
access_key =
secret_key =
# Does not work yet
bucket_policy =

##
# Scraper specific
# Create a section for each scraper, use the scraper file name (exclude extension) and the name
##
[xkcd-comics]
# Each scraper may have its own custom values depending on its needs
# Every scraper can and a `scraper_key` if `scraper_monitor` is enabled
scraper_key =
```

## Usage

### **from scrapers import Scraper**

#### After running `__init__` you will have access to these variables:
- **self.platform** - Platform name passed in to `__init__`
- **self.RUN_SCRAPER_AS** - Environment to run in as passed in to `__init__`
- **self.name** - Filename of the scraper not including the `.py` extension
- **self.scrape_id** - Currently a uuid4 hex value (without `-`)
- **self.stats** - A dict used to store various stats about the current scrape session (more details [ref link here]

----------

#### fn: **\_\_init__**
Params:

- **platform** - _Type: String_ - _Positional Argument_
    - Site the scraper will be scraping, e.g. `walmart` | `amazon` | `etc...`
- **scrape_id** - _Type: String_ -  _Positional Argument_
    - UUID that is used to make this instance of the scraper unique
- **run_scraper_as** - _Type: String_ - _Named Argument_ - _Default:_ `DEV`
    - The environment the scraper is running in e.g. `DEV` | `PROD`
- **config_file** - _Type: String_ - _Named Argument_ - _Default:_ `None`
    - Config file to pull values from

----------

#### fn: **process**
Runs any function using a background queue. This is non blocking so once you pass your task the code will move on. The queue is processed using 2 threads and will not return anything.

Uses `self._process_queue` that was setup in `__init__` to process the data

Params:

- **callback** - _Type: string_ - _Positional Argument_
    - Function to run
- **\*args** - _Type: Positional Arguments_
    - Any positional arguments that were passed. Will be passed to `callback`
- **\**kwargs** - _Type: Named Arguments_
    - Any named arguments that were passed. Will be passed to `callback`

----------

#### fn: **cleanup**
Will block the program until all items in all queues are finished being processed. Run at the end of the script right before it quits.

Params: _N/A_

----------

#### fn: **db_setup**
Gives access to `self.db`
TODO: Is this the best place to have this?

Params:

- **db_config** - _Type: Dict_ - A dict that has the keys 'db_name', 'db_user', 'db_host' ,'db_pass'
- **ref_table** - _Type: String_ - Database table that the ref data is pulled from
- **raw_table** - _Type: String_ - Database table that the raw scrape data is saved to

----------

#### fn: **track_stat**
Used for increasing the count of the stats you are tracking.
This is safe to use in threads. This function adds the action to a single queue so the count does not get messed up.

Returns nothing.

Params:

- **stat_to_track** - _Type: String_ - _Positional Argument_
    - The name of the stat you want to update
    - Valid options are: **ref_data_count**, **ref_data_success_count**, **rows_added_to_db**
    - Others used behind the scenes are: **total_urls**, **get_site_html**, **get_site_not_html**, **parse_html_page**

- **value** - _Type: Number_ - _Positional Argument_
    - How much you want to increase or decrease the stat

*Notes:*

- `ref_data_count` - Total number of things you will be checking.
- `ref_data_success_count` - Total number of things that parsed successfully.
- `rows_added_to_db` - Total number of rows affected by `INSERT` or `UPDATE` statements.

----------

#### fn: **thread_profile**
Takes a callback function and a list of data. Using `x` number of threads, pass each item in the list to the callback function one item at a time.
Each time the callback function is called, the data returned is stored in a list. That list is then returned after the list has been fully processed.

Params:

- **num_threads** - _Type: Int_ - _Positional Argument_
    - Number of threads to process the data
- **driver_type** - _Type: string_ - _Positional Argument_
    - Passed to `Web()`. But either `requests` | `selenium`
- **data** - _Type: List_ - _Positional Argument_
    - List of data that needs to be processed. Will be passed to `callback` as the first positional argument
- **callback** - _Type: Function_ - _Positional Argument_
    - The function that will process items in `data`
- **\*args** - _Type: Positional Arguments_
    - Any positional arguments that were passed after the `callback` will be passed as such to the `callback`
- **\**kwargs** - _Type: Named Arguments_
    - Any named arguments that were passed after the `args` will be passed as such to the `callback`


EXAMPLE:
Will pass a single item from the list to the `callback` along with an instance of `Web` _(referenced below)_. Use like so:
```python
# The callback function will look like...
#   self.thread_profile(1, 'requests', keyword_list, self.parse_item)
def parse_item(self, web, item):
    # `web` is an instance of `Web()` and is unique for each thread that was created
    # `item` is a single item from the list passed into `thread_profile`
    pass

# If you pass a few args and kwargs with it
#   self.thread_profile(1, 'requests', keyword_list, self.parse_item, some_id, something=True, thing='bar')
def parse_item(self, web, item, ref_id, something=False, thing='foo'):
    pass

# If it was a class passed in rather then a function
#   self.thread_profile(1, 'requests', keyword_list, Worker)
class Worker:
    def __init__(self, web, item):
        self.web = web
```
----------

#### fn: **get_new_proxy**
_Used by `Web()` to switch proxies_
Returns a dictionary with the keys of `protocol`, `username`, `password`, `address`

Params:
- **iso_country_code**  - _Type: String_ - _Named Argument_ - _Default:_ `US`

  - The country in which the proxy should be located
  - Will return a proxy from a random location **if**:
    - `iso_country_code` is `None`
    - Cannot find a proxy for `iso_country_code`

*Notes:*
Codes `GB` & `UK` will resolve to `GB`

----------

#### fn: **get_new_apikey**
_Used by `Web()` to switch api keys_
Returns an apikey as a string. This is accomplished by looking in the platforms schema in the `apikey` table. If no valid keys are found or the table does not exist thins function will return `None`

Params: _N/A_








### **from scrapers import Web**

Contains anything related to getting/processing things from the web. Each instance of this class will create a new _profile_ that it will use for any and all web requests.

It will try and get an api key from the `Scraper.get_new_apikey()` and a proxy from `Scraper.get_new_proxy()`, the dufault proxy it will get is a "US" proxy. This is because the best speed will be from the US (which is closest to our servers)

#### fn: **\_\_init__**
Params:

- **scraper** - _Type: Class Object_ - _Positional Argument_
    - `self` is passed in for this to have access to all functions in `Scraper`
- **driver_type** - _Type: String_ -  _Positional Argument_
    - Either:
        - `requests` - Requests
        - `selenium` | `selenium_phantomjs` - PhantomJS
        - `selenium_chrome` - Chrome web driver
        - `selenium_firefox` - Firefox driver (No proxy support)

----------

#### fn: **new_profile**
Params:

- **api** - _Type: Boolean_ - _Named Argument_ - _Default:_ `False`
    - When `False`, the api key will not be rotated (get a new one)
    - When `True`, the api key will be flagged as _rate limited_ and a new key will be used

----------

#### fn: **get_apikey**
Calls `get_new_apikey()` from `Scraper`

Params: _N/A_

----------

#### fn: **apikey_rate_limited**
Call if the current api key has been blocked or rate limited (for the day). In the platforms `apikey` database table this will update `last_rate_limited` and `times_rate_limited`. As well as add a row to `apikey_log` table.

Params: _N/A_

----------

#### fn: **set_proxy**
Params:

- **locale** - _Type: String_ - _Named Argument_ - _Default:_ `None`
    - The country you want to proxy to be from
    - If set to `None`, no proxy will be used and the machine external ip will be used
    - If set to `ANY`, will get a random proxy to use
- **force_new** - _Type: Boolean_ -  _Named Argument_ - _Default:_ `False`
    - By default this will only get and set a new proxy if the locale requested is different then the current proxies locale.
    - When `True`, this will get a new proxy for the locale requested

----------

#### fn: **update_header**
By default `new_profile` sets a random User agent as well as `'Accept-Encoding': 'gzip'`

Params:

- **headers** - _Type: Dict_ - _Positional Argument_
    - Headers to be set. All headers will be set for requests.
    - Only `User-Agent` and `Accept-Encoding` will be set for `phantomjs` at this time.
    - Only `User-Agent` will be set for `firefox` at this time.


----------

#### fn: **set_header**
Unlike update, this will clear all headers and just set the ones passed in.
*WIP* Currently just adds/updates the header and does not reset it all


Params:

- **headers** - _Type: Dict_ - _Positional Argument_
    - Headers to be set. All headers will be set for requests.
    - Only `User-Agent` and `Accept-Encoding` will be set for `phantomjs` at this time.
    - Only `User-Agent` will be set for `firefox` at this time.

----------

#### fn: **get_soup**
Returns data as a beautifulsoup object

Params:

- **raw_content** - _Type: String_ - _Positional Argument_
    - Raw data to be converted into a beautifulsoup object
- **input_type** - _Type: String_ -  _Named Argument_ - _Default:_ `html`
    - Must be either `html` | `xml`. If not the function returns `None`

----------

#### fn: **hover**
Only works if `driver_type` is set to `selenium*`.
Will hover the cursor over an element using injected javascript

Params:

- **element** - _Type: Selenium element_ - _Positional Argument_
    - Element found using `self.driver.selenium.find.....()`

----------

#### fn: **screenshot**
Takes a full page screenshot of a webpage . Can be used with either `driver_type`.

Returns the location on disk that the file was saved to.

Params:

- **filename** - _Type: String_ - _Positional Argument_
    - The path for the file name to be saved to.
- **element** - _Type: Object_ -  _Named Argument_ - _Default:_ `None`
    - selenium object of an element
    - If `None` file the whole screenshot will be saved/returned
- **delay**  - _Type: Numeric_ -  _Named Argument_ - _Default:_ `0`
    - Time to delay befor taking the screenshot
    - When usig chrome, this time is also the delay after every scroll before another screenshot is taken

----------

#### fn: **get_selenium_header**
Only works if `driver_type` is set to `selenium*`.
Use after a `get_site` call to see what headers the server returned.
The `get_site` function uses this to make sure the page loaded with out a server error.
Returns a dictionary of header values as well as the keys:

- `status-code` - The number value HTTP status code
- `status-text` - The text value of the HTTP status code

Params: _N/A_

----------

#### fn: **get_site**
Can be used with any `driver_type`.
This should always be used to request a site. This function will check the http status code and auto handle errors it comes across.

Returns the data as a beautifulsoup object, a dictionary, or the raw page source.

Params:

- **url_raw** - _Type: String_ - _Positional Argument_
    - url that is being requested
- **cookies** - _Type: Dict_ -  _Named Argument_ - _Default:_ `{}`
    - Cookies to send with the request
    - TODO: Get working with `selenium`
- **page_format** - _Type: String_ -  _Named Argument_ - _Default:_ `html`
    - What the page format the site should be returning, options listed below
    - `html` & `xml`
        - Returns a beautifulsoup object
    - `json`
        - Returns a dictionary
    - `raw`
        - Requests: Returns the raw content of the page as a string
        - Selenium: Returns a boolean `True` to let you know the page loaded successfully
- **return_on_error** - _Type: List_ -  _Named Argument_ - _Default:_ `[]`
    - A list of ints of http status codes. Will raise an error to the client if a status code listed here is caught
    - **Caution:** This will disable any action that `get_site` would take for that status code
- **retry_enabled** - _Type: Boolean_ -  _Named Argument_ - _Default:_ `True`
    - If `False`, then do not try that url again and do not get a new_profile if the url failed
- **force_requests** - _Type: Boolean_ -  _Named Argument_ - _Default:_ `False`
    - If `True` the url will be processed by requests no matter what driver is being used
- **headers** - _Type: Dict_ -  _Named Argument_ - _Default:_ `{}`
    - Additonal headers that will only be apart of this call
    - TODO: Get working with `selenium`
- **api** - _Type: Boolean_ -  _Named Argument_ - _Default:_ `False`
    - Set to `True` and `get_site` will correctly append the current apikey to the url
- **track_stat** - _Type: Boolean_ -  _Named Argument_ - _Default:_ `True`
    - By default this will track page load times internally.
    - Access by `scraper.stats` at the end of the script to see the final stats
- **timout** - _Type: Int_ -  _Named Argument_ - _Default:_ `30`
    - How long to wait for the page to load before giving up
- **num_tries** - _Type: Int_ -  _Named Argument_ - _Default:_ `0`
    - Used internally in this function. Do not pass in.
    - Track the number of times the function tried to get the site
- **num_apikey_tries** - _Type: Int_ -  _Named Argument_ - _Default:_ `0`
    - Used internally in this function. Do not pass in.
    - TODO: Currently not working, need to figure this out

----------
