# FMBO data capture — schema

Source: https://fridaymatinee.in (FMBO - Box Office Analytics).
Captured 2026-10-01 from server-rendered pages (no API use).
All box-office figures are Kerala collections in INR (₹) unless noted.

## Layout

- `movies/<id>.json` — one per movie, `<id>` is FMBO's numeric movie id
- `people/<slug>.json` — one per cast/crew person, `<slug>` is FMBO's person slug
- `index.json` — lightweight lookup: id, slug, title, release date, language, imdbId
- `sitemap_movies.json` — the sitemap-derived movie list this crawl ran from
- `people_queue.json` — unique cast/crew slugs collected from the movies
- `crawl.log` — timestamped run log (progress, failures, rate-limit events)
- `scripts/` — the crawlers (`crawl_movies.py`, `crawl_people.py`)

## movies/<id>.json

Top-level keys: `id`, `slug`, `source_url`, `captured_at` (UTC ISO), `views`.

`views` has three box-office granularities — `date` (daily), `week`
(weekly aggregates), `district` (per-district). Each view holds the same
movie payload with its own `boxoffice` array and `summary`:

- `movie`: `id`, `title`, `img` (poster URL, TMDB/Amazon CDN), `released`
  (YYYY-MM-DD), `language`, `live`, `pretrack`, `imdbId` (e.g. `tt9260636`),
  `isRerelease`
- `omdb`: `rated`, `runtime`, `genre`, `plot`, `released`, `director`,
  `directorSlug`, `actors[]`, `awards`, `ratings` (`imdb`/`tmdb`/`rt`/
  `metascore`, each with value/votes/updatedAt where present)
- `cast[]`: `name`, `character`, `slug`, `profile_picture_url`
- `crew[]`: `role` (director/writer/music/dop/editor/producer),
  `people[]` of `name`, `slug`
- `companies[]`: `name`, `slug`, `logo` (nullable)
- `ott`: `releaseDate` (nullable), `platforms[]`
- `otherReleases`: map of `YYYY-MM-DD` → `[{id, title, img}]` (same-day competing releases)
- `boxoffice[]`: one entry per day / week / district:
  `label` (date, week-start date, or district name), `gross`, `sold`,
  `unsold`, `shows`, `occ` (occupancy %), `hf` / `almost` / `ff`
  (housefull / almost-full / fast-filling show counts), `cumul`
  (running total), `lastUpdatedAt`
- `summary`: `totalGross`, `totalShows`, `totalSeats`, `totalSold`,
  `avgOcc`, `totalDays`, `totalHousefull`, `totalAlmost`,
  `totalFastFilling`, `peakDay` {day, gross, date},
  `openingDay` {day, gross, date}, `chartPosition`
  {current_position, weeks_on_chart, peak_position, last_week_position}
  (some keys absent on older titles)
- `_tier`, `_hash`: FMBO internal freshness markers, kept as-is
- `archive`: present on older titles as
  `{"restricted": true, "archivedAt": "YYYY-MM-DD"}` — detailed daily
  box office is withheld for these; only `summary` totals are available

## people/<slug>.json

Top-level keys: `slug`, `name`, `source_url`, `captured_at` (UTC ISO),
plus:

- `person`: `name`, `photo` (TMDB profile URL), `role`
  (e.g. "Actor and producer")
- `tabs[]`: `key`, `label`, `count` — per-role film counts
  (actor/director/producer/writer/...)
- `films[]`: filmography in release order, deduped:
  `movie_id`, `movie_slug`, `title`, `year`, `kerala_gross`
  (display string, e.g. "₹63.5L", "₹4.0 Cr")

## Notes

- People are limited to cast/crew members referenced by the captured
  movies (deduped by slug), not FMBO's full ~9,500-person directory.
- Assets are stored as URLs only (TMDB/Amazon CDNs); nothing downloaded.
- Box-office data on FMBO updates roughly hourly — `captured_at` marks
  the snapshot time per file.
