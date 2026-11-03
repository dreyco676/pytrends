"""Live contract tests against the real Google Trends API.

These tests are deselected by default. Run them with:

    uv run pytest -o addopts="" -m live

They need network access and Google's responses change over time, so each
test is paced to avoid rate limiting.
"""
import time
import xml.etree.ElementTree as ET

import pytest
import requests

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
