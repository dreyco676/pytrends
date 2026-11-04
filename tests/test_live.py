"""Live contract tests against the real Google Trends API.

These tests are deselected by default. Run them with:

    uv run pytest -o addopts="" -m live

They need network access and Google's responses change over time, so each
test is paced to avoid rate limiting.
"""
import time
import xml.etree.ElementTree as ET

import pandas as pd
import pytest
import requests

from pytrends.dailydata import get_daily_data
from pytrends.exceptions import ResponseError
from pytrends.request import BASE_TRENDS_URL, TrendReq

pytestmark = pytest.mark.live

# Seconds to wait after each live test so Google does not rate-limit the run.
PAUSE_BETWEEN_REQUESTS = 2


@pytest.fixture(autouse=True)
def pace_live_requests():
    yield
    time.sleep(PAUSE_BETWEEN_REQUESTS)


def test_live_cookie_url_answers_200_with_nid():
    # The same URL TrendReq.GetGoogleCookie requests for hl='en-US'.
    response = requests.get(f'{BASE_TRENDS_URL}/?geo=US', timeout=(5, 15))
    assert response.status_code == 200
    assert 'NID' in response.cookies


TRENDING_RSS_URL = 'https://trends.google.com/trending/rss'
HT_NAMESPACE = '{https://trends.google.com/trending/rss}'


def test_live_trending_rss_parses():
    response = requests.get(TRENDING_RSS_URL, params={'geo': 'US'}, timeout=(5, 15))
    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith('text/xml')

    items = ET.fromstring(response.content).findall('./channel/item')
    assert items
    for item in items:
        assert item.findtext('title')
        assert item.findtext(f'{HT_NAMESPACE}approx_traffic')
        assert item.findtext('pubDate')
        assert item.findall(f'{HT_NAMESPACE}news_item')


@pytest.mark.parametrize('method', ['trending_searches', 'today_searches', 'realtime_trending_searches'])
def test_live_trending_rss_methods(method):
    result = getattr(TrendReq(), method)(pn='US')
    assert len(result) > 0


def test_live_interest_by_region_resolution():
    pytrend = TrendReq(hl='en-US', tz=360)

    pytrend.build_payload(['pizza'], timeframe='2024-01-01 2024-12-31')
    countries = pytrend.interest_by_region(resolution='COUNTRY')
    assert 'United States' in countries.index

    pytrend.build_payload(['pizza'], geo='US', timeframe='2024-01-01 2024-12-31')
    metros = pytrend.interest_by_region(resolution='DMA')
    assert 'New York NY' in metros.index


def test_live_build_payload_returns_widget_tokens():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza', 'bagel'], timeframe='2024-01-01 2024-12-31')

    interest = pytrend.interest_over_time_widget
    assert interest['id'] == 'TIMESERIES'
    assert interest['token']

    region = pytrend.interest_by_region_widget
    assert region['id'] == 'GEO_MAP'
    assert region['token']

    related = pytrend.related_queries_widget_list
    assert [w['keywordName'] for w in related] == ['pizza', 'bagel']
    assert all('RELATED_QUERIES' in w['id'] and w['token'] for w in related)


def test_live_interest_over_time_shape():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza', 'bagel'], timeframe='2024-01-01 2024-12-31')
    df = pytrend.interest_over_time()

    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df.columns) == ['pizza', 'bagel', 'isPartial']
    for keyword in ['pizza', 'bagel']:
        assert pd.api.types.is_integer_dtype(df[keyword]), keyword
        assert df[keyword].between(0, 100).all(), keyword
    assert pd.api.types.is_bool_dtype(df['isPartial'])


def test_live_interest_over_time_multiple_regions():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(
        ['pizza', 'bagel'],
        geo=['US-NY', 'US-IL'],
        timeframe='2024-01-01 2024-12-31',
    )
    df = pytrend.interest_over_time()

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
    for column in [('pizza', 'US-NY'), ('pizza', 'US-IL'), ('bagel', 'US-NY'), ('bagel', 'US-IL')]:
        assert df[column].between(0, 100).all(), column


def test_live_multirange_interest_over_time_shape():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(
        ['pizza', 'bagel'],
        timeframe=['2024-01-01 2024-01-31', '2024-02-01 2024-02-29'],
    )
    df = pytrend.multirange_interest_over_time()

    assert list(df.columns) == [
        '[0] pizza date',
        '[0] pizza value',
        '[1] bagel date',
        '[1] bagel value',
    ]
    # The first row holds the per-range averages.
    assert df.iloc[0]['[0] pizza date'] == 'Average'
    assert df.iloc[0]['[1] bagel date'] == 'Average'
    assert pd.api.types.is_number(df.iloc[0]['[0] pizza value'])
    assert pd.api.types.is_number(df.iloc[0]['[1] bagel value'])
    # Every row after the average is a dated point.
    assert (df.iloc[1:]['[0] pizza date'] != 'Average').all()


def test_live_related_queries_shape():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza', 'bagel'], timeframe='2024-01-01 2024-12-31')
    related = pytrend.related_queries()

    assert list(related) == ['pizza', 'bagel']
    assert any(result is not None for result in related.values())
    for keyword, result in related.items():
        assert result is None or set(result) == {'top', 'rising'}, keyword
        for kind in ('top', 'rising'):
            frame = None if result is None else result[kind]
            if frame is None:
                continue
            assert {'query', 'value'} <= set(frame.columns), (keyword, kind)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        'plan 1.9: Google sent an empty RELATED_TOPICS rankedList for pizza, bagel and Taylor Swift '
        '(2026-11-03); two keywords send no RELATED_TOPICS widget at all'
    ),
)
def test_live_related_topics_single_keyword():
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza'], timeframe='2024-01-01 2024-12-31')
    topics = pytrend.related_topics()

    assert list(topics) == ['pizza']
    result = topics['pizza']
    assert result is not None
    for kind in ('top', 'rising'):
        frame = result[kind]
        assert frame is not None, kind
        assert {'topic_title', 'topic_type', 'value'} <= set(frame.columns), kind
        assert len(frame) > 0, kind


def test_live_suggestions_and_categories():
    pytrend = TrendReq(hl='en-US', tz=360)

    suggestions = pytrend.suggestions('pizza')
    assert isinstance(suggestions, list)
    assert suggestions
    for suggestion in suggestions:
        assert {'mid', 'title', 'type'} <= set(suggestion)

    categories = pytrend.categories()
    assert isinstance(categories, dict)
    assert 'children' in categories


def test_live_daily_data_two_months():
    df = get_daily_data('pizza', 2024, 1, 2024, 2, verbose=False, wait_time=2)

    # 2024 is a leap year: January (31 days) plus February (29 days).
    assert len(df) == 60
    assert df['pizza'].notna().all()


def test_live_interest_by_region_resolution_outside_us():
    # GB REGION returned 4 rows (England, Northern Ireland, Scotland, Wales) on 2026-11-03,
    # so CITY must return more than that. Google caps the city list at 200 rows.
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza'], geo='GB', timeframe='2024-01-01 2024-12-31')
    gb_cities = pytrend.interest_by_region(resolution='CITY')
    assert len(gb_cities) > 4

    pytrend.build_payload(['pizza'], geo='US-CA', timeframe='2024-01-01 2024-12-31')
    ca_cities = pytrend.interest_by_region(resolution='CITY')
    assert len(ca_cities) > 0


def test_live_interest_by_region_rejects_country_level_for_subregions():
    # Google answers 400 when the resolution is the geo's own level:
    # COUNTRY for GB, and REGION for US-CA.
    pytrend = TrendReq(hl='en-US', tz=360)
    pytrend.build_payload(['pizza'], geo='GB', timeframe='2024-01-01 2024-12-31')
    with pytest.raises(ResponseError):
        pytrend.interest_by_region(resolution='COUNTRY')

    pytrend.build_payload(['pizza'], geo='US-CA', timeframe='2024-01-01 2024-12-31')
    with pytest.raises(ResponseError):
        pytrend.interest_by_region(resolution='REGION')
