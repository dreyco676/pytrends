"""Live contract tests against the real Google Trends API.

These tests are deselected by default. Run them with:

    uv run pytest -o addopts="" -m live

They need network access and Google's responses change over time, so each
test is paced to avoid rate limiting.
"""
import time

import pytest
import requests

from pytrends.request import BASE_TRENDS_URL

pytestmark = pytest.mark.live

# Seconds to wait after each live test so Google does not rate-limit the run.
PAUSE_BETWEEN_REQUESTS = 2


@pytest.fixture(autouse=True)
def pace_live_requests():
    yield
    time.sleep(PAUSE_BETWEEN_REQUESTS)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="plan 2.9: cookie URL returns 404 while still setting NID",
)
def test_live_cookie_url_answers_200_with_nid():
    # The same URL TrendReq.GetGoogleCookie requests for hl='en-US'.
    response = requests.get(f'{BASE_TRENDS_URL}/explore/?geo=US', timeout=(5, 15))
    assert response.status_code == 200
    assert 'NID' in response.cookies
