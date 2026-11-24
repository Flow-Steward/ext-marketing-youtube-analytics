# Changelog

## 0.1.0 — 2026-11-23

First release, built on the Discovery document of the YouTube Analytics API v2 (revision 20261122, SHA-256 `5fcf9ab54b98f007f21905b55e2a0aaa33ab6a545e6cbedd0780785ba21760e6`) and the report tables of YouTube's channel reports page (updated 2026-11-12), downloaded 2026-11-23.

- All 8 methods of the API are steps: reports, groups and group items.
- Everyday steps: Test connection, Get channel report, Get video report, Get top videos, Get all my groups, Create group and Add video to group.
- The report steps check the dimensions, metrics, filters, sort and number of rows against YouTube's report tables before sending, and refuse a combination YouTube does not support, with the reason.
- Connections are YouTube channels authorized through your own Google Cloud OAuth client; Flow Steward keeps and renews the authorization. Revenue metrics have their own connection type.
- Long reports can be saved as a JSON workflow file. Report numbers are exact decimals.
- Changes are sent once and never retried automatically; test runs never send them.
- An answer cut off before its end (fewer bytes than Content-Length, or a chunked answer that stops early) is never taken for a whole one: a read fails with `invalid_response`, a change YouTube confirmed returns without data and with a warning, a group creation says it was made but its id is not known. An empty answer where JSON is documented is `invalid_response`.
- An answer with `errors` set, even with HTTP 200, is a failure: a report or group read fails with `upstream_failure`; a group change has an unknown outcome (`timeout_unknown`).
- A list never returns more records than asked for: groups.list has no page size, so the page that crosses the maximum is cut and the next run starts from `next_page_token` and `skip` (`next_skip`).
- Get analytics groups takes exactly one of `id` or `mine` (true), checked before sending.
