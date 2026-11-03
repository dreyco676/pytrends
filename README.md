# pytrends

## Introduction

Unofficial API for Google Trends

Allows simple interface for automating downloading of reports from Google Trends. 
Only good until Google changes their backend again :-P. When that happens feel free to contribute!

**Looking for maintainers!** Please open an issue with a method of contacting you if you're interested.


## Table of Contents

* [Installation](#installation)

* [API](#api)

  * [API Methods](#api-methods)

  * [Common API Parameters](#common-api-parameters)

    * [Interest Over Time](#interest-over-time)
    * [Multirange Interest Over Time](#multirange-interest-over-time)
    * [Interest by Region](#interest-by-region)
    * [Related Topics](#related-topics)
    * [Related Queries](#related-queries)
    * [Trending Searches](#trending-searches)
    * [Realtime Search Trends](#realtime-search-trends)
    * [Suggestions](#suggestions)

  * [Caveats](#caveats)

* [Credits](#credits)

## Installation

Once 5.0.0 is released:

```bash
pip install pytrends
```

Until then, install from source:

```bash
pip install git+https://github.com/dreyco676/pytrends.git
```

## Requirements

* Python 3.12 or later (tested on 3.12 to 3.15)
* Requires requests, pandas and urllib3, which pip installs for you

<sub><sup>[back to top](#pytrends)</sub></sup>

## API

### Connect to Google

```python
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360)
```

or if you want to use proxies as you are blocked due to Google rate limit:


```python
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360, timeout=(10,25), proxies=['https://34.203.233.13:80',], retries=2, backoff_factor=0.1, requests_args={'verify':False})
```

* `timeout(connect, read)`
  - See explantation on this on [requests docs](https://requests.readthedocs.io/en/master/user/advanced/#timeouts)
* tz
  - Timezone Offset
  - For example US CST is ```'360'``` (note **NOT** -360, Google uses timezone this way...)

* `proxies`

  - https proxies Google passed ONLY
  - list ```['https://34.203.233.13:80','https://35.201.123.31:880', ..., ...]```
  
* `retries`

  - number of retries total/connect/read all represented by one scalar

* `backoff_factor`

  - A backoff factor to apply between attempts after the second try (most errors are resolved immediately by a second try without a delay). urllib3 will sleep for: ```{backoff factor} * (2 ^ ({number of total retries} - 1))``` seconds. If the backoff_factor is 0.1, then sleep() will sleep for [0.0s, 0.2s, 0.4s, …] between retries. It will never be longer than Retry.BACKOFF_MAX. By default, backoff is disabled (set to 0).

* `requests_args`
  - A dict with additional parameters to pass along to the underlying requests library, for example verify=False to ignore SSL errors

* SOCKS proxies
  - Install the extra with `pip install pytrends[socks]`, then pass `socks5://` proxy URLs.

Note: the parameter `hl` specifies host language for accessing Google Trends. 
Note: only https proxies will work, and you need to add the port number after the proxy ip address

### Build Payload
```python
kw_list = ["Blockchain"]
pytrends.build_payload(kw_list, cat=0, timeframe='today 5-y', geo='', gprop='')
```

Parameters

* `kw_list`

  - *Required*
  - Keywords to get data for


<sub><sup>[back to top](#API)</sub></sup>

## API Methods

The following API methods are available:

* [Interest Over Time](#interest-over-time): returns historical, indexed data for when the keyword was searched most as shown on Google Trends' Interest Over Time section.

* [Multirange Interest Over Time](#multirange_interest_over_time): returns historical, indexed data similar to interest over time, but across multiple time date ranges. 

* [Interest by Region](#interest-by-region): returns data for where the keyword is most searched as shown on Google Trends' Interest by Region section.

* [Related Topics](#related-topics): returns data for the related keywords to a provided keyword shown on Google Trends' Related Topics section.

* [Related Queries](#related-queries): returns data for the related keywords to a provided keyword shown on Google Trends' Related Queries section.

* [Trending Searches](#trending-searches): returns data for latest trending searches shown on Google Trends' Trending Searches section.

* [Suggestions](#suggestions): returns a list of additional suggested keywords that can be used to refine a trend search.

<sub><sup>[back to top](#api-methods)</sub></sup>

## Common API parameters

Many API methods use the following:

* `kw_list`

  - keywords to get data for
  - Example ```['Pizza']```
  - Up to five terms in a list: ```['Pizza', 'Italian', 'Spaghetti', 'Breadsticks', 'Sausage']```

    * Advanced Keywords

      - When using Google Trends dashboard Google may provide suggested narrowed search terms.
      - For example ```"iron"``` will have a drop down of ```"Iron Chemical Element, Iron Cross, Iron Man, etc"```.
      - Find the encoded topic by using the get_suggestions() function and choose the most relevant one for you.
      - For example: ```https://www.google.com/trends/explore#q=%2Fm%2F025rw19&cmpt=q```
      - ```"/m/025rw19"``` is the topic "Iron Chemical Element" to use this with pytrends
      - You can also use `pytrends.suggestions()` to automate this.

* `cat`

  - Category to narrow results
  - Find available categories by inspecting the url when manually using Google Trends. The category starts after ```cat=``` and ends before the next ```&``` or view this [wiki page containing all available categories](https://github.com/pat310/google-trends-api/wiki/Google-Trends-Categories)
  - For example: ```"https://www.google.com/trends/explore#q=pizza&cat=71"```
  - ```'71'``` is the category
  - Defaults to no category

* `geo`

  - Two letter country abbreviation
  - For example United States is ```'US'```
  - Defaults to World
  - More detail available for States/Provinces by specifying additional abbreviations
  - For example: Alabama would be ```'US-AL'```
  - For example: England would be ```'GB-ENG'```
  - Can also be a list of up to five regions

* `tz`

  - Timezone Offset (in minutes)
  - For more information of Timezone Offset, [view this wiki page containing about UCT offset](https://en.wikipedia.org/wiki/UTC_offset)
  - For example US CST is ```'360'``` 

* `timeframe`

  - Date to start from
  - Defaults to last 5yrs, `'today 5-y'`.
  - Everything `'all'`
  - Specific dates, 'YYYY-MM-DD YYYY-MM-DD' example `'2016-12-14 2017-01-25'`
  - Specific datetimes, 'YYYY-MM-DDTHH YYYY-MM-DDTHH' example `'2017-02-06T10 2017-02-12T07'`
      - Note Time component is based off UTC

  - Current Time Minus Time Pattern:

    - By Month: ```'today #-m'``` where # is the number of months from that date to pull data for
      - For example: ``'today 3-m'`` would get data from today to 3months ago
      - **NOTE** Google uses UTC date as *'today'*
      - **Works for 1, 3, 12 months only!**

    - Daily: ```'now #-d'``` where # is the number of days from that date to pull data for
      - For example: ``'now 7-d'`` would get data from the last week
      - **Works for 1, 7 days only!**

    - Hourly: ```'now #-H'``` where # is the number of hours from that date to pull data for
      - For example: ``'now 1-H'`` would get data from the last hour
      - **Works for 1, 4 hours only!**

* `gprop`

  - What Google property to filter to
  - Example ```'images'```
  - Defaults to web searches
  - Can be ```images```, ```news```, ```youtube``` or ```froogle``` (for Google Shopping results)


<sub><sup>[back to top](#api-payload-keys)</sub></sup>

### Interest Over Time

```python
pytrends.interest_over_time()
```

Returns pandas.Dataframe. Google shows values below 1 as `<1`; pytrends stores them as `0`.

<sub><sup>[back to top](#interest_over_time)</sub></sup>

### Multirange Interest Over Time

```python
pytrends.build_payload(kw_list=['pizza', 'bagel'], timeframe=['2022-09-04 2022-09-10', '2022-09-18 2022-09-24'])
pytrends.multirange_interest_over_time()
```

Returns pandas.Dataframe. It includes the average in the first row.

<sub><sup>[back to top](#multirange_interest_over_time)</sub></sup>

### Interest by Region

```python
pytrends.interest_by_region(resolution='COUNTRY', inc_low_vol=True, inc_geo_code=False)
```

Parameters

* `resolution`

  - 'CITY' returns city level data
  - 'COUNTRY' returns country level data
  - 'DMA'  returns Metro level data
  - 'REGION'  returns Region level data

* `inc_low_vol`

  - True/False (includes google trends data for low volume countries/regions as well)

* `inc_geo_code`
  
  - True/False (includes ISO codes of countries along with the names in the data)

Returns pandas.DataFrame

<sub><sup>[back to top](#interest_by_region)</sub></sup>

### Related Topics

```python
pytrends.related_topics()
```

Returns dictionary of pandas.DataFrames

<sub><sup>[back to top](#related_topics)</sub></sup>

### Related Queries

```python
pytrends.related_queries()
```

Returns dictionary of pandas.DataFrames

Each DataFrame has the columns `query`, `value`, `formattedValue` (Google's label, such as `'Breakout'` or `'+250%'`) and `link`. `formattedValue` and `link` are empty when Google doesn't send them.

<sub><sup>[back to top](#related_queries)</sub></sup>

### Trending Searches

```python
pytrends.trending_searches(pn='US') # today's trending searches for the United States
pytrends.trending_searches(pn='IN') # India
```

Parameters

* `pn`

  - Two-letter country code, for example `'US'` or `'IN'`
  - Defaults to `'US'`
  - Legacy names such as `'united_states'` raise a `ValueError`

Returns pandas.Series of the trending search titles

<sub><sup>[back to top](#trending-searches)</sub></sup>

### Realtime Search Trends

```python
pytrends.realtime_trending_searches(pn='US') # realtime search trends for United States
pytrends.realtime_trending_searches(pn='IN') # India
```

Parameters

* `pn`

  - Two-letter country code, as for Trending Searches

Returns pandas.DataFrame with the columns:

* `title`
* `approx_traffic`, for example `'500+'`
* `pub_date`
* `articles`, a list of dicts with `title`, `url` and `source` for each news story

<sub><sup>[back to top](#realtime-search-trends)</sub></sup>

### Suggestions

```python
pytrends.suggestions(keyword)
```

Parameters

* `keyword`

  - *Required*
  - keyword to get suggestions for

Returns dictionary

<sub><sup>[back to top](#suggestions)</sub></sup>

### Explore Link

```python
pytrends.build_payload(['pizza', 'bagel'], timeframe='today 12-m', geo='US')
pytrends.get_explore_url()  # https://trends.google.com/trends/explore?date=today+12-m&q=pizza%2Cbagel&geo=US
```

Returns the trends.google.com explore link for the payload set up by the last `build_payload()`, so you can open the same chart in a browser. It requires `build_payload()` first, and it needs a single timeframe for all keywords and regions.

<sub><sup>[back to top](#explore-link)</sub></sup>

### Categories

```python
pytrends.categories()
```

Returns dictionary

<sub><sup>[back to top](#suggestions)</sub></sup>

# Removed endpoints

Google removed the endpoints behind some methods, and they now return HTTP 404:

* `trending_searches`, `today_searches` and `realtime_trending_searches` now read Google's Trending Now RSS feed. The feed lists only today's trending searches for one country, so the `pn` argument takes two-letter country codes only.
* `top_charts` was removed because there is no replacement.

<sub><sup>[back to top](#api-methods)</sub></sup>

# Caveats

* This is not an official or supported API
* Google may change aggregation level for items with very large or very small search volume
* Rate Limit is not publicly known, let me know if you have a consistent estimate
  * One user reports that 1,400 sequential requests of a 4 hours timeframe got them to the limit. (Replicated on 2 networks)
  * It has been tested, and 60 seconds of sleep between requests (successful or not) appears to be the correct amount once you reach the limit.
  * In our own testing, a run of about eight live requests in quick succession was answered with HTTP 429 (`TooManyRequestsError`). Pause between calls, or use `retries`, `backoff_factor` or `proxies`.
* For certain configurations the dependency lib certifi requires the environment variable REQUESTS_CA_BUNDLE to be explicitly set and exported. This variable must contain the path where the ca-certificates are saved or a SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] error is given at runtime. 

# Contributing

See the [CONTRIBUTING](CONTRIBUTING.md) file.

# Credits

* Major JSON revision ideas taken from pat310's JavaScript library

  - https://github.com/pat310/google-trends-api

* Connecting to google code heavily based off Stack Overflow post

  - http://stackoverflow.com/questions/6754709/logging-in-to-google-using-python

* With some ideas pulled from Matt Reid's Google Trends API

  - https://bitbucket.org/mattreid9956/google-trend-api/overview
