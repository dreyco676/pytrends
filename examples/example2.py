from pytrends.request import TrendReq
country_codes = [
    'cy', 'pe', 'hk', 'co', 'mx', 'br', 'ua', 'ng', 'ph', 'au',
    'tr', 'vn', 'tw', 'ar', 'gi', 'my', 'gh', 'ec', 'na', 'sb',
    'ni', 'gt', 'pr', 'sg', 'bh', 'nf', 'pl', 'bo', 'ag', 'om',
    'sa', 'bn', 'lb', 'pk', 'py', 'qa', 'ru', 'pa', 'cu', 'np',
    'sl', 'do', 'sv', 'mt', 'eg', 'kw', 'et', 'ly', 'fj', 'jm',
    'kh', 'uy', 'bd', 'mm', 'vc', 'af', 'tj', 'ai', 'bz', 'pg',
    'by', 'iq', 'tn', 'ge', 'kz', 'gr', 'jo', 'nr', 've', 'lv',
    'pt', 'dz', 'ht', 'gy', 'bi', 'ps', 'gp', 'am',''
]
# Only need to run this once, the rest of requests will use the same session.
country_codes = [
    'vn', 'py', 'sv', 'eg', 'et', 'ly', 'fj', 'jm', 'uy', 'vc',
    'af', 'tj', 'bz', 'pg', 'tn', 'gr'
]
for c in country_codes:

    # print('try',c)
    try:
        pytrend = TrendReq(base_url=c
        ,proxies=['socks5h://127.0.0.1:1080']
        )
        pytrend.build_payload(kw_list=['ai'])

        interest_over_time_df = pytrend.interest_over_time()
        # print(interest_over_time_df.head())
        print(c)
    except :
        # print('failed',c)
        pass

# # Create payload and capture API tokens. Only needed for interest_over_time(), interest_by_region() & related_queries()
# pytrend.build_payload(kw_list=['pizza', 'bagel'])

# # Interest Over Time
interest_over_time_df = pytrend.interest_over_time()
print(interest_over_time_df.head())

# # Interest by Region
# interest_by_region_df = pytrend.interest_by_region()
# print(interest_by_region_df.head())

# # Related Queries, returns a dictionary of dataframes
# related_queries_dict = pytrend.related_queries()
# print(related_queries_dict)

# # Get Google Hot Trends data
# trending_searches_df = pytrend.trending_searches()
# print(trending_searches_df.head())

# # Get Google Hot Trends data
# today_searches_df = pytrend.today_searches()
# print(today_searches_df.head())

# # Get Google Top Charts
# top_charts_df = pytrend.top_charts(2018, hl='en-US', tz=300, geo='GLOBAL')
# print(top_charts_df.head())

# # Get Google Keyword Suggestions
# suggestions_dict = pytrend.suggestions(keyword='pizza')
# print(suggestions_dict)

# # Get Google Realtime Search Trends
# realtime_searches = pytrend.realtime_trending_searches(pn='IN')
# print(realtime_searches.head())

# # Recreate payload with multiple timeframes
# pytrend.build_payload(kw_list=['pizza', 'bagel'], timeframe=['2022-09-04 2022-09-10', '2022-09-18 2022-09-24'])

# # Multirange Interest Over Time
# multirange_interest_over_time_df = pytrend.multirange_interest_over_time()
# print(multirange_interest_over_time_df.head())