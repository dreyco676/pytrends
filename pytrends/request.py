from itertools import product
import json
import logging
import re
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests import status_codes

from pytrends import exceptions

from urllib.parse import quote


BASE_TRENDS_URL = 'https://trends.google.com/trends'
# Google prefixes JSON responses with ')]}' and sometimes a comma, then a newline
logger = logging.getLogger('pytrends')
XSSI_PREFIX = re.compile(r"^\)\]\}',?\n?")
TRENDING_RSS_URL = 'https://trends.google.com/trending/rss'
HT_NAMESPACE = '{https://trends.google.com/trending/rss}'


def parse_trending_rss(content: bytes) -> pd.DataFrame:
    """Parse the Trending Now RSS feed into one row per trending search."""
    items = ET.fromstring(content).findall('./channel/item')
    return pd.DataFrame(
        [
            {
                'title': item.findtext('title'),
                'approx_traffic': item.findtext(f'{HT_NAMESPACE}approx_traffic'),
                'pub_date': item.findtext('pubDate'),
                'articles': [
                    {
                        'title': news.findtext(f'{HT_NAMESPACE}news_item_title'),
                        'url': news.findtext(f'{HT_NAMESPACE}news_item_url'),
                        'source': news.findtext(f'{HT_NAMESPACE}news_item_source'),
                    }
                    for news in item.findall(f'{HT_NAMESPACE}news_item')
                ],
            }
            for item in items
        ],
        columns=['title', 'approx_traffic', 'pub_date', 'articles'],
    )


def _parse_ranked_list(req_json, index, make_frame):
    """Return the ranked list at index as a dataframe, or None when Google sent no such list"""
    try:
        return make_frame(req_json['default']['rankedList'][index]['rankedKeyword'])
    except (KeyError, IndexError):
        return None


def _topic_frame(ranked_keywords):
    return pd.json_normalize(ranked_keywords, sep='_')


def _query_frame(ranked_keywords):
    return pd.DataFrame(ranked_keywords)[['query', 'value']]


class TrendReq(object):
    """
    Google Trends API
    """
    GET_METHOD = 'get'
    POST_METHOD = 'post'
    GENERAL_URL = f'{BASE_TRENDS_URL}/api/explore'
    INTEREST_OVER_TIME_URL = f'{BASE_TRENDS_URL}/api/widgetdata/multiline'
    MULTIRANGE_INTEREST_OVER_TIME_URL = f'{BASE_TRENDS_URL}/api/widgetdata/multirange'
    INTEREST_BY_REGION_URL = f'{BASE_TRENDS_URL}/api/widgetdata/comparedgeo'
    RELATED_QUERIES_URL = f'{BASE_TRENDS_URL}/api/widgetdata/relatedsearches'
    TRENDING_SEARCHES_URL = f'{BASE_TRENDS_URL}/hottrends/visualize/internal/data'
    SUGGESTIONS_URL = f'{BASE_TRENDS_URL}/api/autocomplete/'
    CATEGORIES_URL = f'{BASE_TRENDS_URL}/api/explore/pickers/category'
    TODAY_SEARCHES_URL = f'{BASE_TRENDS_URL}/api/dailytrends'
    REALTIME_TRENDING_SEARCHES_URL = f'{BASE_TRENDS_URL}/api/realtimetrends'
    ERROR_CODES = (500, 502, 504, 429)

    def __init__(self, hl='en-US', tz=360, geo='', timeout=(2, 5), proxies='',
                 retries=0, backoff_factor=0, requests_args=None):
        """
        Initialize default values for params
        """
        # google rate limit
        self.google_rl = 'You have reached your quota limit. Please try again later.'
        self.results = None
        # set user defined options used globally
        self.tz = tz
        self.hl = hl
        self.geo = geo
        # the constructor's geo is the default for build_payload calls that omit geo
        self.default_geo = geo
        self.kw_list = list()
        self.timeout = timeout
        self.proxies = proxies  # add a proxy option
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.proxy_index = 0
        # copy so that popping 'headers' below doesn't mutate the caller's dict
        self.requests_args = dict(requests_args or {})
        self.cookies = self.GetGoogleCookie()
        # intialize widget payloads
        self.token_payload = dict()
        self.interest_over_time_widget = dict()
        self.interest_by_region_widget = dict()
        self.related_topics_widget_list = list()
        self.related_queries_widget_list = list()

        self.headers = {'accept-language': self.hl}
        self.headers.update(self.requests_args.pop('headers', {}))

    @staticmethod
    def _nid_cookie(response):
        """Return the NID cookie from a cookie-URL response, raising on any non-2xx status"""
        if not 200 <= response.status_code < 300:
            raise exceptions.ResponseError.from_response(response)
        return dict(filter(lambda i: i[0] == 'NID', response.cookies.items()))

    def GetGoogleCookie(self):
        """
        Gets google cookie (used for each and every proxy; once on init otherwise)
        Removes proxy from the list on proxy error
        """
        while True:
            if "proxies" in self.requests_args:
                return self._nid_cookie(requests.get(
                    f'{BASE_TRENDS_URL}/?geo={self.hl[-2:]}',
                    timeout=self.timeout,
                    **self.requests_args
                ))
            else:
                if len(self.proxies) > 0:
                    proxy = {'https': self.proxies[self.proxy_index]}
                else:
                    proxy = ''
                try:
                    return self._nid_cookie(requests.get(
                        f'{BASE_TRENDS_URL}/?geo={self.hl[-2:]}',
                        timeout=self.timeout,
                        proxies=proxy,
                        **self.requests_args
                    ))
                except requests.exceptions.ProxyError:
                    logger.warning('Proxy error. Changing IP')
                    if len(self.proxies) > 1:
                        self.proxies.remove(self.proxies[self.proxy_index])
                        # the removed proxy may have been the last one in the list
                        if self.proxy_index >= len(self.proxies):
                            self.proxy_index = 0
                    else:
                        logger.warning('No more proxies available. Bye!')
                        raise
                    continue

    def GetNewProxy(self):
        """
        Increment proxy INDEX; zero on overflow
        """
        if self.proxy_index < (len(self.proxies) - 1):
            self.proxy_index += 1
        else:
            self.proxy_index = 0

    def _get_data(self, url, method=GET_METHOD, **kwargs):
        """Send a request to Google and return the JSON response as a Python object
        :param url: the url to which the request will be sent
        :param method: the HTTP method ('get' or 'post')
        :param kwargs: any extra key arguments passed to the request builder (usually query parameters or data)
        :return:
        """
        s = requests.session()
        # Retries mechanism. Activated when one of statements >0 (best used for proxy)
        if self.retries > 0 or self.backoff_factor > 0:
            retry = Retry(total=self.retries, read=self.retries,
                          connect=self.retries,
                          backoff_factor=self.backoff_factor,
                          status_forcelist=TrendReq.ERROR_CODES,
                          allowed_methods=frozenset(['GET', 'POST']))
            s.mount('https://', HTTPAdapter(max_retries=retry))

        s.headers.update(self.headers)
        if len(self.proxies) > 0:
            self.cookies = self.GetGoogleCookie()
            s.proxies.update({'https': self.proxies[self.proxy_index]})
        if method == TrendReq.POST_METHOD:
            response = s.post(url, timeout=self.timeout,
                              cookies=self.cookies, **kwargs,
                              **self.requests_args)  # DO NOT USE retries or backoff_factor here
        else:
            response = s.get(url, timeout=self.timeout, cookies=self.cookies,
                             **kwargs, **self.requests_args)  # DO NOT USE retries or backoff_factor here
        # check if the response contains json and throw an exception otherwise
        # Google mostly sends 'application/json' in the Content-Type header,
        # but occasionally it sends 'application/javascript
        # and sometimes even 'text/javascript
        if response.status_code == 200 and (
                'application/json' in response.headers['Content-Type'] or
                'application/javascript' in response.headers['Content-Type'] or
                'text/javascript' in response.headers['Content-Type']):
            # trim initial characters
            # some responses start with garbage characters, like ")]}',"
            # these have to be cleaned before being passed to the json parser
            content = XSSI_PREFIX.sub('', response.text)
            # parse json
            self.GetNewProxy()
            return json.loads(content)
        else:
            if response.status_code == status_codes.codes.too_many_requests:
                raise exceptions.TooManyRequestsError.from_response(response)
            raise exceptions.ResponseError.from_response(response)

    def build_payload(self, kw_list, cat=0, timeframe='today 5-y', geo=None,
                      gprop=''):
        """Create the payload for related queries, interest over time and interest by region"""
        if gprop not in ['', 'images', 'news', 'youtube', 'froogle']:
            raise ValueError('gprop must be empty (to indicate web), images, news, youtube, or froogle')
        self.kw_list = kw_list
        # geo='' means worldwide; only an omitted geo falls back to the constructor default
        self.geo = self.default_geo if geo is None else geo
        self.token_payload = {
            'hl': self.hl,
            'tz': self.tz,
            'req': {'comparisonItem': [], 'category': cat, 'property': gprop}
        }

        if not isinstance(self.geo, list):
            self.geo = [self.geo]

        # Check if timeframe is a list
        if isinstance(timeframe, list):
            comparisons = len(self.kw_list) * len(self.geo)
            if len(timeframe) != comparisons:
                raise ValueError(
                    f'timeframe list must have one entry per keyword and region: '
                    f'expected {comparisons}, got {len(timeframe)}')
            for index, (kw, geo) in enumerate(product(self.kw_list, self.geo)):
                keyword_payload = {'keyword': kw, 'time': timeframe[index], 'geo': geo}
                self.token_payload['req']['comparisonItem'].append(keyword_payload)
        else:
            # build out json for each keyword with
            for kw, geo in product(self.kw_list, self.geo):
                keyword_payload = {'keyword': kw, 'time': timeframe, 'geo': geo}
                self.token_payload['req']['comparisonItem'].append(keyword_payload)

        # requests will mangle this if it is not a string
        self.token_payload['req'] = json.dumps(self.token_payload['req'])
        # get tokens
        self._tokens()
        return

    def _tokens(self):
        """Makes request to Google to get API tokens for interest over time, interest by region and related queries"""
        # make the request and parse the returned json
        widget_dicts = self._get_data(
            url=TrendReq.GENERAL_URL,
            method=TrendReq.POST_METHOD,
            params=self.token_payload,
        )['widgets']
        # order of the json matters...
        first_region_token = True
        # clear self.related_queries_widget_list and self.related_topics_widget_list
        # of old keywords'widgets
        self.related_queries_widget_list[:] = []
        self.related_topics_widget_list[:] = []
        # assign requests
        for widget in widget_dicts:
            if widget['id'] == 'TIMESERIES':
                self.interest_over_time_widget = widget
            if widget['id'] == 'GEO_MAP' and first_region_token:
                self.interest_by_region_widget = widget
                first_region_token = False
            # response for each term, put into a list
            if 'RELATED_TOPICS' in widget['id']:
                self.related_topics_widget_list.append(widget)
            if 'RELATED_QUERIES' in widget['id']:
                self.related_queries_widget_list.append(widget)
        return

    def _widget_params(self, widget):
        """Build the query parameters the widget endpoints expect for one widget"""
        return {
            # convert to string as requests will mangle
            'req': json.dumps(widget['request']),
            'token': widget['token'],
            'tz': self.tz,
        }

    def interest_over_time(self):
        """Request data from Google's Interest Over Time section and return a dataframe"""

        over_time_payload = self._widget_params(self.interest_over_time_widget)

        # make the request and parse the returned json
        req_json = self._get_data(
            url=TrendReq.INTEREST_OVER_TIME_URL,
            method=TrendReq.GET_METHOD,
            params=over_time_payload,
        )

        df = pd.DataFrame(req_json['default']['timelineData'])
        if (df.empty):
            return df

        df['date'] = pd.to_datetime(df['time'].astype(dtype='float64'),
                                    unit='s')
        df = df.set_index(['date']).sort_index()
        # split list columns into seperate ones, remove brackets and split on comma
        result_df = df['value'].apply(lambda x: pd.Series(
            str(x).replace('[', '').replace(']', '').split(',')))
        # rename each column with its search term, relying on order that google provides...

        for idx, (kw, g) in enumerate(product(self.kw_list, self.geo)):
            # there is currently a bug with assigning columns that may be
            # parsed as a date in pandas: use explicit insert column method
            name = kw if len(self.geo) == 1 else (kw, g)
            result_df.insert(len(result_df.columns), name,
                             result_df[idx].astype('int'))
            del result_df[idx]

        if 'isPartial' in df:
            # make other dataframe from isPartial key data
            # split list columns into seperate ones, remove brackets and split on comma
            # a missing isPartial counts as False; mapping avoids fillna's downcasting warning on pandas 2.2
            df['isPartial'] = df['isPartial'].map(lambda x: pd.notna(x) and bool(x))
            result_df2 = df['isPartial'].apply(lambda x: pd.Series(
                str(x).replace('[', '').replace(']', '').split(',')))
            result_df2.columns = ['isPartial']
            # Change to a bool type.
            result_df2.isPartial = result_df2.isPartial == 'True'
            # concatenate the two dataframes
            final = pd.concat([result_df, result_df2], axis=1)
        else:
            final = result_df
            final['isPartial'] = False

        if len(self.geo) > 1:
            final.columns = pd.MultiIndex.from_tuples(
                [c if isinstance(c, tuple) else (c, ) for c in final],
                names=['keyword', 'region']
            )
        else:
            # rebuild the labels the normal way so their dtype matches pandas' own default (str on pandas 3)
            final.columns = pd.Index(list(final.columns))
        return final

    def multirange_interest_over_time(self):
        """Request data from Google's Interest Over Time section across different time ranges and return a dataframe"""

        over_time_payload = self._widget_params(self.interest_over_time_widget)

        # make the request and parse the returned json
        req_json = self._get_data(
            url=TrendReq.MULTIRANGE_INTEREST_OVER_TIME_URL,
            method=TrendReq.GET_METHOD,
            params=over_time_payload,
        )

        df = pd.DataFrame(req_json['default']['timelineData'])
        if (df.empty):
            return df

        # one column per keyword, each cell holding that keyword's dict (json_normalize rejects a Series of lists on pandas 3)
        result_df = pd.DataFrame(df['columnData'].tolist())

        # Split dictionary columns into seperate ones
        for i, column in enumerate(result_df.columns):
            result_df["[" + str(i) + "] " + str(self.kw_list[i]) + " date"] = result_df[i].apply(pd.Series)["formattedTime"]
            result_df["[" + str(i) + "] " + str(self.kw_list[i]) + " value"] = result_df[i].apply(pd.Series)["value"]
            result_df = result_df.drop([i], axis=1)

        # Adds a row with the averages at the top of the dataframe
        avg_row = {}
        for i, avg in enumerate(req_json['default']['averages']):
            avg_row["[" + str(i) + "] " + str(self.kw_list[i]) + " date"] = "Average"
            avg_row["[" + str(i) + "] " + str(self.kw_list[i]) + " value"] = req_json['default']['averages'][i]

        result_df.loc[-1] = avg_row
        result_df.index = result_df.index + 1
        result_df = result_df.sort_index()
        # rebuild the labels the normal way so their dtype matches pandas' own default (str on pandas 3)
        result_df.columns = pd.Index(list(result_df.columns))

        return result_df

    def interest_by_region(self, resolution='COUNTRY', inc_low_vol=False,
                           inc_geo_code=False):
        """Request data from Google's Interest by Region section and return a dataframe"""

        # make the request
        # self.geo is always a list after build_payload, e.g. [''] for worldwide
        if self.geo == ['']:
            self.interest_by_region_widget['request'][
                'resolution'] = resolution
        elif self.geo == ['US'] and resolution in ['DMA', 'CITY', 'REGION']:
            self.interest_by_region_widget['request'][
                'resolution'] = resolution

        self.interest_by_region_widget['request'][
            'includeLowSearchVolumeGeos'] = inc_low_vol

        region_payload = self._widget_params(self.interest_by_region_widget)

        # parse returned json
        req_json = self._get_data(
            url=TrendReq.INTEREST_BY_REGION_URL,
            method=TrendReq.GET_METHOD,
            params=region_payload,
        )
        df = pd.DataFrame(req_json['default']['geoMapData'])
        if (df.empty):
            return df

        # rename the column with the search keyword
        geo_column = 'geoCode' if 'geoCode' in df.columns else 'coordinates'
        columns = ['geoName', geo_column, 'value']
        df = df[columns].set_index(['geoName']).sort_index()
        # split list columns into separate ones, remove brackets and split on comma
        result_df = df['value'].apply(lambda x: pd.Series(
            str(x).replace('[', '').replace(']', '').split(',')))
        if inc_geo_code:
            result_df[geo_column] = df[geo_column]

        # rename each column with its search term
        for idx, kw in enumerate(self.kw_list):
            result_df[kw] = result_df[idx].astype('int')
            del result_df[idx]

        # rebuild the labels the normal way so their dtype matches pandas' own default (str on pandas 3)
        result_df.columns = pd.Index(list(result_df.columns))
        return result_df

    def related_topics(self):
        """Request data from Google's Related Topics section and return a dictionary of dataframes

        If no top and/or rising related topics are found, the value for the key "top" and/or "rising" will be None
        """

        # make the request
        result_dict = dict()
        for request_json in self.related_topics_widget_list:
            # ensure we know which keyword we are looking at rather than relying on order
            try:
                kw = request_json['keywordName']
            except KeyError:
                kw = ''
            related_payload = self._widget_params(request_json)

            # parse the returned json
            req_json = self._get_data(
                url=TrendReq.RELATED_QUERIES_URL,
                method=TrendReq.GET_METHOD,
                params=related_payload,
            )

            df_top = _parse_ranked_list(req_json, 0, _topic_frame)
            df_rising = _parse_ranked_list(req_json, 1, _topic_frame)

            result_dict[kw] = {'rising': df_rising, 'top': df_top}
        return result_dict

    def related_queries(self):
        """Request data from Google's Related Queries section and return a dictionary of dataframes

        If no top and/or rising related queries are found, the value for the key "top" and/or "rising" will be None
        """

        # make the request
        result_dict = dict()
        for request_json in self.related_queries_widget_list:
            # ensure we know which keyword we are looking at rather than relying on order
            try:
                kw = request_json['keywordName']
            except KeyError:
                kw = ''
            related_payload = self._widget_params(request_json)

            # parse the returned json
            req_json = self._get_data(
                url=TrendReq.RELATED_QUERIES_URL,
                method=TrendReq.GET_METHOD,
                params=related_payload,
            )

            top_df = _parse_ranked_list(req_json, 0, _query_frame)
            rising_df = _parse_ranked_list(req_json, 1, _query_frame)

            result_dict[kw] = {'top': top_df, 'rising': rising_df}
        return result_dict

    def _trending_feed(self, pn):
        """Fetch Google's Trending Now feed for a country code and parse it into a dataframe"""
        if len(pn) != 2 or not pn.isalpha():
            raise ValueError(f"pn must be a two-letter country code such as 'US', got {pn!r}")
        response = requests.get(TRENDING_RSS_URL, params={'geo': pn}, headers=self.headers,
                                timeout=self.timeout, **self.requests_args)
        return parse_trending_rss(response.content)

    def trending_searches(self, pn='US'):
        """Request Google's Trending Now feed for a country code and return the trending search titles"""
        return self._trending_feed(pn)['title']

    def today_searches(self, pn='US'):
        """Request Google's Trending Now feed for a country code and return the trending search titles"""
        return self._trending_feed(pn)['title']

    def realtime_trending_searches(self, pn='US', cat='all', count=300):
        """Request Google's Trending Now feed for a country code and return one row per trending search.

        cat and count are ignored: the RSS feed has no equivalent parameters.
        """
        return self._trending_feed(pn)

    def suggestions(self, keyword):
        """Request data from Google's Keyword Suggestion dropdown and return a dictionary"""

        # make the request
        kw_param = quote(keyword)
        parameters = {'hl': self.hl}

        req_json = self._get_data(
            url=TrendReq.SUGGESTIONS_URL + kw_param,
            params=parameters,
            method=TrendReq.GET_METHOD
        )['default']['topics']
        return req_json

    def categories(self):
        """Request available categories data from Google's API and return a dictionary"""

        params = {'hl': self.hl}

        req_json = self._get_data(
            url=TrendReq.CATEGORIES_URL,
            params=params,
            method=TrendReq.GET_METHOD
        )
        return req_json

    def get_historical_interest(self, *args, **kwargs):
        raise NotImplementedError(
            "This method has been removed for incorrectness. It will be removed completely in v5.\n"
            "If you'd like similar functionality, please try implementing it yourself and "
            "consider submitting a pull request to add it to pytrends.\n"
            "\n"
            "There is discussion at:\n"
            "https://github.com/GeneralMills/pytrends/pull/542"
        )
