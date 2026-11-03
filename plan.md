# pytrends revival plan

Evaluation and repair plan for this fork (`dreyco676/pytrends`). It drives a TDD loop: on **"go"**, take the first unchecked item below and complete exactly that item.

The baseline was gathered on 2026-11-03 from three sources:

- the offline suite, run on two dependency stacks;
- mocked, offline reproductions of each suspected defect;
- about two dozen paced, read-only requests to live Google Trends from a residential IP.

Upstream `GeneralMills/pytrends` is archived, so nothing can be merged there. Its open PRs are triaged below and adopted by re-implementing them here.

## How to work this plan

- **"go"** → first unchecked `- [ ]` item, top to bottom, one item per cycle.
- Item kinds:
  - **TEST**: behavioral change. Write the one named test. Run it and see it fail *for the stated reason*. Write the minimum code to pass. Run the full offline suite and the linter, then refactor while green. Commit `behavior: <id> …`.
  - **TIDY**: structural or tooling change with no behavior change. Suite results must be identical before and after, except quarantine markers the item explicitly removes. Commit `structure: <id> …`.
  - **LIVE**: contract test against real Google, marked `@pytest.mark.live` and excluded from default runs. It may pass immediately, since its job is to record reality. Note the observed result next to the checkbox.
  - **EVAL**: manual measurement. Record findings in this file.
  - **DECIDE**: needs the maintainer. Stop, present the options and the recommendation, and wait.
- Quarantine: a known failure is marked `@pytest.mark.xfail(strict=True, reason="plan X.Y")`. Removing that marker is the Red step of item X.Y. `strict=True` makes an unexpected pass fail the run.
- Commands (from item 0.6 on):
  - offline suite: `uv run pytest`
  - live suite: `uv run pytest -o addopts="" -m live`
  - lint: `uv run ruff check .`
- Done items become `- [x]`, with the date, short commit hash and any observed result.
- Work on a branch (e.g. `revive`), not `master`.
- Cassettes are frozen 2023 responses. They prove the parsing still works, not that Google still answers; only `live` tests tell you what works today. Don't re-record a cassette to make a test pass, because that rewrites the expected data.

## Baseline (2026-11-03)

### Per-method status

"Old stack" is Python 3.9 with pip-resolved dependencies. "pandas 3" is Python 3.13 with the latest dependencies and decompressed cassettes (see below).

| Public API | Live Google | Offline test | Defects → items |
|---|---|---|---|
| `TrendReq()` (NID cookie) | ⚠️ cookie URL `/trends/explore/?geo=US` returns **404** but still sets NID, so it works by accident | ❌ `test_initial_data` | D2, D3, D7, D9, D15 → 2.5–2.10 |
| `build_payload` | ✅ (`POST api/explore` 200) | ✅ | D6, D8 → 2.11, 2.12 |
| `interest_over_time` | ✅ | ✅ old stack / ❌ pandas 3 | D12 → 3.1, 3.4 |
| `multirange_interest_over_time` | ✅ | ✅ old / ❌ pandas 3 | D12 → 3.3 |
| `interest_by_region` | ⚠️ data returns, but `resolution` is ignored (a US `DMA` request returned states) | ✅ old, but the CITY test asserts the bug / ❌ pandas 3 | D1, D12 → 2.13, 3.2 |
| `related_queries` | ✅ (2 keywords) | ✅ | D10 → 2.14, 2.16 |
| `related_topics` | ⚠️ returned `{}` for 2 keywords (the known FIXME); 1 keyword not probed | ✅ (1 keyword) | D10, D14 → 1.9, 2.15, 2.16 |
| `suggestions` | ✅ | ✅ | none |
| `categories` | ✅ | none | → 2.17 |
| `trending_searches` | ❌ **404** | ✅ (2023 cassette) | D17 → Phase 4 |
| `today_searches` | ❌ **404** | none | D11, D17 → Phase 4 |
| `realtime_trending_searches` | ❌ **404** | ✅ (2023 cassette) | D17 → Phase 4 |
| `top_charts` | ❌ **404** | ✅ (2023 cassette) | D17 → Phase 4 |
| `get_historical_interest` | raises `NotImplementedError`; README still documents it | none | → 6.1 |
| `dailydata.get_daily_data` | not probed (slow) | none (0% coverage) | D13 → 3.5–3.7 |
| `retries` / `backoff_factor` | n/a | none | D4 → 2.4 |
| proxies | n/a | none | D7, D15 → 2.6, 2.7 |
| *Candidate:* Trending Now RSS `trends.google.com/trending/rss?geo=US` | ✅ 200 XML | none | → 4.3–4.5 |

The live results are a snapshot from one IP. Rate limiting (HTTP 429, the most-reported upstream problem) was not hit at this volume.

### Offline suite

| Stack | Result |
|---|---|
| Python 3.9.6, pip-resolved (pandas 2.3.3, urllib3 1.26.20, vcrpy 7.0.0) | 25 passed, 1 failed (`test_initial_data`), 2 pandas FutureWarnings; coverage 68% (`dailydata` 0%) |
| Python 3.13, latest (pandas 3.1.0, numpy 2.5.4, urllib3 2.8.0, requests 2.34.2, vcrpy 9.4.2, pytest 9.2.0) | **3 passed, 23 failed**: `JSONDecodeError`, because cassette bodies are stored gzip-compressed and aren't decoded on replay |
| Python 3.13, latest, cassette bodies decompressed (tried on a copy) | 16 passed, 10 failed: 1 expired cookie, 7 pandas 3 column-label dtype, 2 multirange `json_normalize` `TypeError` |

### Tooling and dependencies

- **Local Python:** this machine only has `/usr/bin/python3` 3.9.6, which reached EOL in Oct 2025. Current pandas, vcrpy, flake8 and numpy need Python ≥3.11 or ≥3.12. Python 3.10 reached EOL in Oct 2026; CPython 3.11–3.15 are available.
- **Declared dependencies:** `requirements.txt` declares only bare floors (`requests>=2.0`, `pandas>=0.25`), so fresh installs pull the newest major versions, which break the suite. `lxml` is declared but never imported. `urllib3` is imported (via `requests.packages`) but not declared.
- **Latest on PyPI (2026-11-03):**
  - requests 2.34.2
  - urllib3 2.8.0
  - pandas 3.1.0 (Python ≥3.11)
  - numpy 2.5.4 (Python ≥3.12)
  - pytest 9.2.0
  - pytest-recording 0.14.1
  - vcrpy 9.4.2 (Python ≥3.11)
  - responses 0.26.3
  - pytest-cov 7.1.0
  - flake8 7.5.0 (Python ≥3.11)
  - ruff 0.17.3
  - setuptools 84.2.1
- **`pyproject.toml`:**
  - `requires-python >=3.7`, with classifiers for 3.7–3.11.
  - `license = {text = ...}` is deprecated, and setuptools stops accepting it after **2027-02-18**.
  - `setuptools-scm` is a build requirement, but the version is static.
- **CI (`.github/workflows/python-package.yml`):**
  - Runs a Python 3.7–3.11 matrix on `actions/checkout@v2` and `actions/setup-python@v4`.
  - Neither repo has any run history left.
  - The blocking flake8 gate passes; 25 style warnings are non-blocking.

### Confirmed defects

All were reproduced on 2026-11-03, with the network mocked, unless they are noted as live, cassette-based or found by reading.

- **D1** `interest_by_region` ignores `resolution`. Since PR #533, `self.geo` is always a list, so `self.geo == ''` and `self.geo == 'US'` never match. The CITY cassette recorded a `COUNTRY` request, and a live `geo='US', resolution='DMA'` call returned states.
- **D2** `test_initial_data` is a time bomb. The cassette's NID cookie expired on 2023-09-25, so the cookie jar drops it on replay.
- **D3** The cookie URL returns 404, both in the 2023 cassettes and live today. The status code is never checked.
- **D4** `Retry(method_whitelist=…)` raises `TypeError` on urllib3 2.x, so any `TrendReq(retries>0 or backoff_factor>0)` crashes on its first request (upstream #591). On urllib3 1.26 it only emits a DeprecationWarning.
- **D5** Two `_get_data` bugs. Operator precedence treats a non-200 `text/javascript` response as a success, giving `JSONDecodeError`. A response without `Content-Type` raises `KeyError` (upstream #616).
- **D6** Sticky geo: `build_payload(geo='')` after `geo='US'` still queries the US (upstream #600).
- **D7** `GetGoogleCookie` swallows every exception when proxies are passed via `requests_args`, so a dead proxy causes an infinite loop (upstream #519, #634, #606).
- **D8** `build_payload(timeframe=[…], geo=[several])` raises `IndexError`.
- **D9** `TrendReq.__init__` pops `headers` out of the caller's `requests_args` dict.
- **D10** `related_queries` and `related_topics` raise `IndexError` when `rankedList` is empty, because only `KeyError` is caught (upstream #628). Result keys also drop compound keywords: `'blockchain + bitcoin'` becomes `'blockchain'` (per PR #527; not reproduced).
- **D11** `today_searches` passes `requests_args` twice, giving `TypeError` whenever `requests_args` is non-empty.
- **D12** pandas incompatibilities:
  - pandas 3 defaults string column labels to `StringDtype`, but `interest_over_time` and `interest_by_region` build their column labels as `object` dtype.
  - `pd.json_normalize` on a Series of lists raises `TypeError` (multirange).
  - pandas 2.2+ emits a `fillna` downcasting `FutureWarning` in `interest_over_time`.
- **D13** `dailydata.get_daily_data` problems:
  - On pandas 3, 57 of 59 rows get a `NaN` scale, because a chained `ffill(inplace=True)` is a no-op under copy-on-write. The output is silently wrong.
  - Found by reading: after exhausting its retries, `_fetch_data` still calls `interest_over_time()` on a stale payload.
  - Found by reading: it returns 5 columns while the docstring promises 4.
- **D14** `related_topics` with 2 keywords returned `{}` live (see the FIXME in `tests/test_request.py`); cause unknown.
- **D15** Proxy failover (found by reading; not reproduced). When the failing proxy is the last list entry, it is removed and `proxy_index` points past the end, raising `IndexError`. It also mutates the caller's list.
- **D16** The `lxml` dependency is unused.
- **D17** The `trending_searches`, `today_searches`, `realtime_trending_searches` and `top_charts` endpoints return 404.

### Open PRs and branches

Upstream is archived, so "adopt" means re-implementing the change here through the referenced item and crediting the author in the commit (`Co-authored-by:`).

| PR | Change | Verdict |
|---|---|---|
| #584, #626, #637 | `method_whitelist` → `allowed_methods`; #584 also imports `Retry` from urllib3 | Adopt via 2.4 (#584 is the most complete) |
| #519 | Stop swallowing cookie errors when proxies come via `requests_args` | Adopt via 2.6 (the diff targets 2022 code) |
| #634 | Print the swallowed exception | Superseded by 2.6 |
| #527 | Key related results by `keywordName` | Adopt via 2.16 |
| #458 | Regex instead of a fixed `trim_chars` | Adopt the idea via 5.3 (the diff targets 2021 code) |
| #629 | Fill every object column with `"Unknown"` and numerics with 0 | Reject: it changes the data. 3.4 fixes the warning |
| #627 | Wrap in the `future.no_silent_downcasting` option context | Reject: version-specific pandas option. 3.4 fixes it |
| #604 | Fenced code blocks in the README | Adopt in 6.1 |
| #621 | Add `articles` to realtime results | Close: the endpoint returns 404 (Phase 4) |
| #484 | Drop duplicate `requests_args` in `trending_searches` | Already on master; the same bug in `today_searches` is D11 |
| #386 | Tolerate a missing `geoCode` | Mostly superseded (master falls back to `coordinates`); backlog |
| #624 | Country-domain base URL, SOCKS proxies, unpinned deps, version bump, example with a local proxy | Reject as-is (mixed concerns); ideas → backlog |
| #430 | `get_monthly_interest` | Backlog (written against 2020 code; uses the removed `DataFrame.append`) |
| #414 | Keyword-less explore | Backlog (changes the return shape) |
| fork branch `origin/poetry` | `[tool.poetry]` + `poetry.lock` alongside the setuptools metadata, at v4.8.0 | Superseded by 0.6; delete in 6.4 |

## Plan

### Phase 0: Supported toolchain and a trustworthy green suite

- [x] **0.1 DECIDE** Support policy and tooling. Decided 2026-11-03: uv for environments; minimum Python 3.12 (CI on 3.12–3.15). Also approved: runtime floors `requests>=2.32.4`, `pandas>=2.2.2`, `urllib3>=1.26.5` declared directly (raised from `>=1.26` on 2026-11-03: 1.26.0–1.26.4 fail to import on Python 3.12, found by the lowest-direct job); drop `lxml`; ruff replaces flake8; next release is 5.0.0.
  - Recommended:
    - Python ≥3.12, with CI on 3.12–3.15.
    - Runtime dependencies `requests>=2.32.4`, `pandas>=2.2.2` (supporting both 2.x and 3.x) and `urllib3>=1.26`, declared directly.
    - Drop `lxml`.
    - uv for environments, with `uv.lock`.
    - ruff replaces flake8.
    - The next release is 5.0.0 (breaking).
  - Alternatives: keep pip with requirements files, or Poetry.
- [x] **0.2 TIDY** Local environment. Done 2026-11-03 with uv; observed 3 passed / 23 failed on Python 3.13.18, pandas 3.1.0, urllib3 2.8.0 (matches expected):
  1. Install uv (e.g. `brew install uv`).
  2. `uv python install 3.13`
  3. `uv venv --python 3.13`
  4. `uv pip install -r requirements.txt -r requirements-dev.txt -e .`
  5. `.venv/bin/pytest --block-network`

  Expect 3 passed / 23 failed (as of 2026-11-03; newer releases may shift this). Nothing to commit.
- [x] **0.3 TIDY** (done 2026-11-03; observed 16 passed / 10 failed, as expected) Decompress the cassette bodies with a one-off script (not shipped). For each interaction with `Content-Encoding: gzip`, store the decoded text body and remove `Content-Encoding` and `Content-Length`. Drop `binary` from `.gitattributes` so cassettes diff as text. Expect 16 passed / 10 failed.
- [x] **0.4 TIDY** (done 2026-11-03; observed 16 passed / 10 failed, unchanged) Add a `vcr_config` fixture in `tests/conftest.py` with `decode_compressed_response=True` and `filter_headers=["cookie"]`, so future recordings stay readable and carry no session cookie. Results unchanged.
- [x] **0.5 TIDY** (done 2026-11-03; observed 16 passed / 10 xfailed; pandas-3 markers made conditional on pandas ≥3 during 0.8) Quarantine the 10 failures with strict xfail. Expect 16 passed / 10 xfailed.
  - `test_initial_data` → 2.8
  - `test_interest_over_time_{ok,images,news,youtube,froogle}` → 3.1
  - `test_interest_by_region_ok` → 3.2
  - `test_interest_by_region_city_resolution` → 2.13
  - `test_multirange_interest_over_time_{ok,same_keyword_ok}` → 3.3
- [x] **0.6 TIDY** (done 2026-11-03; observed `uv run pytest` 16 passed / 10 xfailed, `uv build` clean, `uv.lock` created, `requirements*.txt` removed; nothing committed) Update `pyproject.toml` per 0.1.
  - Set `requires-python` and `dependencies`, and add `[dependency-groups] dev`.
  - Use the SPDX form `license = "Apache-2.0"` plus `license-files`, and update the classifiers.
  - Drop `setuptools-scm` and the `dynamic` block.
  - Delete `requirements*.txt` and commit `uv.lock`.

  Expect `uv run pytest` → 16 passed / 10 xfailed, and `uv build` with no deprecation warnings.
- [x] **0.7 TIDY** (done 2026-11-03; `uv run ruff check .` clean, tests unchanged at 16 passed / 10 xfailed, `NotImplementedError` text and realtime request params verified identical to HEAD; flake8 removed, ruff 0.17.3 added to dev group) Configure ruff, covering at least the rules CI enforced before, with line length 127 to match CI. Fix the existing warnings. The two bare `except:` clauses are behavioral, so leave them with `# noqa: E722` for 2.6 and Phase 4. `uv run ruff check .` must be clean.
- [x] **0.8 TIDY** (done 2026-11-03 locally; not yet run on GitHub) Rewrite CI:
  - uv-based workflow;
  - matrix 3.12–3.15 on locked dependencies;
  - a lowest-direct job on 3.12 using the minimum declared versions;
  - blocking lint;
  - `pytest --block-network`;
  - current major versions of the actions.

### Phase 1: Evaluation with live contract tests (what works today)

Each LIVE test calls the public API, asserts the documented shape, and records the result. Expected outcomes come from the 2026-11-03 probe.

- [ ] **1.1 TIDY** Live-test scaffolding:
  - Register a `live` marker, and make `addopts` add `-m "not live" --block-network`.
  - Create `tests/test_live.py` with `pytestmark = pytest.mark.live` and a fixture that sleeps ~2 s between tests.
  - Document the live command in CONTRIBUTING.
- [ ] **1.2 LIVE** `test_live_cookie_url_answers_200_with_nid`: the URL `GetGoogleCookie` requests returns 200 and sets NID. Expected: fails (404), so mark it strict xfail → 2.9.
- [ ] **1.3 LIVE** `test_live_build_payload_returns_widget_tokens`: TIMESERIES, GEO_MAP and RELATED_QUERIES widgets come back with tokens. Expected: pass.
- [ ] **1.4 LIVE** `test_live_interest_over_time_shape`: DatetimeIndex, one int column per keyword in 0–100, and a bool `isPartial`. Expected: pass.
- [ ] **1.5 LIVE** `test_live_interest_over_time_multiple_regions`: `geo=['US-NY','US-IL']` gives `(keyword, region)` MultiIndex columns. Expected: unknown.
- [ ] **1.6 LIVE** `test_live_multirange_interest_over_time_shape`: the average row comes first, with a date/value column pair per range. Expected: pass.
- [ ] **1.7 LIVE** `test_live_interest_by_region_resolution`: world/COUNTRY returns countries; `geo='US', resolution='DMA'` returns DMA names (e.g. `New York NY`). Expected: the DMA case fails (returns states), so mark it strict xfail → 2.13.
- [ ] **1.8 LIVE** `test_live_related_queries_shape`: results keyed by keyword, with `top`/`rising` frames holding `query` and `value`, or `None`. Expected: pass.
- [ ] **1.9 LIVE** `test_live_related_topics_single_keyword`: frames with `topic_title`, `topic_type` and `value`. Expected: unknown. Also try a 2-keyword comparison on trends.google.com. If the site shows related topics where pytrends returns `{}` (D14), add a TEST item to Phase 2; otherwise document the limitation.
- [ ] **1.10 LIVE** `test_live_suggestions_and_categories`: suggestions return a list of `{mid, title, type}`; categories return a dict with `children`. Expected: pass.
- [ ] **1.11 LIVE** `test_live_removed_endpoints`, parametrized over `trending_searches`, `today_searches`, `realtime_trending_searches` and `top_charts(2023)`. It documents the 404 as strict xfail(raises=ResponseError) and is reworked in 4.6.
- [ ] **1.12 LIVE** (slow) `test_live_daily_data_two_months`: `get_daily_data('pizza', 2024, 1, 2024, 2, wait_time=2)` has no NaN in the scaled column. Also record what granularity Google returns for the "monthly" request over a short range; weekly or daily data would undermine the scaling method.
- [ ] **1.13 EVAL** (optional) Rate limits: run sequential `build_payload` + `interest_over_time` calls at 0 s, 5 s and 30 s spacing. Stop at the first 429 or after 50 requests, and record the counts here. This informs the retry defaults and the README guidance.
- [ ] **1.14 EVAL** Data fidelity. The departing maintainer claims in upstream #636 that bot traffic gets altered data. For 3 fixed queries, compare `interest_over_time()` with the CSV exported from trends.google.com in a logged-out browser. Record the correlation and the maximum difference.
- [ ] **1.15 TIDY** Update the Baseline table above with the Phase 1 results, including the date and network type. This completes the inventory of what works and what doesn't.

### Phase 2: Core request path (offline TDD with `responses`)

- [ ] **2.1 TEST** (characterization; expected green) `test_429_json_response_raises_too_many_requests`. Pins the current `_get_data` behavior before it changes.
- [ ] **2.2 TEST** `test_non_200_javascript_response_raises_response_error`: a 500 with `text/javascript`. Red today: `JSONDecodeError` (D5).
- [ ] **2.3 TEST** `test_response_without_content_type_raises_response_error`: a 429 without `Content-Type` should raise `TooManyRequestsError`. Red today: `KeyError` (D5).
- [ ] **2.4 TEST** `test_retries_use_allowed_methods`: `TrendReq(retries=2, backoff_factor=0.1)` completes a request, and the session's `Retry` has `allowed_methods == {'GET', 'POST'}`. Red on urllib3 2.x: `TypeError` (D4). Import `Retry` from `urllib3`.
- [ ] **2.5 TEST** `test_init_does_not_mutate_requests_args`: the caller's dict still has `headers` after construction (D9).
- [ ] **2.6 TEST** `test_cookie_error_with_requests_args_proxy_propagates`: the first cookie request raises `ConnectionError` and a second would succeed; construction must raise. Red today: it doesn't raise (D7). Use a counting `side_effect` or two ordered `responses` registrations so the test can't hang.
- [ ] **2.7 TEST** `test_failing_last_proxy_is_skipped_without_index_error`: reproduce D15 first. If it doesn't reproduce, mark the item done as "not a defect".
- [ ] **2.8 TIDY** Rewrite `test_initial_data` with `responses`, using an NID cookie with no expiry. Delete its cassette and remove the xfail.
- [ ] **2.9 TEST** The cookie request goes to a URL that answers 200. The probe found `https://trends.google.com/` → 301 → 200 with NID; confirm with 1.2.
  - Red step: first change the mocked URL in `test_initial_data`.
  - In the same commit, rewrite the cookie-interaction `uri` in every cassette.
  - Remove the xfail from 1.2.
- [ ] **2.10 TEST** `test_non_2xx_cookie_response_raises`, so a future Google change fails loudly (D3).
- [ ] **2.11 TEST** `test_empty_geo_after_country_queries_worldwide`: `build_payload(geo='US')` then `build_payload(geo='')` gives a comparison item with `geo == ''` (D6).
- [ ] **2.12 TEST** `test_timeframe_list_length_mismatch_raises_value_error`: a clear message instead of `IndexError` (D8).
- [ ] **2.13 TEST** `test_interest_by_region_sends_requested_resolution`, parametrized over world/`CITY` and `US`/`DMA`; assert on the `req` that is sent. Red today: `COUNTRY` (D1). This replaces `test_interest_by_region_city_resolution` and its cassette. Remove the xfail from 1.7.
- [ ] **2.14 TEST** `test_related_queries_empty_ranked_list_returns_none`. Red today: `IndexError` (D10).
- [ ] **2.15 TEST** `test_related_topics_empty_ranked_list_returns_none`: the same for topics.
- [ ] **2.16 TEST** `test_related_results_keyed_by_full_keyword_name`, parametrized over both methods: a widget with `keywordName: 'blockchain + bitcoin'` produces that key (D10, PR #527).
- [ ] **2.17 TEST** (characterization) `test_categories_returns_parsed_tree`. This method has no coverage today.
- [ ] **2.18 TEST** (characterization) `test_interest_by_region_includes_geo_code_when_requested`.

### Phase 3: Dependency fallout (pandas 3, warnings)

- [ ] **3.1 TEST** Remove the xfail from the 5 `test_interest_over_time_*` tests. Red: column-label dtype. Build the result from a dict of columns so the labels match a normally constructed frame on both pandas 2 and 3 (D12).
- [ ] **3.2 TEST** The same for `test_interest_by_region_ok`.
- [ ] **3.3 TEST** Remove the xfail from both multirange tests. Red: `json_normalize` `TypeError`. Parse `columnData` without `json_normalize` (D12).
- [ ] **3.4 TEST** `test_interest_over_time_emits_no_warnings`. It is red only on the lowest supported pandas, so run it in a local copy of the 0.8 lowest-direct environment. Supersedes PRs #627 and #629.
- [ ] **3.5 TEST** `test_daily_data_scale_has_no_gaps`, using a fake `TrendReq` and a patched `sleep`. Red on pandas 3: NaN scale values (D13).
- [ ] **3.6 TEST** `test_fetch_data_raises_after_retries_exhausted`, instead of reading a stale payload (D13).
- [ ] **3.7 TEST** `test_daily_data_returns_documented_columns`. Decide whether to drop `isPartial` or document 5 columns.
- [ ] **3.8 TIDY** Set `filterwarnings = ["error"]` in the pytest config; both CI jobs must stay green.

### Phase 4: Removed endpoints

- [ ] **4.1 DECIDE** `trending_searches`, `today_searches`, `realtime_trending_searches` and `top_charts` all return 404.
  - Options:
    - (a) remove them;
    - (b) re-implement on the Trending Now RSS feed;
    - (c) make the legacy methods raise a clear error pointing to a new RSS-backed `trending_now(geo)`.
  - Recommended: (c) for the three trending methods, and (a) for `top_charts`, which has no known replacement.
  - Close PR #621.
- [ ] **4.2 TEST** `test_removed_endpoints_raise_clear_error_without_request`, parametrized. No network call is made, and the message names the replacement. This removes D11 and the remaining bare `except:`.
- [ ] **4.3 LIVE** `test_live_trending_rss_parses`: the feed is reachable, and its items carry a title, approximate traffic, a pub date and news items. Save a fixture to `tests/fixtures/`.
- [ ] **4.4 TEST** `test_trending_now_parses_feed_into_dataframe`, offline from the fixture. Use stdlib `xml.etree`; no lxml needed.
- [ ] **4.5 TEST** `test_trending_now_requests_given_geo`.
- [ ] **4.6 TIDY** Delete the obsolete cassettes and tests for removed endpoints, and update 1.11 to the new contract.

### Phase 5: Structural cleanup (behavior pinned by Phases 2–4)

- [ ] **5.1 TIDY** Extract the duplicated `req`/`token`/`tz` widget payload building into one helper.
- [ ] **5.2 TIDY** Extract the ranked-list parsing shared by `related_queries` and `related_topics`.
- [ ] **5.3 TEST** `test_get_data_strips_any_xssi_prefix`: bodies prefixed with `)]}'` or `)]}',`, with or without a newline, parse without `trim_chars` (the idea from PR #458). Then, as a TIDY step, remove the `trim_chars` arguments.
- [ ] **5.4 TEST** `test_diagnostics_use_logging_not_print`: `GetGoogleCookie`, `interest_by_region` and `dailydata` log via `logging.getLogger("pytrends")` (check with caplog).

### Phase 6: Docs, canary, release

- [ ] **6.1 TIDY** Update the README:
  - Python ≥3.11;
  - the removed endpoints and their replacements;
  - delete the `get_historical_interest` section;
  - caveats on rate limits and data fidelity from 1.13 and 1.14;
  - fenced code blocks (PR #604).
- [ ] **6.2 TIDY** Make `examples/example.py` use only working methods. Update CONTRIBUTING to cover uv, offline vs live tests and decoded cassettes, and fix the `pip -r install` typo.
- [ ] **6.3 TIDY** Add a weekly scheduled workflow that runs the live suite as a non-blocking canary. GitHub runner IPs may be throttled more than a residential IP.
- [ ] **6.4 DECIDE** Release 5.0.0 (changelog; PyPI via trusted publishing), and delete `origin/poetry`.

## Backlog (unscheduled)

- Configurable base URL / country domains, and SOCKS proxies via a `requests[socks]` extra (PR #624).
- Monthly interest by region (PR #430) and keyword-less explore (PR #414).
- `interest_by_region` responses that have neither `geoCode` nor `coordinates` (PR #386).
- One `requests.Session` per `TrendReq` instead of one per call.
- Google announced an official Google Trends API (alpha, limited access) in July 2025. If you can get access, evaluate it as a sturdier backend than scraping.
