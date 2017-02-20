# Scraper Library

[![PyPI](https://img.shields.io/pypi/v/scraper_lib.svg)](https://pypi.python.org/pypi/scraper_lib)
[![PyPI](https://img.shields.io/pypi/l/scraper_lib.svg)](https://pypi.python.org/pypi/scraper_lib)

Developed using Python 3.5 (use at least 3.4.2+)

**TODO: Update functions in Readme **

## Install
- Use pip `pip3 install scraper_lib`

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

TODO...

