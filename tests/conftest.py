import pytest
from responses import RequestsMock


@pytest.fixture
def vcr_config():
    """Settings for pytest-recording (VCR.py) applied to every cassette."""
    return {
        # Store readable bodies instead of gzip bytes when recording.
        "decode_compressed_response": True,
        # Never store the session cookie in a cassette.
        "filter_headers": ["cookie"],
    }


@pytest.fixture
def mocked_responses():
    requests_mock = RequestsMock(
        assert_all_requests_are_fired=True
    )
    with requests_mock as mocked_responses:
        yield mocked_responses
