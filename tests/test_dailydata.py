from unittest.mock import patch

import pandas as pd
import pytest

from pytrends import dailydata
from pytrends.exceptions import ResponseError


class FakeTrendReq:
    """Stands in for TrendReq: monthly requests return one row per month, daily requests one row per day."""

    def __init__(self, *args, **kwargs):
        self.timeframe = None

    def build_payload(self, kw_list, cat=0, timeframe='', geo='', gprop=''):
        self.timeframe = timeframe

    def interest_over_time(self):
        start, stop = (pd.Timestamp(day) for day in self.timeframe.split())
        freq = 'MS' if (stop - start).days > 40 else 'D'
        index = pd.date_range(start, stop, freq=freq)
        return pd.DataFrame({'pizza': 50, 'isPartial': False}, index=pd.Index(index, name='date'))


def fetch_two_months():
    with patch.object(dailydata, 'TrendReq', FakeTrendReq), patch.object(dailydata, 'sleep'):
        return dailydata.get_daily_data('pizza', 2021, 1, 2021, 2, verbose=False, wait_time=0)


def test_daily_data_scale_has_no_gaps():
    complete = fetch_two_months()
    assert complete['scale'].notna().all()


def test_daily_data_returns_documented_columns():
    complete = fetch_two_months()
    assert set(complete.columns) == {
        'pizza', 'pizza_unscaled', 'pizza_monthly', 'isPartial', 'scale',
    }


class AlwaysRateLimited:
    """Every payload request fails; reading the data would return stale results."""

    def build_payload(self, timeframe):
        raise ResponseError('rate limited', None)

    def interest_over_time(self):
        return pd.DataFrame({'stale': [1]})


def test_fetch_data_raises_after_retries_exhausted():
    pytrends = AlwaysRateLimited()
    with patch.object(dailydata, 'sleep'), pytest.raises(ResponseError):
        dailydata._fetch_data(pytrends, pytrends.build_payload, '2021-01-01 2021-01-31')
