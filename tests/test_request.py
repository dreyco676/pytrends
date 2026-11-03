from dataclasses import dataclass
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch
import json
import logging
import re
import warnings

import pandas as pd
import numpy as np
import pytest
import requests
import responses
from pandas.testing import assert_frame_equal

from pytrends import dailydata
from pytrends.exceptions import ResponseError, TooManyRequestsError
from pytrends.request import TrendReq, BASE_TRENDS_URL, TRENDING_RSS_URL, parse_trending_rss


@dataclass
class ExpectedResult:
    """
    Small class to reduce boilerplate code in the tests that compares a `pd.DataFrame`.
    Instead of compare against a whole `pd.DataFrame` compares it with a given length, head
    and tail.
    The length of head and tail is 3 by default but you can change it.
    """
    length: int
    df_head: pd.DataFrame
    df_tail: pd.DataFrame
    head_tail_length: int = 3

    def assert_equals(self, df_result: pd.DataFrame):
        assert len(df_result) == self.length
        assert_frame_equal(df_result.head(self.head_tail_length), self.df_head)
        assert_frame_equal(df_result.tail(self.head_tail_length), self.df_tail)


def build_interest_over_time_df(records, dates):
    """
    Creates a `pd.DataFrame` with the same shape as a pytrends `interest_over_time` result.
    `records` is a dict of keyword -> results.
    If `records` doesn't include the key 'isPartial' then `[False]` will be used.
    Example:

        In [6]: build_interest_over_time_df(
           ...:     {'kw1': [1, 2, 3], 'kw2': [10, 20, 30]},
           ...:     dates=['2021-01-01', '2021-01-02', '2021-01-03']
           ...: )
        Out[6]:
                    kw1  kw2  isPartial
        date
        2021-01-01    1   10      False
        2021-01-02    2   20      False
        2021-01-03    3   30      False
    """
    records = records.copy()
    if 'isPartial' not in records:
        records['isPartial'] = [False]
    return pd.DataFrame(
        records,
        index=pd.Index(
            data=pd.to_datetime(dates),
            name='date'
        )
    )


def test_initial_data(mocked_responses):
    """Should use same values as in the documentation."""
    # NID cookie without an expiry, so the test doesn't depend on the clock.
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    pytrend = TrendReq()
    result = {
        "hl": pytrend.hl,
        "tz": pytrend.tz,
        "geo": pytrend.geo,
        "cookie_NID": bool(pytrend.cookies["NID"]),
    }
    expected = {"hl": "en-US", "tz": 360, "geo": "", "cookie_NID": True}
    assert result == expected


@pytest.mark.vcr
def test_build_payload():
    """Should return the widgets to get data."""
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=["pizza", "bagel"])
    expected = {
        "hl": "en-US",
        "tz": 360,
        "req": (
            '{"comparisonItem": ['
            '{"keyword": "pizza", "time": "today 5-y", "geo": ""}, '
            '{"keyword": "bagel", "time": "today 5-y", "geo": ""}'
            '], "category": 0, "property": ""}'
        ),
    }
    assert pytrend.token_payload == expected


@pytest.mark.vcr
def test_tokens():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=["pizza", "bagel"], timeframe='2021-01-01 2021-12-31')
    expected = [
        {
            "request": {
                "restriction": {
                    "geo": {},
                    "time": "2021-01-01 2021-12-31",
                    "originalTimeRangeForExploreUrl": "2021-01-01 2021-12-31",
                    "complexKeywordsRestriction": {
                        "keyword": [{"type": "BROAD", "value": "pizza"}]
                    },
                },
                "keywordType": "QUERY",
                "metric": ["TOP", "RISING"],
                "trendinessSettings": {"compareTime": "2020-01-02 2020-12-31"},
                "requestOptions": {"property": "", "backend": "IZG", "category": 0},
                "language": "en",
                "userCountryCode": "ES",
                "userConfig": {"userType": "USER_TYPE_SCRAPER"},
            },
            # We don't care if the help dialog changes.
            "helpDialog": ANY,
            "color": "PALETTE_COLOR_1",
            "keywordName": "pizza",
            # The token will change in every request.
            "token": ANY,
            "id": "RELATED_QUERIES_0",
            "type": "fe_related_searches",
            "title": "Related queries",
            "template": "fe",
            "embedTemplate": "fe_embed",
            "version": "1",
            "isLong": False,
            "isCurated": False,
        },
        {
            "request": {
                "restriction": {
                    "geo": {},
                    "time": "2021-01-01 2021-12-31",
                    "originalTimeRangeForExploreUrl": "2021-01-01 2021-12-31",
                    "complexKeywordsRestriction": {
                        "keyword": [{"type": "BROAD", "value": "bagel"}]
                    },
                },
                "keywordType": "QUERY",
                "metric": ["TOP", "RISING"],
                "trendinessSettings": {"compareTime": "2020-01-02 2020-12-31"},
                "requestOptions": {"property": "", "backend": "IZG", "category": 0},
                "language": "en",
                "userCountryCode": "ES",
                "userConfig": {"userType": "USER_TYPE_SCRAPER"},
            },
            # We don't care if the help dialog changes.
            "helpDialog": ANY,
            "color": "PALETTE_COLOR_2",
            "keywordName": "bagel",
            # The token will change in every request.
            "token": ANY,
            "id": "RELATED_QUERIES_1",
            "type": "fe_related_searches",
            "title": "Related queries",
            "template": "fe",
            "embedTemplate": "fe_embed",
            "version": "1",
            "isLong": False,
            "isCurated": False,
        },
    ]
    assert pytrend.related_queries_widget_list == expected


@pytest.mark.vcr
def test_interest_over_time_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    df_expected = build_interest_over_time_df({
        'pizza': [100, 83, 78, 49, 50],
        'bagel': [2, 2, 2, 1, 1]
    }, dates=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'])
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_interest_over_time_images():
    pytrend = TrendReq()
    pytrend.build_payload(
        kw_list=['pizza', 'bagel'],
        gprop='images',
        timeframe='2021-01-01 2021-01-05'
    )
    df_result = pytrend.interest_over_time()
    df_expected = build_interest_over_time_df({
        'pizza': [85, 100, 93, 93, 93],
        'bagel': [3, 2, 9, 4, 4]
    }, dates=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'])
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_interest_over_time_news():
    pytrend = TrendReq()
    pytrend.build_payload(
        kw_list=['pizza', 'bagel'],
        gprop='news',
        timeframe='2021-01-01 2021-01-05'
    )
    df_result = pytrend.interest_over_time()
    df_expected = build_interest_over_time_df({
        'pizza': [100, 67, 78, 32, 75],
        'bagel': [0, 0, 0, 20, 0]
    }, dates=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'])
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_interest_over_time_youtube():
    pytrend = TrendReq()
    pytrend.build_payload(
        kw_list=['pizza', 'bagel'],
        gprop='youtube',
        timeframe='2021-01-01 2021-01-05'
    )
    df_result = pytrend.interest_over_time()
    df_expected = build_interest_over_time_df({
        'pizza': [88, 100, 100, 92, 95],
        'bagel': [1, 1, 1, 2, 1]
    }, dates=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'])
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_interest_over_time_froogle():
    pytrend = TrendReq()
    pytrend.build_payload(
        kw_list=['pizza', 'bagel'],
        gprop='froogle',
        timeframe='2021-01-01 2021-01-05'
    )
    df_result = pytrend.interest_over_time()
    df_expected = build_interest_over_time_df({
        'pizza': [94, 99, 94, 62, 100],
        'bagel': [0, 0, 0, 0, 8]
    }, dates=['2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05'])
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_interest_over_time_bad_gprop():
    pytrend = TrendReq()
    expected_message = re.compile(r'^gprop must be.+$')
    with pytest.raises(ValueError, match=expected_message):
        pytrend.build_payload(kw_list=['pizza', 'bagel'], gprop=' ')


@pytest.mark.vcr
def test_multirange_interest_over_time_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe=['2021-01-01 2021-01-05', '2021-01-06 2021-01-10'])
    df_result = pytrend.multirange_interest_over_time()

    expected_result = ExpectedResult(
        length=6,
        df_head=pd.DataFrame({
            '[0] pizza date': ['Average', 'Jan 1, 2021', 'Jan 2, 2021'],
            '[0] pizza value': [72, 100, 83],
            '[1] bagel date': ['Average', 'Jan 6, 2021', 'Jan 7, 2021'],
            '[1] bagel value': [1, 1, 1]
        }),
        df_tail=pd.DataFrame({
            '[0] pizza date': ['Jan 3, 2021', 'Jan 4, 2021', 'Jan 5, 2021'],
            '[0] pizza value': [78, 49, 50],
            '[1] bagel date': ['Jan 8, 2021', 'Jan 9, 2021', 'Jan 10, 2021'],
            '[1] bagel value': [1, 2, 2]
        }, index=pd.Index([3, 4, 5]))
    )
    expected_result.assert_equals(df_result)


@pytest.mark.vcr
def test_multirange_interest_over_time_same_keyword_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'pizza'], timeframe=['2021-01-01 2021-01-05', '2021-01-06 2021-01-10'])
    df_result = pytrend.multirange_interest_over_time()

    expected_result = ExpectedResult(
        length=6,
        df_head=pd.DataFrame({
            '[0] pizza date': ['Average', 'Jan 1, 2021', 'Jan 2, 2021'],
            '[0] pizza value': [72, 100, 83],
            '[1] pizza date': ['Average', 'Jan 6, 2021', 'Jan 7, 2021'],
            '[1] pizza value': [68, 52, 52]
        }),
        df_tail=pd.DataFrame({
            '[0] pizza date': ['Jan 3, 2021', 'Jan 4, 2021', 'Jan 5, 2021'],
            '[0] pizza value': [78, 49, 50],
            '[1] pizza date': ['Jan 8, 2021', 'Jan 9, 2021', 'Jan 10, 2021'],
            '[1] pizza value': [70, 89, 74]
        }, index=pd.Index([3, 4, 5]))
    )
    expected_result.assert_equals(df_result)


@pytest.mark.vcr
def test_interest_by_region_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.interest_by_region()
    # Both head and tail have all 0's in both values, sort the result to test more meaningful values
    df_result = df_result.sort_values(by=['bagel', 'pizza', 'geoName'], ascending=False)
    expected_result = ExpectedResult(
        length=250,
        df_head=pd.DataFrame({
            'pizza': [92, 94, 96],
            'bagel': [8, 6, 4],
        }, index=pd.Index(['Singapore', 'Hong Kong', 'Taiwan'], name='geoName')),
        df_tail=pd.DataFrame({
            'pizza': [0, 0, 0],
            'bagel': [0, 0, 0],
        }, index=pd.Index(['Algeria', 'Albania', 'Afghanistan'], name='geoName'))
    )
    expected_result.assert_equals(df_result)


# FIXME: With more than one term the result is always an empty dict.
# In the web we can get related topics using ['Torvalds', 'Dijkstra'] but not here, something's wrong.
@pytest.mark.vcr
def test_related_topics_result_keys():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_topics()
    # Since the result dict contains pd.DataFrame's we can't create an expected dict and compare
    # because PAndas raises an error "the truth value of a DataFrame is ambiguous".
    assert set(df_result.keys()) == {'pizza'}
    df_result = df_result['pizza']
    assert set(df_result.keys()) == {'top', 'rising'}


@pytest.mark.vcr
def test_related_topics_result_top():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_topics()['pizza']['top']
    expected_result = ExpectedResult(
        length=21,
        df_head=pd.DataFrame({
            'value': [100, 23, 12],
            'formattedValue': ['100', '23', '12'],
            'hasData': [True, True, True],
            'link': [
                '/trends/explore?q=/m/0663v&date=2021-01-01+2021-12-31',
                '/trends/explore?q=/m/09cfq&date=2021-01-01+2021-12-31',
                '/trends/explore?q=/m/03clwm&date=2021-01-01+2021-12-31'
            ],
            'topic_mid': ['/m/0663v', '/m/09cfq', '/m/03clwm'],
            'topic_title': ['Pizza', 'Pizza Hut', "Domino's"],
            'topic_type': ['Dish', 'Restaurant chain', 'Restaurant chain'],
        }),
        df_tail=pd.DataFrame({
            'value': [0, 0, 0],
            'formattedValue': ['<1', '<1', '<1'],
            'hasData': [True, True, True],
            'link': [
                '/trends/explore?q=/g/11b7c9w1y6&date=2021-01-01+2021-12-31',
                '/trends/explore?q=/m/09nghg&date=2021-01-01+2021-12-31',
                '/trends/explore?q=/m/0gwh_4&date=2021-01-01+2021-12-31',
            ],
            'topic_mid': ['/g/11b7c9w1y6', '/m/09nghg', '/m/0gwh_4'],
            'topic_title': ["Roman's Pizza", 'Sam Goody', 'Detroit-style pizza'],
            'topic_type': ['Topic', 'Retail company', 'Food']
        }, index=pd.Index([18, 19, 20]))
    )
    expected_result.assert_equals(df_result)


@pytest.mark.vcr
def test_related_topics_result_rising():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_topics()['pizza']['rising']
    df_expected = pd.DataFrame({
        'value': [12600, 160, 80, 70],
        'formattedValue': ['Breakout', '+160%', '+80%', '+70%'],
        'link': [
            '/trends/explore?q=/m/09nghg&date=2021-01-01+2021-12-31',
            '/trends/explore?q=/m/0gwh_4&date=2021-01-01+2021-12-31',
            '/trends/explore?q=/g/11g6qhxwmd&date=2021-01-01+2021-12-31',
            '/trends/explore?q=/m/02hvyj&date=2021-01-01+2021-12-31',
        ],
        'topic_mid': ['/m/09nghg', '/m/0gwh_4', '/g/11g6qhxwmd', '/m/02hvyj'],
        'topic_title': ['Sam Goody', 'Detroit-style pizza', 'Ooni', 'Mystic Pizza'],
        'topic_type': ['Retail company', 'Food', 'Topic', '1988 film'],
    })
    assert_frame_equal(df_result, df_expected)


@pytest.mark.vcr
def test_related_queries_result_keys():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_queries()
    assert set(df_result.keys()) == {'pizza', 'bagel'}
    df_result_pizza = df_result['pizza']
    assert set(df_result_pizza.keys()) == {'top', 'rising'}
    df_result_bagel = df_result['bagel']
    assert set(df_result_bagel.keys()) == {'top', 'rising'}


@pytest.mark.vcr
def test_related_queries_result_top():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_queries()

    expected_pizza = ExpectedResult(
        length=25,
        df_head=pd.DataFrame({
            'query': ['pizza hut', 'pizza near me', 'pizza pizza near me'],
            'value': [100, 68, 65],
        }),
        df_tail=pd.DataFrame({
            'query': ['pizza little caesars', 'cheese pizza', 'new york pizza'],
            'value': [5, 5, 5],
        }, index=pd.Index([22, 23, 24]))
    )
    expected_pizza.assert_equals(df_result['pizza']['top'])

    expected_bagel = ExpectedResult(
        length=25,
        df_head=pd.DataFrame({
            'query': ['the bagel', 'bagel me', 'everything bagel'],
            'value': [100, 97, 92],
        }),
        df_tail=pd.DataFrame({
            'query': ['what a bagel', 'bagel sandwich', 'coffee meets bagel'],
            'value': [22, 22, 22],
        }, index=pd.Index([22, 23, 24]))
    )
    expected_bagel.assert_equals(df_result['bagel']['top'])


@pytest.mark.vcr
def test_related_queries_result_rising():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_queries()

    expected_pizza = ExpectedResult(
        length=11,
        df_head=pd.DataFrame({
            'query': ['licorice pizza', 'history of pizza', 'stoned pizza'],
            'value': [8550, 400, 300],
        }),
        df_tail=pd.DataFrame({
            'query': ['incredible pizza', 'mountain mike pizza', 'angels pizza'],
            'value': [60, 50, 40],
        }, index=pd.Index([8, 9, 10]))
    )
    expected_pizza.assert_equals(df_result['pizza']['rising'])

    expected_bagel = ExpectedResult(
        length=18,
        df_head=pd.DataFrame({
            'query': ['rover bagel', 'kettlemans bagel', 'bagel karen'],
            'value': [350, 250, 180],
        }),
        df_tail=pd.DataFrame({
            'query': ['bagel street deli', 'best bagel near me', 'the bagel nook'],
            'value': [50, 50, 40],
        }, index=pd.Index([15, 16, 17]))
    )
    expected_bagel.assert_equals(df_result['bagel']['rising'])


@pytest.mark.vcr
def test_suggestions_ok():
    pytrend = TrendReq()
    # suggestions doesn't need to call build_payload.
    result = pytrend.suggestions(keyword='pizza')
    expected = [
        {'mid': '/m/0663v', 'title': 'Pizza', 'type': 'Dish'},
        {'mid': '/g/11k19hmrkk', 'title': 'Licorice Pizza', 'type': '2021 film'},
        {'mid': '/m/0rg8s1t', 'title': 'Dominos Pizza', 'type': 'Topic'},
        {'mid': '/m/0dfxdnc', 'title': 'Pizza dough', 'type': 'Food'},
        {'mid': '/g/11hdxfw7c0', 'title': 'history of pizza', 'type': 'Food'},
    ]
    assert result == expected


@pytest.mark.vcr
def test_interest_over_time_partial():
    # NOTE: This test may fails if regenerate the cassette on Mondays because the last week will not be partial
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'])
    df_result = pytrend.interest_over_time()
    s_last_row = df_result.iloc[-1]
    assert s_last_row.isPartial is np.bool_(True)


def test_request_args_passing(mocked_responses):
    mocked_responses.add(
        url=f'{BASE_TRENDS_URL}/?geo=US',
        method='GET',
        match=[responses.matchers.header_matcher({'User-Agent': 'pytrends'})]
    )
    mocked_responses.add(
        url=TRENDING_RSS_URL,
        method='GET',
        match=[responses.matchers.header_matcher({'User-Agent': 'pytrends'})],
        body=TRENDING_RSS_FIXTURE.read_bytes(),
        content_type='text/xml',
    )
    requests_args = {'headers': {
        'User-Agent': 'pytrends',
    }}
    pytrend = TrendReq(requests_args=requests_args)
    pytrend.trending_searches()


def test_non_200_javascript_response_raises_response_error(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='POST',
        url=TrendReq.GENERAL_URL,
        status=500,
        body='<html>server error</html>',
        content_type='text/javascript',
    )
    pytrend = TrendReq()
    with pytest.raises(ResponseError):
        pytrend.build_payload(kw_list=['pizza'])


def test_response_without_content_type_raises_too_many_requests(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='POST',
        url=TrendReq.GENERAL_URL,
        status=429,
        body='',
        content_type=None,
    )
    pytrend = TrendReq()
    with pytest.raises(TooManyRequestsError):
        pytrend.build_payload(kw_list=['pizza'])


def test_retries_use_allowed_methods(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='POST',
        url=TrendReq.GENERAL_URL,
        body=')]}\'\n{"widgets": []}',
        content_type='application/json',
    )
    created_sessions = []
    real_session = requests.session

    def capturing_session():
        session = real_session()
        created_sessions.append(session)
        return session

    pytrend = TrendReq(retries=2, backoff_factor=0.1)
    with patch('pytrends.request.requests.session', side_effect=capturing_session):
        pytrend.build_payload(kw_list=['pizza'])

    retry = created_sessions[-1].get_adapter('https://').max_retries
    assert retry.allowed_methods == frozenset({'GET', 'POST'})


def test_init_does_not_mutate_requests_args():
    requests_args = {'headers': {'User-Agent': 'pytrends'}, 'verify': True}
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        TrendReq(requests_args=requests_args)
    assert requests_args == {'headers': {'User-Agent': 'pytrends'}, 'verify': True}


def test_cookie_error_with_requests_args_proxy_propagates():
    # The second response is ready so that a retry loop would succeed instead of hanging.
    ok_response = MagicMock(status_code=200)
    ok_response.cookies.items.return_value = [('NID', 'cookie-value')]
    dead_proxy = requests.exceptions.ConnectionError('dead proxy')
    with patch('pytrends.request.requests.get', side_effect=[dead_proxy, ok_response]) as get:
        with pytest.raises(requests.exceptions.ConnectionError):
            TrendReq(requests_args={'proxies': {'https': 'https://127.0.0.1:9'}})
    assert get.call_count == 1


def test_failing_last_proxy_is_skipped_without_index_error():
    ok_response = MagicMock(status_code=200)
    ok_response.cookies.items.return_value = [('NID', 'cookie-value')]
    proxy_error = requests.exceptions.ProxyError('dead proxy')
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq(proxies=['https://10.0.0.1:8080', 'https://10.0.0.2:8080'])
    pytrend.proxy_index = 1  # the failing proxy is the last one in the list
    with patch('pytrends.request.requests.get', side_effect=[proxy_error, ok_response]) as get:
        cookies = pytrend.GetGoogleCookie()
    assert cookies == {'NID': 'cookie-value'}
    assert get.call_count == 2


def test_empty_geo_after_country_queries_worldwide():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
        pytrend.build_payload(['pizza'], geo='')
    items = json.loads(pytrend.token_payload['req'])['comparisonItem']
    assert [item['geo'] for item in items] == ['']


@pytest.mark.parametrize('geo, resolution, expected', [
    ('', 'CITY', 'CITY'),
    ('US', 'DMA', 'DMA'),
])
def test_interest_by_region_sends_requested_resolution(geo, resolution, expected):
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo=geo)
    # Google's widget defaults to COUNTRY; the resolution argument should override it.
    pytrend.interest_by_region_widget = {'request': {'resolution': 'COUNTRY'}, 'token': 'token'}
    with patch.object(TrendReq, '_get_data', return_value={'default': {'geoMapData': []}}) as get_data:
        pytrend.interest_by_region(resolution=resolution)
    sent = json.loads(get_data.call_args.kwargs['params']['req'])
    assert sent['resolution'] == expected


def test_interest_by_region_without_geo_columns_returns_values():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
    pytrend.interest_by_region_widget = {'request': {'resolution': 'COUNTRY'}, 'token': 'token'}
    geo_map = {'default': {'geoMapData': [
        {'geoName': 'Texas', 'value': [80]},
        {'geoName': 'Ohio', 'value': [40]},
    ]}}
    with patch.object(TrendReq, '_get_data', return_value=geo_map):
        result = pytrend.interest_by_region()
    assert list(result.index) == ['Ohio', 'Texas']
    assert list(result['pizza']) == [40, 80]


def test_interest_by_region_warns_when_geo_code_requested_but_missing(caplog):
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
    pytrend.interest_by_region_widget = {'request': {'resolution': 'COUNTRY'}, 'token': 'token'}
    geo_map = {'default': {'geoMapData': [{'geoName': 'Texas', 'value': [80]}]}}
    with patch.object(TrendReq, '_get_data', return_value=geo_map), \
            caplog.at_level(logging.WARNING, logger='pytrends'):
        result = pytrend.interest_by_region(inc_geo_code=True)
    assert list(result['pizza']) == [80]
    assert 'Could not find geo_code column; Skipping' in caplog.text


def test_related_queries_empty_ranked_list_returns_none():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq()
    pytrend.related_queries_widget_list = [{
        'request': {'restriction': {'complexKeywordsRestriction': {'keyword': [{'value': 'pizza'}]}}},
        'keywordName': 'pizza',
        'token': 'token',
    }]
    with patch.object(TrendReq, '_get_data', return_value={'default': {'rankedList': []}}):
        result = pytrend.related_queries()
    assert result == {'pizza': {'top': None, 'rising': None}}


def test_related_topics_empty_ranked_list_returns_none():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq()
    pytrend.related_topics_widget_list = [{
        'request': {'restriction': {'complexKeywordsRestriction': {'keyword': [{'value': 'pizza'}]}}},
        'keywordName': 'pizza',
        'token': 'token',
    }]
    with patch.object(TrendReq, '_get_data', return_value={'default': {'rankedList': []}}):
        result = pytrend.related_topics()
    assert result == {'pizza': {'top': None, 'rising': None}}


@pytest.mark.parametrize('method_name, widget_list_name', [
    ('related_queries', 'related_queries_widget_list'),
    ('related_topics', 'related_topics_widget_list'),
])
def test_related_results_keyed_by_full_keyword_name(method_name, widget_list_name):
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq()
    setattr(pytrend, widget_list_name, [{
        'request': {'restriction': {'complexKeywordsRestriction': {'keyword': [
            {'type': 'BROAD', 'value': 'blockchain'},
            {'type': 'BROAD', 'value': 'bitcoin'},
        ]}}},
        'keywordName': 'blockchain + bitcoin',
        'token': 'token',
    }])
    with patch.object(TrendReq, '_get_data', return_value={'default': {'rankedList': []}}):
        result = getattr(pytrend, method_name)()
    assert list(result) == ['blockchain + bitcoin']


def test_categories_returns_parsed_tree(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='GET',
        url=TrendReq.CATEGORIES_URL,
        body=')]}\',\n{"children": [{"name": "Arts", "id": 3}]}',
        content_type='application/json',
    )
    pytrend = TrendReq()
    assert pytrend.categories() == {'children': [{'name': 'Arts', 'id': 3}]}


def test_interest_by_region_includes_geo_code_when_requested():
    geo_map = {'default': {'geoMapData': [{'geoName': 'Japan', 'geoCode': 'JP', 'value': [50]}]}}
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'])
    pytrend.interest_by_region_widget = {'request': {'resolution': 'COUNTRY'}, 'token': 'token'}
    with patch.object(TrendReq, '_get_data', return_value=geo_map):
        with_code = pytrend.interest_by_region(inc_geo_code=True)
        without_code = pytrend.interest_by_region(inc_geo_code=False)
    assert with_code.loc['Japan', 'geoCode'] == 'JP'
    assert with_code.loc['Japan', 'pizza'] == 50
    assert 'geoCode' not in without_code.columns


def test_interest_over_time_emits_no_warnings():
    timeline = {'default': {'timelineData': [
        {'time': '1609459200', 'value': [10], 'isPartial': False},
        {'time': '1609545600', 'value': [20], 'isPartial': True},
        # Some rows (e.g. the newest week) come back without isPartial, which becomes NaN.
        {'time': '1609632000', 'value': [30]},
    ]}}
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'])
    pytrend.interest_over_time_widget = {'request': {}, 'token': 'token'}
    with patch.object(TrendReq, '_get_data', return_value=timeline), \
            warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        pytrend.interest_over_time()
    future_warnings = [str(w.message) for w in caught if issubclass(w.category, FutureWarning)]
    assert future_warnings == []


def test_timeframe_list_length_mismatch_raises_value_error():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        # two keywords x two regions need four timeframes, but only two are given
        with pytest.raises(ValueError, match='timeframe'):
            pytrend.build_payload(
                ['pizza', 'bagel'],
                timeframe=['2021-01-01 2021-01-05', '2021-01-06 2021-01-10'],
                geo=['US-NY', 'US-IL'],
            )


def test_non_2xx_cookie_response_raises(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        status=404,
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    with pytest.raises(ResponseError):
        TrendReq()


def test_429_json_response_raises_too_many_requests(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='POST',
        url=TrendReq.GENERAL_URL,
        status=429,
        json={'error': 'quota exceeded'},
    )
    pytrend = TrendReq()
    with pytest.raises(TooManyRequestsError):
        pytrend.build_payload(kw_list=['pizza'])


@pytest.mark.vcr
def test_interest_over_time_multiple_regions():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], geo=['US-NY', 'US-IL'])
    df = pytrend.interest_over_time()
    assert df is not None
    pd.testing.assert_index_equal(
        df.columns,
        pd.MultiIndex.from_tuples(
            [
                ('pizza', 'US-NY'),
                ('pizza', 'US-IL'),
                ('bagel', 'US-NY'),
                ('bagel', 'US-IL'),
                ('isPartial', ),
            ],
            names=['keyword', 'region']
        )
    )
    assert df[('pizza', 'US-NY')].notna().all()
    assert df[('pizza', 'US-IL')].notna().all()
    assert (df[('pizza', 'US-NY')] >= 0).all()
    assert (df[('pizza', 'US-IL')] >= 0).all()


TRENDING_RSS_FIXTURE = Path(__file__).parent / 'fixtures' / 'trending_rss_US.xml'


def test_trending_rss_items_parse_into_dataframe():
    df = parse_trending_rss(TRENDING_RSS_FIXTURE.read_bytes())
    assert list(df.columns) == ['title', 'approx_traffic', 'pub_date', 'articles']
    assert len(df) == 10
    assert df.iloc[0]['title'] == 'sc lottery'
    assert df.iloc[0]['approx_traffic'] == '500+'
    assert df.iloc[0]['pub_date'] == 'Tue, 3 Nov 2026 10:50:00 -0800'


def test_trending_searches_requests_rss_for_country_code(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        responses.GET,
        TRENDING_RSS_URL,
        body=TRENDING_RSS_FIXTURE.read_bytes(),
        content_type='text/xml',
        match=[responses.matchers.query_param_matcher({'geo': 'US'})],
    )
    titles = TrendReq().trending_searches(pn='US')
    assert len(titles) == 10
    assert titles.iloc[0] == 'sc lottery'


def test_today_searches_and_realtime_use_rss(mocked_responses):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        responses.GET,
        TRENDING_RSS_URL,
        body=TRENDING_RSS_FIXTURE.read_bytes(),
        content_type='text/xml',
        match=[responses.matchers.query_param_matcher({'geo': 'US'})],
    )
    pytrend = TrendReq()
    today = pytrend.today_searches(pn='US')
    realtime = pytrend.realtime_trending_searches(pn='US')

    feed_requests = [call for call in mocked_responses.calls if call.request.url.startswith(TRENDING_RSS_URL)]
    assert len(feed_requests) == 2
    assert today.iloc[0] == 'sc lottery'
    assert list(realtime.columns) == ['title', 'approx_traffic', 'pub_date', 'articles']
    assert realtime.iloc[0]['articles'][0] == {
        'title': 'Palmetto Cash 5 delivers million dollar treat to Barnwell lotto player on Halloween',
        'url': 'https://www.wjbf.com/news/south-carolina-news/palmetto-cash-5-delivers-million-dollar-treat-to-barnwell-on-halloween/',
        'source': 'WJBF',
    }


@pytest.mark.parametrize('method', ['trending_searches', 'today_searches', 'realtime_trending_searches'])
def test_legacy_country_names_raise_value_error(mocked_responses, method):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    pytrend = TrendReq()
    with pytest.raises(ValueError, match="two-letter country code such as 'US'"):
        getattr(pytrend, method)(pn='united_states')
    assert not [call for call in mocked_responses.calls if call.request.url.startswith(TRENDING_RSS_URL)]


@pytest.mark.parametrize('prefix', [")]}'\n", ")]}',\n", ")]}'", ")]}',"])
def test_get_data_strips_any_xssi_prefix(mocked_responses, prefix):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/api/test',
        body=prefix + '{"default": {"ok": true}}',
        content_type='application/json',
    )
    pytrend = TrendReq()
    assert pytrend._get_data(url=f'{BASE_TRENDS_URL}/api/test') == {'default': {'ok': True}}


def test_diagnostics_use_logging_not_print(mocked_responses, caplog, capsys):
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        body=requests.exceptions.ProxyError(),
    )
    mocked_responses.add(
        method='GET',
        url=f'{BASE_TRENDS_URL}/?geo=US',
        headers={'Set-Cookie': 'NID=511=test; path=/'},
    )
    with caplog.at_level(logging.WARNING, logger='pytrends'):
        TrendReq(proxies=['https://127.0.0.1:1', 'https://127.0.0.2:1'])

        def always_rate_limited(timeframe):
            raise ResponseError('rate limited', None)

        with patch.object(dailydata, 'sleep'), pytest.raises(ResponseError):
            dailydata._fetch_data(None, always_rate_limited, '2021-01-01 2021-01-31')
    assert capsys.readouterr().out == ''
    assert 'Proxy error. Changing IP' in caplog.text
    assert 'Failed after 3 attemps, abort fetching.' in caplog.text
