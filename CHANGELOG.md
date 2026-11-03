# Changelog

## 5.0.0 (unreleased)

### Breaking changes

* Requires Python 3.12 or later. CI tests 3.12 to 3.15.
* The `lxml` dependency is gone. Runtime dependencies are now `requests>=2.32.4`, `pandas>=2.2.2` and `urllib3>=1.26.5`.
* `trending_searches`, `today_searches` and `realtime_trending_searches` read Google's Trending Now RSS feed. Google removed the old endpoints (they returned HTTP 404).
  * `pn` takes two-letter country codes only, for example `'US'`. Legacy names such as `'united_states'` raise `ValueError`.
  * `trending_searches` and `today_searches` return a `pandas.Series` of titles. `trending_searches` used to return a DataFrame.
  * `realtime_trending_searches` returns the columns `title`, `approx_traffic`, `pub_date` and `articles`. The `entityNames` column is gone, and the `cat` and `count` arguments are removed.
* `top_charts` is removed. Google removed its endpoint and there is no replacement.
* `get_historical_interest` is removed. It only raised `NotImplementedError`.
* Progress and warnings go through `logging` (logger `pytrends`) instead of `print`. `get_daily_data(verbose=True)` logs progress at `info`, so you see it only when logging is configured.
* `get_daily_data` raises the `ResponseError` after its retries are exhausted. It used to return stale data.

### Added

* `get_explore_url()` returns the trends.google.com explore link for the payload set up by the last `build_payload()`.
* `related_queries` keeps Google's `formattedValue` and `link` columns, as `related_topics` already did.
* `pip install pytrends[socks]` installs PySocks, so `socks5://` proxies work.
* The package ships a `py.typed` marker, and the public methods have type hints.

### Changed

* `interest_by_region` sends the requested `resolution` for any single location. Google decides what an unsupported combination returns, so it may fall back to its default level.
* Each `TrendReq` keeps one `requests` session for its life, with its retries and headers set up once. Cookies are fetched once per proxy, not once per request.

### Fixed

* The cookie request uses the `trends.google.com/trends/?geo=` endpoint, which answers 200 with an NID cookie. A non-2xx cookie response raises `ResponseError`.
* A 429 with a JSON body raises `TooManyRequestsError`. A non-200 JavaScript response raises `ResponseError`.
* `interest_by_region` sends the requested `resolution`, and the geo setting no longer sticks between calls.
* `build_payload` raises `ValueError` when a list of timeframes does not match the number of keywords and regions.
* Proxy rotation resets its index correctly, and a failing last proxy is skipped without an `IndexError`.
* `requests_args` is no longer mutated by `TrendReq()`.
* `related_queries` and `related_topics` key results by the full keyword name. Empty ranked lists return `None`.
* Responses with an XSSI prefix (`)]}'`, with or without a comma or newline) parse correctly.
* Compatible with pandas 3 (labels, `json_normalize` on lists, copy-on-write `ffill`) and free of pandas 2.2 and 3 deprecation warnings.
* Compatible with urllib3 2.x retries (`allowed_methods` replaces the removed `method_whitelist`).
* The `isPartial` column is a clean boolean, and `get_daily_data` documents its five columns.

### Known limits

* Google rate-limits the explore API. During testing, about eight live requests in quick succession returned HTTP 429. Pause between calls, or use `retries`, `backoff_factor` or `proxies`.
* Data fidelity against the public Google Trends site is not yet verified for this release.
