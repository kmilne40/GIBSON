# RSS Security Review

RSS feed URLs are validated before fetching. Only HTTP and HTTPS are accepted. Localhost, loopback, private, link-local, multicast, reserved and unspecified IP targets are blocked for literal IPs. DNS resolution guardrails are available through `GIBSON_RSS_RESOLVE_GUARD=YES` but default off to keep offline classrooms responsive. Feed summaries are stripped and escaped before rendering.
