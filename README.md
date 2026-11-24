# YouTube Analytics integration for Flow Steward

<img src="icon.png" width="96" alt="YouTube Analytics integration for Flow Steward">

[![CI](https://img.shields.io/github/actions/workflow/status/Flow-Steward/ext-marketing-youtube-analytics/ci.yml?branch=main&label=CI)](https://github.com/Flow-Steward/ext-marketing-youtube-analytics/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/Flow-Steward/ext-marketing-youtube-analytics?label=release)](https://github.com/Flow-Steward/ext-marketing-youtube-analytics/releases/latest)
[![YouTube Analytics API](https://img.shields.io/badge/YouTube%20Analytics%20API-v2-FF0000)](https://developers.google.com/youtube/analytics)
[![Steps](https://img.shields.io/badge/steps-15-blue)](#whats-inside)

Bring your YouTube channel's numbers into Flow Steward workflows and AI agents — no code, no spreadsheet exports by hand. Views, watch time, subscribers, traffic sources, devices, audiences, revenue and your top videos, for any period, straight into reports, dashboards and AI summaries.

The extension works through the YouTube Analytics API v2 and your own Google Cloud OAuth client. Every report request is checked against YouTube's own channel report tables before it is sent, numbers are exact decimals, and every method of the API is a workflow step.

## What is this

YouTube Analytics is the reporting side of [YouTube](https://www.youtube.com): the statistics of a channel and its videos. [Flow Steward](https://docs.flowsteward.org) runs workflows and AI agents that connect business systems.

This extension connects the two. Once installed, YouTube Analytics appears in the Flow Steward workflow editor as a set of steps, and the same operations are available to AI agents as tools. Each connection is one YouTube channel, authorized by its owner through Google's sign-in page; Flow Steward keeps the authorization, renews it and never shows it again.

Videos, playlists and comments come from the companion extension [YouTube](https://github.com/Flow-Steward/ext-media-youtube).

## What you can automate

### Reporting

- **Weekly channel report.** Every Monday, read views, watch time and new subscribers by day for the past week and post the summary to a team channel, an email or a spreadsheet.
- **Monthly management summary.** Read the month's numbers by country, device and traffic source and let an AI agent write the summary for management.
- **Dashboards without exports.** Feed channel and video numbers to a BI tool or a database on a schedule; long reports go out as JSON workflow files.

### Content performance

- **Top videos of a period.** List the most watched videos of the last month by views, watch time, subscribers gained or revenue — worldwide or for one country.
- **Launch tracking.** Follow a new video day by day after its release: views, watch time, average view duration, likes, traffic sources and audience retention.
- **Campaign groups.** Keep YouTube Analytics groups of videos — one per campaign, product or series — add new videos as they are published, and report on the whole group at once.

### Audience

- **Who watches.** Read viewer age group, gender and geography where YouTube reports them, and subscribed versus not-subscribed viewers.
- **Where viewers come from.** Traffic sources, playback locations, devices and operating systems, sharing services.

### Revenue

- **Revenue and ads.** With the connection with revenue, read estimated revenue, ad impressions, CPM and other monetary metrics of a channel in the YouTube Partner Program, in the currency you choose.

## Why teams use it

- **Requests YouTube accepts.** YouTube answers only some combinations of dimensions, metrics and filters. The report steps check a request against the report tables of YouTube's documentation first and say what is missing — for example a sort, or at most 25 rows — before anything is sent.
- **Exact numbers.** Report values are exact decimals, never rounded through floating point.
- **Long reports as files.** A report too long for a step output is saved as a JSON workflow file with its column headers and rows.
- **Revenue only where allowed.** Revenue metrics have their own connection type; without it they are refused before anything is sent.
- **The right channel, always.** After the authorization the extension learns which channel was connected; connecting the same connection to another channel is refused.
- **Lists never overshoot.** A list of groups never returns more than asked for, and when it stops early it returns the exact place to continue from.
- **Changes are sent once.** A step that changes a group is never retried automatically; when its outcome is unclear it says so. A test run changes nothing.
- **Tokens stay secret.** A step receives only the current access token and removes it from every answer.

## What's inside

### Everyday steps

- **Test connection** — checks the authorization by reading one day of the channel's views.
- **Get channel report** — the metrics and dimensions you choose for the channel and a period, with filters, sort and number of rows.
- **Get video report** — the same for one video.
- **Get top videos** — the channel's top videos of a period, by views, watch time, subscribers or revenue.
- **Get all my groups**, **Create group**, **Add video to group** — YouTube Analytics groups.

### YouTube Analytics API steps

- **Reports** (1 step) — **Query analytics report**: any report the API answers, with every parameter of reports.query.
- **Groups** (7 steps) — **Get analytics groups**, **Create analytics group**, **Update analytics group**, **Delete analytics group**, **Get analytics group items**, **Add analytics group item**, **Remove analytics group item**.

All 8 methods of the YouTube Analytics API v2 have their own step. The **YouTube Analytics API coverage** page lists every step with the method it calls, its inputs, the fields of its request body and the fields YouTube returns. The **Report tables** page lists every combination of dimensions, metrics and filters YouTube allows for channel reports.

### Pages in Flow Steward

- **Setup Guide** — the Google Cloud project, consent screen, OAuth client, metrics and errors.
- **Connection** and **Connection with revenue** — one page per connection type.
- **YouTube Analytics API**, **Reports** and **Groups** — every step with what it does.
- **Report tables**, **YouTube Analytics API coverage**, **Changelog**, **Support**.

## Get started

1. **Install the extension.** In Flow Steward open **Extensions → Catalog**, find **YouTube Analytics** and install it.
2. **Set up Google Cloud.** Enable the **YouTube Analytics API** and the **YouTube Data API v3**, configure the OAuth consent screen with `yt-analytics.readonly` and `youtube.readonly`, and create an OAuth client of the type **Web application** with the **OAuth Redirect URI** from the extension's **Connection** page.
3. **Enter the client.** On the **Connection** page enter the **Client ID** and **Client Secret** and save them.
4. **Connect the channel.** Press **Connect** (or use **Connection with revenue**), sign in with the channel's Google account and allow the access. Press **Test connection**.
5. **Build your first workflow.** For example: *every Monday* → **Get channel report** with `views`, `estimatedMinutesWatched` and `subscribersGained` by `day` → *a message to your team*.

The **Setup Guide** page of the extension walks through every screen.

## Requirements

- **A YouTube channel** and the Google account that owns or manages it.
- **A Google Cloud project** with the YouTube Analytics API and the YouTube Data API v3 enabled and an OAuth client of the type Web application. Whether Google must verify the app follows Google's policies for the scopes it asks for. An external app in **Testing** receives refresh tokens that expire in 7 days; publish it for lasting connections.
- **The connection type:** **YouTube channel analytics** (`yt-analytics.readonly`) or **YouTube channel analytics with revenue** (also `yt-analytics-monetary.readonly`; YouTube gives revenue metrics for channels in the YouTube Partner Program). Both also ask for `youtube.readonly` to learn which channel is connected.
- **Flow Steward** 0.9.23 or later.

## FAQ

**How do I get YouTube views by day for my channel?**
Use **Get channel report** with `metrics` `views` and `dimensions` `day` for the period you need.

**Which metrics and dimensions can I combine?**
Those of one report table on YouTube's channel reports page; the extension's **Report tables** page lists them. A step refuses a combination that no table allows and says why, before anything is sent.

**How do I find my most watched videos of last month?**
Use **Get top videos** with the month's first and last day and `sort` `-estimatedMinutesWatched`.

**How do I report on a set of videos?**
Create a group with **Create group**, add the videos with **Add video to group**, and use the group as a filter of **Get channel report**.

**Can I read revenue?**
Yes, with a connection made on **Connection with revenue**, for a channel in the YouTube Partner Program. Choose the currency with `currency`.

**Why does my connection stop working after a week?**
The OAuth consent screen is in **Testing**, where Google issues refresh tokens that expire in 7 days. Publish the app, then connect again.

**Where do I upload videos or answer comments?**
In the companion extension [YouTube](https://github.com/Flow-Steward/ext-media-youtube), which works with the same channel and can use the same Google OAuth client.

## In your language

**Русский.** Интеграция YouTube Analytics для Flow Steward приносит в workflow и AI-агентам цифры канала без программирования: просмотры, время просмотра, подписчики, источники трафика, устройства, аудитория, доход и лучшие видео за любой период. Запрос отчёта проверяется по таблицам отчётов YouTube до отправки, числа точные, все 8 методов YouTube Analytics API v2 — шаги workflow.

**Deutsch.** Die YouTube-Analytics-Integration für Flow Steward bringt die Zahlen Ihres Kanals ohne Programmierung in Workflows und KI-Agenten: Aufrufe, Wiedergabezeit, Abonnenten, Traffic-Quellen, Zielgruppe, Umsatz und Top-Videos für jeden Zeitraum.

**Español.** La integración de YouTube Analytics para Flow Steward lleva las cifras de tu canal a workflows y agentes de IA sin programar: visualizaciones, tiempo de visualización, suscriptores, fuentes de tráfico, audiencia, ingresos y los vídeos más vistos de cualquier periodo.

**Français.** L'intégration YouTube Analytics pour Flow Steward apporte les chiffres de votre chaîne aux workflows et agents IA sans code : vues, durée de visionnage, abonnés, sources de trafic, audience, revenus et meilleures vidéos sur n'importe quelle période.

## Links

- Flow Steward documentation: <https://docs.flowsteward.org>
- Flow Steward extension catalog: <https://github.com/Flow-Steward/extensions>
- Issues and support: <https://github.com/Flow-Steward/ext-marketing-youtube-analytics/issues>
- YouTube Analytics API documentation: <https://developers.google.com/youtube/analytics>
- YouTube Analytics channel reports: <https://developers.google.com/youtube/analytics/channel_reports>
- Changes: [CHANGELOG.md](CHANGELOG.md)

## For developers

Every step is generated from the Discovery document pinned in `tests/reference/` (`youtubeAnalytics_v2.json`, revision 20261122, downloaded 2026-11-23) and from the report tables extracted from YouTube's channel reports page (`tests/reference/channel_reports.json`). `tests/reference/field_texts.py` gives each input name one label in every step. To rebuild the contracts and the generated pages:

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
