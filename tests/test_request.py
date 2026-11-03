from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import logging
import re
import warnings

import pandas as pd
import pytest
import requests
import responses
import yaml
from pandas.testing import assert_frame_equal

from pytrends import dailydata
from pytrends.exceptions import ResponseError, TooManyRequestsError
from pytrends.request import TrendReq, BASE_TRENDS_URL, TRENDING_RSS_URL, parse_trending_rss


CASSETTE_DIR = Path(__file__).parent / 'cassettes' / 'test_request'
XSSI_PREFIX = re.compile(r"^\)\]\}',?\n?")

QUERY_PATHS = {'query': ('query',), 'value': ('value',)}
TOPIC_PATHS = {
    'topic_mid': ('topic', 'mid'),
    'topic_title': ('topic', 'title'),
    'topic_type': ('topic', 'type'),
    'value': ('value',),
    'formattedValue': ('formattedValue',),
    'link': ('link',),
}


def recorded_responses(test_name, uri_fragment):
    """Parsed JSON bodies of the recorded 200 responses whose request URI contains uri_fragment, in order.

    The cassette tests take their expected values from these bodies instead of typing them in,
    so re-recording a cassette does not mean editing the test.
    """
    interactions = yaml.safe_load((CASSETTE_DIR / f'{test_name}.yaml').read_text())['interactions']
    bodies = [
        json.loads(XSSI_PREFIX.sub('', interaction['response']['body']['string']))
        for interaction in interactions
        if uri_fragment in interaction['request']['uri'] and interaction['response']['status']['code'] == 200
    ]
    assert bodies, f'no recorded response for {uri_fragment!r} in {test_name}'
    return bodies


def ranked_keywords(test_name, nth_request, rank):
    """The keyword dicts in one ranked list (0 = top, 1 = rising) of the nth related-searches response."""
    body = recorded_responses(test_name, 'widgetdata/relatedsearches')[nth_request]
    return body['default']['rankedList'][rank]['rankedKeyword']


def assert_interest_over_time_matches_recording(df, test_name, keywords, timeframe=None):
    points = recorded_responses(test_name, 'widgetdata/multiline')[0]['default']['timelineData']
    # structure: a datetime index in order, one int column per keyword in 0-100, and a bool isPartial
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.is_monotonic_increasing
    assert list(df.columns) == [*keywords, 'isPartial']
    assert df[keywords].isin(list(range(101))).all().all()
    if timeframe is not None:
        start, end = (pd.Timestamp(day) for day in timeframe.split())
        assert df.index.min() >= start
        assert df.index.max() <= end
    # values: exactly the recorded points
    expected = pd.DataFrame(
        {keyword: [point['value'][i] for point in points] for i, keyword in enumerate(keywords)},
        index=pd.DatetimeIndex(pd.to_datetime([int(point['time']) for point in points], unit='s'), name='date'),
    )
    expected['isPartial'] = [bool(point.get('isPartial', False)) for point in points]
    assert_frame_equal(df, expected)


def assert_multirange_matches_recording(df, test_name, keywords):
    body = recorded_responses(test_name, 'widgetdata/multirange')[0]['default']
    points = body['timelineData']
    expected = {}
    for i, keyword in enumerate(keywords):
        # the average row comes first, then one row per recorded point
        expected[f'[{i}] {keyword} date'] = ['Average'] + [point['columnData'][i]['formattedTime'] for point in points]
        expected[f'[{i}] {keyword} value'] = [body['averages'][i]] + [point['columnData'][i]['value'] for point in points]
    assert_frame_equal(df.reset_index(drop=True), pd.DataFrame(expected))


def assert_interest_by_region_matches_recording(df, test_name, keywords):
    regions = recorded_responses(test_name, 'widgetdata/comparedgeo')[0]['default']['geoMapData']
    assert df[keywords].isin(list(range(101))).all().all()
    expected = pd.DataFrame(
        {keyword: [int(region['value'][i]) for region in regions] for i, keyword in enumerate(keywords)},
        index=pd.Index([region['geoName'] for region in regions], name='geoName'),
    ).sort_index()
    assert_frame_equal(df, expected)


def assert_ranked_rows_match_recording(df, keywords, paths):
    """Each column of df holds, row by row, the recorded value at its path in each ranked keyword."""
    assert len(df) == len(keywords)
    for column, path in paths.items():
        recorded = []
        for item in keywords:
            for key in path:
                item = item[key]
            recorded.append(item)
        assert list(df[column]) == recorded, column


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
    widgets = recorded_responses('test_tokens', 'api/explore')[0]['widgets']
    expected = [widget for widget in widgets if 'RELATED_QUERIES' in widget['id']]
    assert pytrend.related_queries_widget_list == expected


@pytest.mark.vcr
def test_interest_over_time_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    assert_interest_over_time_matches_recording(
        df_result, 'test_interest_over_time_ok', ['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')


@pytest.mark.vcr
def test_interest_over_time_images():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], gprop='images', timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    assert_interest_over_time_matches_recording(
        df_result, 'test_interest_over_time_images', ['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')


@pytest.mark.vcr
def test_interest_over_time_news():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], gprop='news', timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    assert_interest_over_time_matches_recording(
        df_result, 'test_interest_over_time_news', ['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')


@pytest.mark.vcr
def test_interest_over_time_youtube():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], gprop='youtube', timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    assert_interest_over_time_matches_recording(
        df_result, 'test_interest_over_time_youtube', ['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')


@pytest.mark.vcr
def test_interest_over_time_froogle():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], gprop='froogle', timeframe='2021-01-01 2021-01-05')
    df_result = pytrend.interest_over_time()
    assert_interest_over_time_matches_recording(
        df_result, 'test_interest_over_time_froogle', ['pizza', 'bagel'], timeframe='2021-01-01 2021-01-05')


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
    assert_multirange_matches_recording(df_result, 'test_multirange_interest_over_time_ok', ['pizza', 'bagel'])


@pytest.mark.vcr
def test_multirange_interest_over_time_same_keyword_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'pizza'], timeframe=['2021-01-01 2021-01-05', '2021-01-06 2021-01-10'])
    df_result = pytrend.multirange_interest_over_time()
    assert_multirange_matches_recording(
        df_result, 'test_multirange_interest_over_time_same_keyword_ok', ['pizza', 'pizza'])


@pytest.mark.vcr
def test_interest_by_region_ok():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.interest_by_region()
    assert_interest_by_region_matches_recording(df_result, 'test_interest_by_region_ok', ['pizza', 'bagel'])


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
    keywords = ranked_keywords('test_related_topics_result_top', nth_request=0, rank=0)
    assert_ranked_rows_match_recording(df_result, keywords, TOPIC_PATHS)


@pytest.mark.vcr
def test_related_topics_result_rising():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_topics()['pizza']['rising']
    keywords = ranked_keywords('test_related_topics_result_rising', nth_request=0, rank=1)
    assert_ranked_rows_match_recording(df_result, keywords, TOPIC_PATHS)


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
    for nth_request, keyword in enumerate(['pizza', 'bagel']):
        keywords = ranked_keywords('test_related_queries_result_top', nth_request=nth_request, rank=0)
        assert_ranked_rows_match_recording(df_result[keyword]['top'], keywords, QUERY_PATHS)


@pytest.mark.vcr
def test_related_queries_result_rising():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe='2021-01-01 2021-12-31')
    df_result = pytrend.related_queries()
    for nth_request, keyword in enumerate(['pizza', 'bagel']):
        keywords = ranked_keywords('test_related_queries_result_rising', nth_request=nth_request, rank=1)
        assert_ranked_rows_match_recording(df_result[keyword]['rising'], keywords, QUERY_PATHS)


@pytest.mark.vcr
def test_suggestions_ok():
    pytrend = TrendReq()
    # suggestions doesn't need to call build_payload.
    result = pytrend.suggestions(keyword='pizza')
    topics = recorded_responses('test_suggestions_ok', 'api/autocomplete/pizza')[0]['default']['topics']
    assert result == [{'mid': topic['mid'], 'title': topic['title'], 'type': topic['type']} for topic in topics]


@pytest.mark.vcr
def test_interest_over_time_partial():
    pytrend = TrendReq()
    pytrend.build_payload(kw_list=['pizza', 'bagel'])
    df_result = pytrend.interest_over_time()
    # the isPartial flags, including the last week's, come from the recording
    assert_interest_over_time_matches_recording(df_result, 'test_interest_over_time_partial', ['pizza', 'bagel'])


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
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
    pytrend.related_queries_widget_list = [{
        'request': {'restriction': {'complexKeywordsRestriction': {'keyword': [{'value': 'pizza'}]}}},
        'keywordName': 'pizza',
        'token': 'token',
    }]
    with patch.object(TrendReq, '_get_data', return_value={'default': {'rankedList': []}}):
        result = pytrend.related_queries()
    assert result == {'pizza': {'top': None, 'rising': None}}


def test_related_topics_empty_ranked_list_returns_none():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
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
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}), \
            patch.object(TrendReq, '_tokens'):
        pytrend = TrendReq()
        pytrend.build_payload(['pizza'], geo='US')
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


@pytest.mark.parametrize('method', [
    'interest_over_time',
    'multirange_interest_over_time',
    'interest_by_region',
    'related_queries',
    'related_topics',
])
def test_data_methods_before_build_payload_raise_clear_error(method):
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq()
    with patch.object(TrendReq, '_get_data', side_effect=AssertionError('sent a request')), \
            pytest.raises(ValueError, match=r'build_payload\(\)'):
        getattr(pytrend, method)()


def test_build_payload_rejects_more_than_five_keywords():
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={}):
        pytrend = TrendReq()
    with patch.object(TrendReq, '_tokens') as tokens, \
            pytest.raises(ValueError, match='at most five keywords'):
        pytrend.build_payload(['pizza', 'bagel', 'sushi', 'tacos', 'ramen', 'pasta'])
    # the limit is checked before any request is made
    tokens.assert_not_called()


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


def test_proxied_requests_fetch_one_cookie_per_proxy(mocked_responses):
    proxies = ['https://127.0.0.1:1', 'https://127.0.0.2:1']
    mocked_responses.add(method='GET', url=f'{BASE_TRENDS_URL}/api/test', json={'default': {}})
    with patch.object(TrendReq, 'GetGoogleCookie', return_value={'NID': 'test'}) as get_cookie:
        pytrend = TrendReq(proxies=proxies)
        for _ in range(4):
            pytrend._get_data(url=f'{BASE_TRENDS_URL}/api/test')
    # the init plus four data requests, alternating between the two proxies
    assert get_cookie.call_count <= len(proxies)
