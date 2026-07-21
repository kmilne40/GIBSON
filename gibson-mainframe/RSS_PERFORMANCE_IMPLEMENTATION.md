# RSS Performance Implementation

The previous RSS flow could block a web request while every feed was fetched sequentially. The new model is cache-first: `/cti/rss` renders cached data immediately, while refresh actions create tracked refresh jobs. Live refresh is optional and can be enabled through `GIBSON_RSS_LIVE_FETCH=YES` or the live refresh link. The implementation supports single-feed refresh, bounded parallel fetch execution, safer timeout values and visible feed health.
