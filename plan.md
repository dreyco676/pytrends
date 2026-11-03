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
- **D14** `related_topics` with 2 keywords returned `{}` live (see the FIXME in `tests/test_request.py`); cause not yet confirmed. Upstream #536 reports that for multi-keyword payloads the explore response contains no RELATED_TOPICS widgets, so `related_topics_widget_list` stays empty. 1.9 checks this live.
- **D15** Proxy failover (found by reading; not reproduced). When the failing proxy is the last list entry, it is removed and `proxy_index` points past the end, raising `IndexError`. It also mutates the caller's list.
- **D16** The `lxml` dependency is unused.
- **D17** The `trending_searches`, `today_searches`, `realtime_trending_searches` and `top_charts` endpoints return 404.
- **D18** `interest_by_region` sends `resolution` only for worldwide and for exactly `'US'` (found by reading; upstream #342, #417, #497, #571, #605). Any other single geo, such as `'GB'`, `'FR'` or `'US-CA'`, silently gets Google's default level.
- **D19** `build_payload` doesn't enforce Google's five-keyword limit, so a sixth keyword gets HTTP 400 from Google instead of a clear error (upstream #394, #456; not reproduced).
- **D20** Data methods called before `build_payload` fail unclearly: `interest_over_time`, `multirange_interest_over_time` and `interest_by_region` raise `KeyError: 'request'`, and `related_queries` and `related_topics` return `{}` (upstream #459).
- **D21** With proxies set, `_get_data` fetches the cookie again before every request: 4 cookie requests for 4 data requests, plus 1 at init (upstream #515).

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

### Upstream open issues

Reviewed 2026-11-03: all 136 open issues in `GeneralMills/pytrends`. Closed issues were not reviewed. Upstream is archived, so none can be answered or closed there.

| Upstream issues | Outcome |
|---|---|
| #342, #417, #497, #571, #605 | D18 → 7.1, 7.2 |
| #394, #456 | D19 → 7.3 |
| #459 | D20 → 7.4 |
| #515 | D21 → 7.5 |
| #569 | 7.6, then 7.7 re-records the hand-edited cassettes |
| #536 | Likely cause of D14; checked live in 1.9 |
| #588, #596, #601, #602, #609, #614, #618, #622, #625, #631 | Rate limits → 1.13 |
| #524, #534, #549, #551, #559, #576, #577, #587, #592, #607 | Data fidelity → 1.14 |
| #373, #377, #490, #543 | `tz` and timeframe docs → 6.1 |
| #390, #482, #514, #521 | `formattedValue`, `link` and "<1" → backlog |
| #562 | Type hints → backlog (its logging half was done in 5.4) |
| #471 | Explore link for a payload → backlog |
| #429, #457; #358, #451 | Monthly interest and keyword-less explore → existing backlog items (PR #430, #414) |
| #316 | Missing geo columns: fixed on branch `interest-by-region-geo-fallback` (`4c35a53`), not merged yet |
| #439, #600; #583, #591; #606; #608; #616; #628; #635; #487 | Already fixed: D6, D4, D7, Phase 0, D5, D10, Phase 4, D13 |
| #638 | February 2025 404s. The fix linked there targets Google's daily-trends endpoint, which Phase 4 replaced with the RSS feed |
| The rest | Not added: support questions; `get_historical_interest` reports (the method raises `NotImplementedError`); Selenium, headless-browser and reverse-engineering requests; JSON output (#398); jsonpath (#472); a time window for trending searches (#630; the feed has none); maintainer threads (#598, #615, #636) |

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

- [x] **1.1 TIDY** (done 2026-11-03 on branch `live-tests`; observed default run 16 passed / 10 xfailed, `-m live` collects 0 tests, lint clean) Live-test scaffolding:
  - Register a `live` marker, and make `addopts` add `-m "not live" --block-network`.
  - Create `tests/test_live.py` with `pytestmark = pytest.mark.live` and a fixture that sleeps ~2 s between tests.
  - Document the live command in CONTRIBUTING.
- [x] **1.2 LIVE** (done 2026-11-03 on branch `live-cookie-test`; observed `404 == 200` before quarantine, now strict xfail plan 2.9) `test_live_cookie_url_answers_200_with_nid`: the URL `GetGoogleCookie` requests returns 200 and sets NID. Expected: fails (404), so mark it strict xfail → 2.9.
- [ ] **1.3 LIVE** `test_live_build_payload_returns_widget_tokens`: TIMESERIES, GEO_MAP and RELATED_QUERIES widgets come back with tokens. Expected: pass.
- [ ] **1.4 LIVE** `test_live_interest_over_time_shape`: DatetimeIndex, one int column per keyword in 0–100, and a bool `isPartial`. Expected: pass.
- [ ] **1.5 LIVE** `test_live_interest_over_time_multiple_regions`: `geo=['US-NY','US-IL']` gives `(keyword, region)` MultiIndex columns. Expected: unknown.
- [ ] **1.6 LIVE** `test_live_multirange_interest_over_time_shape`: the average row comes first, with a date/value column pair per range. Expected: pass.
- [ ] **1.7 LIVE** `test_live_interest_by_region_resolution`: world/COUNTRY returns countries; `geo='US', resolution='DMA'` returns DMA names (e.g. `New York NY`). Expected: the DMA case fails (returns states), so mark it strict xfail → 2.13.
- [ ] **1.8 LIVE** `test_live_related_queries_shape`: results keyed by keyword, with `top`/`rising` frames holding `query` and `value`, or `None`. Expected: pass.
- [ ] **1.9 LIVE** `test_live_related_topics_single_keyword`: frames with `topic_title`, `topic_type` and `value`. Expected: unknown. Also try a 2-keyword comparison on trends.google.com. If the site shows related topics where pytrends returns `{}` (D14), add a TEST item to Phase 2; otherwise document the limitation.
- [ ] **1.10 LIVE** `test_live_suggestions_and_categories`: suggestions return a list of `{mid, title, type}`; categories return a dict with `children`. Expected: pass.
- [x] **1.11 LIVE** (done 2026-11-03; live run passes, not rate-limited, 3 of 3) `test_live_trending_rss_methods`, parametrized over `trending_searches`, `today_searches` and `realtime_trending_searches` with `pn='US'`. Each one returns at least one row from the live feed, with no 404. Replaces the removed-endpoint check (`top_charts` was removed in 4.7). Passed on the first run; it is a contract check, not a Red step.
- [ ] **1.12 LIVE** (slow) `test_live_daily_data_two_months`: `get_daily_data('pizza', 2024, 1, 2024, 2, wait_time=2)` has no NaN in the scaled column. Also record what granularity Google returns for the "monthly" request over a short range; weekly or daily data would undermine the scaling method.
- [ ] **1.13 EVAL** (optional) Rate limits: run sequential `build_payload` + `interest_over_time` calls at 0 s, 5 s and 30 s spacing. Stop at the first 429 or after 50 requests, and record the counts here. This informs the retry defaults and the README guidance.
  - From the upstream triage: also time `related_queries`, which users report hitting 429 sooner than `interest_over_time` (#588, #625). Upstream 429 reports: #588, #596, #601, #602, #609, #614, #618, #622, #625, #631.
- [ ] **1.14 EVAL** Data fidelity. The departing maintainer claims in upstream #636 that bot traffic gets altered data. For 3 fixed queries, compare `interest_over_time()` with the CSV exported from trends.google.com in a logged-out browser. Record the correlation and the maximum difference.
  - From the upstream triage: also record the `userConfig.userType` in the widget requests. Upstream #534 and #551 report `USER_TYPE_SCRAPER` for pytrends and `USER_TYPE_LEGIT_USER` for the browser, and link the scraper tag to zeroed "holes" in the data. The string `USER_TYPE_SCRAPER` appears 124 times in the 2023 cassettes, and `USER_TYPE_LEGIT_USER` never does. Related upstream reports: #524, #549, #559, #576, #577, #587, #592, #607.
- [ ] **1.15 TIDY** Update the Baseline table above with the Phase 1 results, including the date and network type. This completes the inventory of what works and what doesn't.

### Phase 2: Core request path (offline TDD with `responses`)

- [x] **2.1 TEST** (done 2026-11-03 on branch `phase2-offline`; characterization, passed on first run) `test_429_json_response_raises_too_many_requests`. Pins the current `_get_data` behavior before it changes.
- [x] **2.2 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `JSONDecodeError` at request.py:157; Green: grouped the content-type checks under `status_code == 200`) `test_non_200_javascript_response_raises_response_error`: a 500 with `text/javascript`. Red today: `JSONDecodeError` (D5).
- [x] **2.3 TEST** (done 2026-11-03 on branch `phase2-offline`; Red confirmed against pre-2.2 code: `KeyError: 'content-type'`; it passes now because the 2.2 change checks `Content-Type` only for 200 responses, so the 429 never reads the header) `test_response_without_content_type_raises_response_error`: a 429 without `Content-Type` should raise `TooManyRequestsError`. Red today: `KeyError` (D5).
- [x] **2.4 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `TypeError` on `method_whitelist` at request.py:125 with urllib3 2.8; Green: `allowed_methods`, and `Retry` now imported from `urllib3.util.retry`; passes on urllib3 1.26.5 and 2.8) `test_retries_use_allowed_methods`: `TrendReq(retries=2, backoff_factor=0.1)` completes a request, and the session's `Retry` has `allowed_methods == {'GET', 'POST'}`. Red on urllib3 2.x: `TypeError` (D4). Import `Retry` from `urllib3`.
- [x] **2.5 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: caller's dict lost `headers`; Green: `TrendReq` copies `requests_args` before popping) `test_init_does_not_mutate_requests_args`: the caller's dict still has `headers` after construction (D9).
- [x] **2.6 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: "DID NOT RAISE"; Green: removed the bare `except` from the `requests_args` proxy branch of `GetGoogleCookie`, which also removes one of the two `noqa: E722` clauses) `test_cookie_error_with_requests_args_proxy_propagates`: the first cookie request raises `ConnectionError` and a second would succeed; construction must raise. Red today: it doesn't raise (D7). Use a counting `side_effect` or two ordered `responses` registrations so the test can't hang.
- [x] **2.7 TEST** (done 2026-11-03 on branch `phase2-offline`; D15 reproduced: `IndexError` at request.py:83; Green: reset `proxy_index` to 0 when the removed proxy was last. Still open: the caller's proxy list is mutated, which needs its own test, not covered here) `test_failing_last_proxy_is_skipped_without_index_error`: reproduce D15 first. If it doesn't reproduce, mark the item done as "not a defect".
- [x] **2.8 TIDY** (done 2026-11-03 on branch `phase2-offline`; cassette deleted, xfail removed, test now passes on both stacks) Rewrite `test_initial_data` with `responses`, using an NID cookie with no expiry. Delete its cassette and remove the xfail.
- [x] **2.9 TEST** (done 2026-11-03 on branch `phase2-offline`; cookie request now goes to `{BASE_TRENDS_URL}/?geo=US`, which answers 200 directly with NID; 1.2 xfail removed and passing live; the 24 cassette cookie URIs were rewritten, but their recorded status is still 404, which must be resolved before 2.10 makes non-2xx responses raise) The cookie request goes to a URL that answers 200. The probe found `https://trends.google.com/` → 301 → 200 with NID; confirm with 1.2.
  - Red step: first change the mocked URL in `test_initial_data`.
  - In the same commit, rewrite the cookie-interaction `uri` in every cassette.
  - Remove the xfail from 1.2.
- [x] **2.10 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: "DID NOT RAISE"; Green: `GetGoogleCookie` checks the status through a `_nid_cookie` helper in both branches. Cassettes: the recorded status of the cookie interaction was changed from 404 to 200 in all 24 cassettes (hand-edited, not re-recorded; the URI was already changed in 2.9). Re-record these cassettes once the rate limit clears) `test_non_2xx_cookie_response_raises`, so a future Google change fails loudly (D3).
- [x] **2.11 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `['US'] == ['']`; Green: `build_payload` defaults `geo=None`, falls back to the constructor's geo (now stored as `default_geo`) only when omitted, so `geo=''` means worldwide) `test_empty_geo_after_country_queries_worldwide`: `build_payload(geo='US')` then `build_payload(geo='')` gives a comparison item with `geo == ''` (D6).
- [x] **2.12 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `IndexError`; Green: a length check raises `ValueError` naming the expected and actual counts) `test_timeframe_list_length_mismatch_raises_value_error`: a clear message instead of `IndexError` (D8).
- [x] **2.13 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `COUNTRY` sent for both cases; Green: `interest_by_region` compares the list form of geo (`[""]`, `["US"]`); deleted `test_interest_by_region_city_resolution` and its cassette. Open: the 1.7 live test (stashed on `live-build-payload`) still has its xfail and must have it removed when that work is restored) `test_interest_by_region_sends_requested_resolution`, parametrized over world/`CITY` and `US`/`DMA`; assert on the `req` that is sent. Red today: `COUNTRY` (D1). This replaces `test_interest_by_region_city_resolution` and its cassette. Remove the xfail from 1.7.
- [x] **2.14 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `IndexError`; Green: `related_queries` catches `(KeyError, IndexError)` for top and rising) `test_related_queries_empty_ranked_list_returns_none`. Red today: `IndexError` (D10).
- [x] **2.15 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `IndexError`; Green: `related_topics` catches `(KeyError, IndexError)` for top and rising) `test_related_topics_empty_ranked_list_returns_none`: the same for topics.
- [x] **2.16 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `['blockchain']`; Green: both methods key by the widget's `keywordName`; the 2.14 and 2.15 widget fixtures gained a `keywordName` as real responses have) `test_related_results_keyed_by_full_keyword_name`, parametrized over both methods: a widget with `keywordName: 'blockchain + bitcoin'` produces that key (D10, PR #527).
- [x] **2.17 TEST** (done 2026-11-03 on branch `phase2-offline`; characterization, passed on first run) `test_categories_returns_parsed_tree`. This method has no coverage today.
- [x] **2.18 TEST** (done 2026-11-03 on branch `phase2-offline`; characterization, passed on first run) `test_interest_by_region_includes_geo_code_when_requested`.

### Phase 3: Dependency fallout (pandas 3, warnings)

- [x] **3.1 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `object` vs `StringDtype` column labels on pandas 3; Green: single-region labels rebuilt with `pd.Index(list(...))`; the 5 tests pass on pandas 3 and 2.2.2) Remove the xfail from the 5 `test_interest_over_time_*` tests. Red: column-label dtype. Build the result from a dict of columns so the labels match a normally constructed frame on both pandas 2 and 3 (D12).
- [x] **3.2 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: same `object` vs `StringDtype` labels; Green: `interest_by_region` rebuilds its labels the same way; passes on pandas 3 and 2.2.2) The same for `test_interest_by_region_ok`.
- [x] **3.3 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: `TypeError` from `json_normalize` on a Series of lists, then `object` vs `StringDtype` labels; Green: frame built from `df['columnData'].tolist()` and labels normalized; passes on pandas 3 and 2.2.2. The offline `test_request.py` suite now has no xfails on pandas 3.)  Remove the xfail from both multirange tests. Red: `json_normalize` `TypeError`. Parse `columnData` without `json_normalize` (D12).
- [x] **3.4 TEST** (done 2026-11-03 on branch `phase2-offline`; Red on pandas 2.2.2: FutureWarning from `fillna` on the whole frame; the test passes on pandas 3 already, so the Red was confirmed only on the lowest-direct stack; Green: only `isPartial` is mapped to bool, with missing values as False; the 44 offline tests pass on both stacks with FutureWarning as an error) It is red only on the lowest supported pandas, so run it in a local copy of the 0.8 lowest-direct environment. Supersedes PRs #627 and #629.
- [x] **3.5 TEST** (done 2026-11-03 on branch `phase2-offline`; Red on pandas 3: 58 of 59 scale values NaN; Green: `ffill` assigned back instead of in place. Note for 3.8: `dailydata.py` still uses `join(lsuffix=..., rsuffix=...)`, which raises a `Pandas4Warning`, so it must move to `suffixes=` before warnings can be errors) `test_daily_data_scale_has_no_gaps`, using a fake `TrendReq` and a patched `sleep`. Red on pandas 3: NaN scale values (D13).
- [x] **3.6 TEST** (done 2026-11-03 on branch `phase2-offline`; Red: "DID NOT RAISE"; Green: `_fetch_data` re-raises the last `ResponseError` instead of breaking out and reading stale data) `test_fetch_data_raises_after_retries_exhausted`, instead of reading a stale payload (D13).
- [x] **3.7 TEST** (done 2026-11-03 on branch `phase2-offline`; decision: keep `isPartial` and document 5 columns, since dropping it would change the output; the docstring now says 5 and describes `isPartial`) `test_daily_data_returns_documented_columns`. Decide whether to drop `isPartial` or document 5 columns.
- [x] **3.8 TIDY** (done 2026-11-03 on branch `phase2-offline`; the one remaining warning was `join(lsuffix=, rsuffix=)` in `dailydata.py`, now a `pd.merge` with `suffixes=`; `filterwarnings = ["error"]` set; 47 offline tests pass on pandas 3 and 2.2.2; coverage 92%) Set `filterwarnings = ["error"]` in the pytest config; both CI jobs must stay green.

### Phase 4: Removed endpoints

- [x] **4.1 DECIDE** (decided 2026-11-03) `trending_searches`, `today_searches`, `realtime_trending_searches` and `top_charts` all return 404.
  - Decisions:
    - Re-implement `trending_searches`, `today_searches` and `realtime_trending_searches` on the Trending Now RSS feed (`trends.google.com/trending/rss?geo=XX`), keeping their names.
    - Their `pn`/`geo` argument accepts 2-letter country codes only. Legacy names such as `'united_states'` raise a clear error. This is breaking and belongs in 5.0.0.
    - Remove `top_charts`, which has no replacement.
  - Open: the RSS items have no `entityNames`, so `realtime_trending_searches` loses that column. Decide its new columns while doing 4.5.
  - Close PR #621 (realtime articles) when this is merged.
- [x] **4.2 LIVE** (done 2026-11-03; live test passes, not rate-limited: 200 `text/xml`, 10 items each with title, approx traffic, pubDate and news items) `test_live_trending_rss_parses`: the RSS feed for `geo=US` answers 200 XML, and its items carry a title, approximate traffic, a pub date and news items. Saved the response as `tests/fixtures/trending_rss_US.xml`.
- [x] **4.3 TEST** (done 2026-11-03; Red was an ImportError for `parse_trending_rss`, Green with 48 passed) `test_trending_rss_items_parse_into_dataframe`, offline from the fixture. Use stdlib `xml.etree`; no lxml needed. The parser is `pytrends.request.parse_trending_rss(content)`, with columns `title`, `approx_traffic`, `pub_date`.
- [x] **4.4 TEST** (done 2026-11-03; Red: the old endpoint call and the unmocked feed request; Green with 48 passed) `test_trending_searches_requests_rss_for_country_code`: `trending_searches(pn='US')` requests the feed with `geo=US` and returns the item titles, using a mocked response. Red today: the old endpoint returns 404.
  - Returns a Series of titles. Session headers (`self.headers`, where `requests_args['headers']` ends up) are sent with the feed request.
  - Also done here: deleted `test_trending_searches_ok` and its cassette (it pinned the 404 endpoint); `test_request_args_passing` now mocks the feed.
  - Not yet covered: a non-200 feed response currently surfaces as a parse error, not a `ResponseError`.
- [x] **4.5 TEST** (done 2026-11-03; Red: `today_searches` still hit the old endpoint; Green with 48 passed) `test_today_searches_and_realtime_use_rss`: both methods use the same feed. `realtime_trending_searches` returns the columns decided above. Because `today_searches` is rewritten, D11 (the duplicate `requests_args`) goes away with it.
  - Decided: `realtime_trending_searches` returns `title`, `approx_traffic`, `pub_date` and `articles` (a list of `{title, url, source}` dicts from the news items; the old `entityNames` column is gone). `cat` and `count` are accepted but ignored, since the feed has no equivalent; removing them waits for 5.0.0.
  - `today_searches` returns the same title Series as `trending_searches`. Both go through one `_trending_feed(pn)` helper.
  - Also done here: deleted `test_realtime_trending_searches_ok` and its cassette (it pinned the old endpoint). `test_trending_rss_items_parse_into_dataframe` now expects the `articles` column.
- [x] **4.6 TEST** (done 2026-11-03; Red: the request went out with `geo=united_states`; Green with 51 passed) `test_legacy_country_names_raise_value_error`: `trending_searches(pn='united_states')` raises `ValueError` that names the expected code format, without a network call.
  - The check sits in the shared `_trending_feed(pn)` helper, so `today_searches` and `realtime_trending_searches` get it too. The test is parametrized over all three.
  - The check accepts any two letters (`str.isalpha`, so not only `[A-Z]`) and passes them through unchanged. It doesn't check that the code is a real country.
- [x] **4.7 TIDY** (done 2026-11-03; offline suite 50 passed, 2 deselected, `ruff check` clean) Remove `top_charts` and its test and cassette. Also removed its `TOP_CHARTS_URL` constant, its example in `examples/example.py`, and its README section, table-of-contents entry and feature-list entry. Delete the cassettes and tests for the old trending endpoints (both `test_trending_searches_ok` and `test_realtime_trending_searches_ok` were already removed in 4.4 and 4.5). Update 1.11 to a live check of the RSS methods.

### Phase 5: Structural cleanup (behavior pinned by Phases 2–4)

- [x] **5.1 TIDY** (done 2026-11-03; structural, suite unchanged at 55 passed, `ruff check` clean) Extract the duplicated `req`/`token`/`tz` widget payload building into one helper.
  - `_widget_params(widget)` replaces the five copies in `interest_over_time`, `multirange_interest_over_time`, `interest_by_region`, `related_topics` and `related_queries`. `build_payload`'s own `req` handling is a different shape and is left as it is.
- [x] **5.2 TIDY** (done 2026-11-03; structural, suite unchanged at 55 passed, `ruff check` clean) Extract the ranked-list parsing shared by `related_queries` and `related_topics`.
  - `_parse_ranked_list(req_json, index, make_frame)` returns the top (index 0) or rising (index 1) list, or `None` on `KeyError`/`IndexError`. The `try` covers the frame build too, as before. `_topic_frame` and `_query_frame` are the two per-method frame builders.
- [x] **5.3 TEST** (done 2026-11-03; Red: 4 `JSONDecodeError`s, one per prefix form; Green with 54 passed; then TIDY removed the `trim_chars` parameter and its 7 call-site arguments, still 54 passed) `test_get_data_strips_any_xssi_prefix`: bodies prefixed with `)]}'` or `)]}',`, with or without a newline, parse without `trim_chars` (the idea from PR #458). Then, as a TIDY step, remove the `trim_chars` arguments.
  - `_get_data` strips the prefix with `XSSI_PREFIX = re.compile(r"^\)\]\}',?\n?")`. The live cassettes still replay.
- [x] **5.4 TEST** (done 2026-11-03; Red: proxy message printed to stdout, then the dailydata retry messages; Green with 55 passed) `test_diagnostics_use_logging_not_print`: `GetGoogleCookie`, `interest_by_region` and `dailydata` log via `logging.getLogger("pytrends")` (check with caplog).
  - Covered by the test: the two `GetGoogleCookie` proxy messages (`logger.warning`), and the `dailydata` retry messages (`warning`), abort (`error`), and verbose progress (`info`). Asserts nothing reaches stdout.
  - `interest_by_region` had no reachable `print`. Its `Could not find geo_code column` branch was dead: the code selects `geo_column` before the check, so the column always exists. I removed the branch rather than converting it, so there is nothing to log there. This departs from the plan's wording.
  - Behavior change: verbose progress in `get_daily_data` no longer prints. It logs at `info`, which only shows if the application configures logging. Warnings still reach stderr through Python's default handler.

### Phase 6: Docs, canary, release

- [ ] **6.1 TIDY** Update the README (partly done 2026-11-03: the items marked done below are finished; the caveats wait for 1.13 and 1.14, and the `tz` and timeframe notes came from the upstream triage, so the item stays open):
  - [x] Python 3.12 (the 0.1 decision; the original text said ≥3.11, which contradicted it), and the dependency list with lxml removed;
  - [x] the removed endpoints and their replacements, in a new "Removed endpoints" section; trending and realtime documented for the RSS feed, with the new return shapes;
  - [x] `get_historical_interest` section deleted, with its table-of-contents and method-list entries;
  - [ ] caveats on rate limits and data fidelity from 1.13 and 1.14. A rate-limit note from our own runs is in place; the fidelity caveat is not written yet;
  - [ ] document that the `interest_over_time` index is UTC, built from Google's epoch timestamps, and check live whether `tz` shifts the day boundaries (upstream #377, #490); state that the only year-based timeframes are `'today 5-y'` and `'all'` (#373, #543);
  - [x] fenced code blocks (PR #604) for every indented example; the multirange example's extra parenthesis is fixed.
  - Install instructions now show `pip install git+https://github.com/dreyco676/pytrends.git` until 5.0.0 is released.
- [x] **6.2 TIDY** (done 2026-11-03; docs only, suite unchanged at 55 passed, `ruff check` clean) Make `examples/example.py` use only working methods. Update CONTRIBUTING to cover uv, offline vs live tests and decoded cassettes, and fix the `pip -r install` typo.
  - `examples/example.py` needed no change: it calls only methods that still exist and are covered offline, and `top_charts` was removed in 4.7. It compiles. A live run is blocked by the explore rate limit, so it has not been run end to end.
  - CONTRIBUTING: the setup section now uses `uv sync --locked` (the `pip -r` typo is gone with the requirements files), commands use `uv run`, and new sections cover running the suite offline, linting, and the cassette format (decoded bodies, filtered cookie, vendored in `.gitattributes`).
- [ ] **6.3 TIDY** Add a weekly scheduled workflow that runs the live suite as a non-blocking canary. GitHub runner IPs may be throttled more than a residential IP.
  - Skipped 2026-11-03: GitHub Actions is off for this account (no billing), so no workflow is added. Revisit if Actions is enabled.
- [ ] **6.4 DECIDE** Release 5.0.0 (changelog; PyPI via trusted publishing), and delete `origin/poetry`.
  - Prepared 2026-11-03, not published: `pyproject.toml` and `uv.lock` set to 5.0.0; `CHANGELOG.md` written (breaking changes, fixes, known limits). Suite 55 passed, lint clean.
  - Open, needs the maintainer's go-ahead: publishing to PyPI (trusted publishing is not set up here), and deleting `origin/poetry` (a remote branch, so it cannot be undone from here).

### Phase 7: Upstream issue triage

Added 2026-11-03 from the review of upstream's open issues (see "Upstream open issues" above). 7.1 and 7.3 to 7.6 run offline. 7.2 and 7.7 need the explore API, which answered 429 on 2026-11-03.

- [ ] **7.1 TEST** `test_interest_by_region_sends_resolution_for_any_single_geo`, parametrized over `geo='GB'` with `CITY`, `geo='FR'` with `DMA` and `geo='US-CA'` with `CITY`: the GEO_MAP widget request carries the requested resolution (D18). Red today: only worldwide and exactly `'US'` send it, so these silently return the default level.
  - Proposed: send the requested resolution for any single geo, and let Google's answer for an unsupported combination surface as usual. Alternative: keep the current rule and log a warning when the resolution is ignored. Confirm the choice when starting the item.
- [ ] **7.2 LIVE** `test_live_interest_by_region_resolution_outside_us`: `geo='GB'` with `CITY` and `geo='US-CA'` with `CITY` return finer areas than the default level. Expected: unknown; upstream #497 says the site lists about 200 UK cities. Record which combinations Google rejects, and document them in the README.
- [x] **7.3 TEST** (done 2026-11-03 on branch `build-payload-keyword-limit`, uncommitted; Red: `DID NOT RAISE ValueError`; Green with 58 passed on pandas 3 and on the lowest-direct stack; `ruff check` clean) `test_build_payload_rejects_more_than_five_keywords`: six keywords raise `ValueError` naming the five-keyword limit, before any request (D19). Red today: the request goes out and Google answers HTTP 400.
  - `build_payload` raises `ValueError` ('at most five keywords per request') when `kw_list` has more than five entries, before it sets any state or sends a request.
  - Still unverified: whether Google's cap also counts keyword-and-region pairs. The check counts keywords only. Check with one live request when the rate limit allows, and extend the validation if it does.
- [ ] **7.4 TEST** `test_data_methods_before_build_payload_raise_clear_error`, parametrized over `interest_over_time`, `multirange_interest_over_time`, `interest_by_region`, `related_queries` and `related_topics`: each raises an error that says to call `build_payload()` first, without sending a request (D20). Red today: the first three raise `KeyError: 'request'`, and the related methods return `{}`.
- [x] **7.5 TEST** (done 2026-11-03, PR #11; Red: `assert 5 <= 2`, one cookie request per data request; Green with 58 passed on pandas 3 and on the lowest-direct stack; `ruff check` clean) `test_proxied_requests_fetch_one_cookie_per_proxy`: with two proxies, the init plus four data requests fetch the cookie at most once per proxy (D21). Red today: one cookie request per data request. This overlaps the backlog item "one `requests.Session` per `TrendReq`"; do them together if that item is scheduled.
  - Done with a per-proxy cookie cache, `_proxy_cookies()`, which `__init__` and `_get_data` both use. The one-session part of the backlog item is still open.
  - Trade-off: a cookie now lasts as long as its `TrendReq` instance. Before, each request fetched a fresh one. A long-running instance could hold an expired NID cookie (D2 shows NID cookies do expire). Revisit this if a long-running job starts failing.
  - Edge case: if a proxy fails inside `GetGoogleCookie`, the cookie from the next proxy is cached under the removed proxy. The next request for the next proxy fetches again. This costs an extra request but gives no wrong cookie.
- [x] **7.6 TIDY** (done 2026-11-03, merged as PR #10; structural, suite identical at 57 passed on pandas 3 and on the lowest-direct stack; `ruff check` clean) Make the cassette tests assert structure instead of hard-coded values (upstream #569): columns, index type and range, dtypes, and values within 0–100. Derive any exact values from the cassette's own response body. Re-recording a cassette then no longer rewrites expected data. Suite results must be identical before and after.
  - Done: `recorded_responses(test, uri_fragment)` reads the JSON bodies from the cassette. The 15 cassette tests whose expected values were typed in now derive them from those bodies: the interest-over-time family (`ok`, `images`, `news`, `youtube`, `froogle`, `partial`) with `assert_interest_over_time_matches_recording`, the two multirange tests, `interest_by_region_ok`, the four related-search tests, `suggestions_ok` and `test_tokens`. The helpers check the structure first: datetime index in order, one int column per keyword in 0–100, bool `isPartial`, the timeframe range where one is given, and the multirange average row first.
  - Removed `ExpectedResult` and `build_interest_over_time_df`, which had no users left.
  - Checked by mutation: inverting the `isPartial` flags where a point carries the key fails only `test_interest_over_time_partial`, because the other cassettes have no per-point flag. Inverting the default `False` used for a missing flag fails the five cassette tests that have none. Making `_tokens` select topic widgets fails `test_tokens`. Reversing the region values across keywords fails `test_interest_by_region_ok`. The source was restored after each run.
  - Not covered by the helpers: dtypes are only checked through `assert_frame_equal` against the derived frame, not separately.
  - `test_request.py` imports `yaml`, which comes in through vcrpy's dependency on PyYAML. It isn't declared directly.
- [ ] **7.7 LIVE** Re-record the 24 cassettes whose cookie status was hand-edited in 2.10, once the explore API stops answering 429. Expected: the whole offline suite still passes, which 7.6 makes possible without editing expected values.

## Backlog (unscheduled)

- Configurable base URL / country domains, and SOCKS proxies via a `requests[socks]` extra (PR #624).
- Monthly interest by region (PR #430) and keyword-less explore (PR #414).
- [x] `interest_by_region` responses that have neither `geoCode` nor `coordinates` (PR #386). Done 2026-11-03 on branch `interest-by-region-geo-fallback`, uncommitted: values are returned without the geo column, and `inc_geo_code=True` logs `Could not find geo_code column; Skipping` on the `pytrends` logger. Two Red tests (`KeyError: ['coordinates'] not in index`, then no warning); suite 57 passed on pandas 3 and on the lowest-direct stack.
- One `requests.Session` per `TrendReq` instead of one per call.
- Google announced an official Google Trends API (alpha, limited access) in July 2025. If you can get access, evaluate it as a sturdier backend than scraping.
- `related_queries` keeps only `query` and `value`. It drops Google's `formattedValue` (such as "Breakout" or "+250%") and `link`, which `related_topics` already keeps (upstream #390, #482, #521). Similarly, `interest_over_time` reports the site's "<1" as 0 (#514). Adding columns changes the return shape, so it needs a decision.
- Type hints and a `py.typed` marker (upstream #562).
- A method that returns the trends.google.com explore link for the current payload (upstream #471).
