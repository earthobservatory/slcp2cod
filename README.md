HOW does the COD-network selector work?

1. Gather pre-event SLCPs + co-event SLCPs
    1. pairs are pre-event if pre_end < eventtime
    1. pairs are co-event if event_time is between co_start and co_end
2. Match pairs if:
    1. pre-event[‘end’] - co-event[‘end’] < 1day
    1. area_intersect(pre-event,co-event) /area_co-event> min_overlap
3. Returns minmatch valid pairs for COD based on shortest temporal baseline
    1. baseline = pre_start to  co_end
