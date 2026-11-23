# YouTube Analytics integration for Flow Steward

<img src="icon.png" width="96" alt="YouTube Analytics integration for Flow Steward">

[![CI](https://img.shields.io/github/actions/workflow/status/Flow-Steward/ext-marketing-youtube-analytics/ci.yml?branch=main&label=CI)](https://github.com/Flow-Steward/ext-marketing-youtube-analytics/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/Flow-Steward/ext-marketing-youtube-analytics?label=release)](https://github.com/Flow-Steward/ext-marketing-youtube-analytics/releases/latest)

Bring your YouTube channel's numbers into Flow Steward workflows and AI agents: views, watch time, subscribers, traffic sources, audiences and your top videos for any period — without writing code.

This Flow Steward extension is a YouTube Analytics integration for channel reporting. It works through the YouTube Analytics API v2, checks every report request against YouTube's own report tables before sending it, returns exact numbers and makes every method of the API available for workflow automation.

## What is this

YouTube Analytics is the reporting side of YouTube: the statistics of a channel and its videos. This extension is a connector: it adds ready YouTube Analytics steps to the Flow Steward workflow editor and the same operations as tools for AI agents. Read more about Flow Steward at <https://docs.flowsteward.org>.

## What you can automate

- Send a weekly report of views, watch time and new subscribers by day to a team channel or a spreadsheet.
- List the top videos of the last month by views or watch time, for a country or worldwide.
- Follow one video after its release: views by day, countries, traffic sources, audience retention.
- Feed channel numbers to a BI tool or an AI agent that writes the monthly summary.
- Read revenue and ad performance metrics of a monetized channel.
- Keep YouTube Analytics groups of videos, for example one per campaign, and report on a group.

## Why teams use it

- **Requests YouTube accepts.** YouTube supports only some combinations of dimensions, metrics and filters and answers others with an error. The report steps check a request against the report tables of YouTube's documentation first and say what is missing, for example a sort or at most 25 rows.
- **Exact numbers.** Report values are exact decimals, never rounded through floating point.
- **Long reports as files.** A report too long for a step output can be saved as a JSON workflow file.
- **Revenue only where allowed.** Revenue metrics have their own connection type; without it they are refused before anything is sent.
- **Changes are not lost or doubled.** A step that changes a group is never retried automatically. When its outcome is unclear it says so, and you check YouTube before running it again. A test run changes nothing.
- **Tokens stay secret.** Flow Steward keeps and renews the Google authorization; a step receives only the current access token and removes it from every answer.

## What's inside

Everyday steps:

- **Test connection** — checks the authorization by reading one day of the channel's views.
- **Get channel report** — the metrics and dimensions you choose for the channel and a period, with filters, sort and number of rows.
- **Get video report** — the same for one video.
- **Get top videos** — the channel's top videos of a period, by views, watch time, subscribers or revenue.
- **Get all my groups**, **Create group**, **Add video to group** — YouTube Analytics groups.

All 8 methods of the YouTube Analytics API v2 are also available as steps: reports, groups and group items. The **Report tables** page lists every combination of dimensions, metrics and filters YouTube allows for channel reports.

## Get started

1. In Flow Steward, open **Extensions → Catalog**, find **YouTube Analytics** and install it.
2. In Google Cloud, enable the **YouTube Analytics API**, configure the OAuth consent screen and create an OAuth client of the type **Web application**. Add the OAuth Redirect URI shown on the extension's **Connection** page as an authorized redirect URI.
3. On the **Connection** page, enter the client's **Client ID** and **Client Secret**, choose a connection type, press **Connect**, sign in with the channel's Google account and allow the access. Then press **Test connection**.
4. Build your first workflow: for example, a weekly schedule → **Get channel report** with `views`, `estimatedMinutesWatched` and `subscribersGained` by `day` → a message to your team.

## Requirements

- A YouTube channel and its Google account.
- A Google Cloud project with the YouTube Analytics API enabled and an OAuth client of the type Web application; its Client ID and Client Secret are entered on the Connection page. Whether Google must verify the app follows Google's policies for the scopes it asks for.
- The connection type: **YouTube channel analytics** (`yt-analytics.readonly`) or **YouTube channel analytics with revenue** (also `yt-analytics-monetary.readonly`; YouTube gives revenue metrics only for channels in the YouTube Partner Program).
- Flow Steward 0.9.23 or later.

## FAQ

**How do I get YouTube views by day for my channel?**
Use **Get channel report** with `metrics` `views` and `dimensions` `day` for the period you need.

**Which metrics and dimensions can I combine?**
Those of one report table on YouTube's channel reports page; the extension's **Report tables** page lists them. A step refuses a combination that no table allows and says why, before anything is sent.

**How do I find my most watched videos of last month?**
Use **Get top videos** with the month's first and last day and `sort` `-estimatedMinutesWatched`.

**Can I read revenue?**
Yes, with a connection of the type **YouTube channel analytics with revenue**, for a channel in the YouTube Partner Program.

**Does this extension upload videos or answer comments?**
No. It reads YouTube Analytics. The Flow Steward YouTube extension covers videos, playlists and comments.

## In your language

Интеграция YouTube Analytics с Flow Steward приносит в workflow и AI-агентам цифры канала без программирования: просмотры, время просмотра, подписчики, источники трафика, аудитория и лучшие видео за любой период. Запрос отчёта проверяется по таблицам отчётов YouTube до отправки; числа точные. Все 8 методов YouTube Analytics API v2 доступны как шаги workflow. Для подключения нужен собственный OAuth-клиент Google Cloud (Client ID и Client Secret).

## Links

- Flow Steward documentation: <https://docs.flowsteward.org>
- Flow Steward extension catalog: <https://github.com/Flow-Steward/extensions>
- Issues and support: <https://github.com/Flow-Steward/ext-marketing-youtube-analytics/issues>
- YouTube Analytics API documentation: <https://developers.google.com/youtube/analytics>
- YouTube Analytics channel reports: <https://developers.google.com/youtube/analytics/channel_reports>
- Changes: [CHANGELOG.md](CHANGELOG.md)

## For developers

Every step is generated from the Discovery document pinned in `tests/reference/` (`youtubeAnalytics_v2.json`, revision 20261122, downloaded 2026-11-23) and from the report tables extracted from YouTube's channel reports page (`tests/reference/channel_reports.json`). To rebuild the contracts:

```bash
python3 tests/reference/build_contracts.py
```

To extract the report tables again, download `https://developers.google.com/youtube/analytics/channel_reports?hl=en` to `tests/reference/sources/channel_reports.html` (not committed) and run `python3 -I tests/reference/extract_channel_reports.py`.

From a Flow Steward checkout (the checks run in the `fs-audit` container):

```bash
./core/entrypoints/cli/scripts/lint.sh --checks extension-static,extension-tests --extension-root "$PWD/workspace/extensions/flowsteward_youtube_analytics"
./flow-steward extensions validate flowsteward.youtube-analytics --root workspace/extensions --health --marketplace
./flow-steward extensions test flowsteward.youtube-analytics --root workspace/extensions
```

The read-only live test runs when `YOUTUBE_ANALYTICS_TOKEN_FILE` names a file with a current access token of a test channel; without it, it is skipped.

YouTube and the YouTube logo are trademarks of Google LLC; see [BRANDING.md](BRANDING.md) for the icon's source.
