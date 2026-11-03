"""Live contract tests against the real Google Trends API.

These tests are deselected by default. Run them with:

    uv run pytest -o addopts="" -m live

They need network access and Google's responses change over time, so each
test is paced to avoid rate limiting.
"""
import time

import pytest

pytestmark = pytest.mark.live

# Seconds to wait after each live test so Google does not rate-limit the run.
PAUSE_BETWEEN_REQUESTS = 2


@pytest.fixture(autouse=True)
def pace_live_requests():
    yield
    time.sleep(PAUSE_BETWEEN_REQUESTS)
