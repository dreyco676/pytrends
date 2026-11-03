# Contributing

## Set up your environment

First of all, create a virtualenv usign `python -m venv` or whatever tool you use to manage them, and install the requirements listed in the requirements files:

```bash
$ python -m venv ~/virtualenvs/pytrends
$ pip -r install requirements.txt  # library requirements
$ pip -r install requirements-dev.txt  # development requirements
```

## Running the tests

To run the tests, simply run `pytest` inside the project root:

```bash
$ pytest
```

## Running the live tests

Some tests call the real Google Trends API. They are deselected by default because they need network access, are slow, and Google's responses change over time. To run them:

```bash
$ uv run pytest -o addopts="" -m live
```

Each live test pauses for 2 seconds afterwards so that Google does not rate-limit the run.

## About the test suite

There are two main libraries used in the test suite:

* [VCR.py](https://github.com/kevin1024/vcrpy): Records requests and responses and replays them at every execution; we use it through [pytest-recording](https://github.com/kiwicom/pytest-recording)

* [responses](https://github.com/getsentry/responses): Mocks the `requests` library, able to reproduce edge cases and check the requests made.

If you don't know them we highly encourage you to take a peek at their README to understand what they are and the differences between them.

## VCR.py tests

VCR.py records the HTTP requests made by a test and the responses returned by the server, and save them in a YAML file called "cassette".

When a cassette exists, instead of passing the HTTP requests to the server VCR.py will catch the requests made by a test, search for it in the cassette file, and replays the recorded response for that exact request.

Use VCR.py to check the behavior of Google Trends API: check the response returned, know a specific request is valid, etc.

To use VCR.py in a test, decorate it with `pytest.mark.vcr`:

```python
@pytest.mark.vcr
def test_example():
    # This test will do real requests.
    pass
```

### Running a VCR.py test without cassette

The first time you execute a VCR.py test without a cassette file (e.g. a new test) you will get an error:

```
E               vcr.errors.CannotOverwriteExistingCassetteException: Can't overwrite existing cassette ('/home/user/pytrends/tests/cassettes/test_request/test_name.yaml') in your current record mode ('none').
E               No match for the request (<Request (GET) https://trends.google.com/?geo=US>) was found.
E               No similar requests, that have not been played, found.

.venv/python-3.7.10/lib/python3.7/site-packages/vcr/stubs/__init__.py:232: CannotOverwriteExistingCassetteException
```

By default `pytest-recording` will **not** let the requests pass to prevent unintentional network requests.

To create a new cassette use the pytest parameter `--record-mode=once`, this will write a new cassette for tests that doesn't have one yet and will replay the existing cassette for tests that does have it.

You can read more about this behavior in the [pytest-recording README](https://github.com/kiwicom/pytest-recording#default-recording-mode).

### Rewriting an existing cassette

Sometimes you will change how the requests are made or want to see if the library still handles correctly the requests made.

You have two options here:

* Delete the cassette file and execute the tests with `--record-mode=once`:

```bash
# The path format is `tests/cassettes/<test file name>/<test function name>.yaml`
$ rm tests/cassettes/test_request/test_build_payload.yaml
$ pytest --record-mode=once
```

* Execute the single test you want using `-k` and `--record-mode=rewrite`:

```bash
# the format is `pytest -k <pattern>`
$ pytest -k test_build_payload --record-mode=rewrite
```

Beware, the latter will execute all the tests whose name matches the pattern and rewrite its cassette.

Please keep in mind that the Google Trends API **can change its returned data over time, even a year-old data**, this means that when you regenerate the cassette of an existing test you may also need to update the data returned by the backend, the fastest way to get the new values is using the pytest `--pdb` flag to start a pdb session when the test fails comparing the expected `pd.DataFrame`:

```bash
$ pytest -k test_interest_over_time --pdb

E   AssertionError: DataFrame.iloc[:, 0] (column name="pizza") are different
E
E   DataFrame.iloc[:, 0] (column name="pizza") values are different (80.0 %)
E   [index]: [2021-01-01T00:00:00.000000000, 2021-01-02T00:00:00.000000000, 2021-01-03T00:00:00.000000000, 2021-01-04T00:00:00.000000000, 2021-01-05T00:00:00.000000000]
E   [left]:  [100, 80, 77, 50, 51]
E   [right]: [100, 87, 78, 51, 52]

pandas/_libs/testing.pyx:168: AssertionError

# By default the error of an `assert_frame_equal` is raised inside the Pandas code.
# Inspect the backtrace to find the point where we made the assert and move there.
(Pdb) bt

...
-> assert_frame_equal(df_result, df_expected)
  /home/user/pytrends/.venv/python-3.7.10/lib/python3.7/site-packages/pandas/_testing/asserters.py(1321)assert_frame_equal()
-> check_index=False,
  /home/user/pytrends/.venv/python-3.7.10/lib/python3.7/site-packages/pandas/_testing/asserters.py(1084)assert_series_equal()
-> index_values=np.asarray(left.index),
  /home/user/pytrends/pandas/_libs/testing.pyx(53)pandas._libs.testing.assert_almost_equal()
> /home/user/pytrends/pandas/_libs/testing.pyx(168)pandas._libs.testing.assert_almost_equal()
  /home/user/pytrends/.venv/python-3.7.10/lib/python3.7/site-packages/pandas/_testing/asserters.py(665)raise_assert_detail()
-> raise AssertionError(msg)

(Pdb) up
> /home/user/pytrends/pandas/_libs/testing.pyx(53)pandas._libs.testing.assert_almost_equal()
(Pdb) up
> /home/user/pytrends/.venv/python-3.7.10/lib/python3.7/site-packages/pandas/_testing/asserters.py(1084)assert_series_equal()
-> index_values=np.asarray(left.index),
(Pdb) up
> /home/user/pytrends/.venv/python-3.7.10/lib/python3.7/site-packages/pandas/_testing/asserters.py(1321)assert_frame_equal()
-> check_index=False,
(Pdb) up
> /home/user/pytrends/tests/test_request.py(179)test_interest_over_time_ok()
-> assert_frame_equal(df_result, df_expected)

# Check the returned response and see if it contains valid data.
# We can use the following values to update our test and make it pass.
(Pdb) df_result.to_dict(orient='list')
{'pizza': [100, 87, 78, 51, 52], 'bagel': [2, 2, 2, 1, 1], 'isPartial': [False, False, False, False, False]}
```

## responses tests

responses is used to monkey patch the `requests` library, intercepting requests and simulating responses from the backend without letting them pass through.

Use responses to simulate hard-to-reproduce behavior from the backend, to perform asserts on how a specific request is made, or to prevent unintended requests to be made.

To use responses in a test, make it receive the fixture `mocked_responses` and configure the mock adding the requests you expect the test to do and the response that the backend will return:

```python
def test_example(mocked_responses):
    mocked_responses.add(
        url="https://trends.google.com/?geo=US",
        method="GET",
        body=ConnectionError("Fake connection error")
    )
    # The next request made will throw a `ConnectionError` exception
```

The fixture `mocked_responses` is configured to always assert that all registered requests are made, otherwise it will fail:

```
E           AssertionError: Not all requests have been executed [('GET', 'https://trends.google.com/trends/fake_call')]
```
