#!/usr/bin/env python3
"""FMBO movie crawler — fridaymatinee.in box office data capture.

Reads the sitemap for the full movie list, fetches each movie page's
server-rendered HTML, and extracts the embedded data object with three
box-office views (daily / weekly / district) plus movie, cast, crew,
companies, OTT and summary data.

Polite crawl: sequential requests, ~1.2-1.8s delay, retries with backoff.
Resumable: skips movies/<id>.json files that already exist.
Never touches /api/* (robots.txt honeypots are auto-ban).
"""
import gzip
import json
import os
import random
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://fridaymatinee.in"
ROOT = os.path.expanduser("~/workspace/movies/fmbo")
MOVIES_DIR = os.path.join(ROOT, "movies")
LOG = os.path.join(ROOT, "crawl.log")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DELAY_MIN, DELAY_MAX = 3.0, 5.0
MAX_RETRIES = 4
COOLDOWN_ON_TRUNCATION = 300  # legacy, kept for log compat


def log(msg):
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def fetch(url):
    """Returns (html, status) via curl subprocess.

    curl proved far more reliable than urllib here: the server intermittently
    truncates the TCP stream for urllib's TLS fingerprint (IncompleteRead),
    while curl completes the same pages cleanly.
    """
    import subprocess
    import tempfile
    last_err = None
    for attempt in range(MAX_RETRIES):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        tmp.close()
        try:
            p = subprocess.run(
                ["curl", "-sL", "--compressed", "-A", UA,
                 "--max-time", "40",
                 "-w", "\n%{http_code}",
                 "-o", tmp.name, url],
                capture_output=True, text=True, timeout=60)
            code_out = p.stdout.strip().split("\n")[-1] if p.stdout.strip() else ""
            try:
                status = int(code_out)
            except ValueError:
                status = 0
            if p.returncode != 0 or status != 200:
                raise RuntimeError(f"curl rc={p.returncode} http={status} "
                                   f"err={p.stderr[:200]}")
            with open(tmp.name, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            if len(html) < 5000:
                raise RuntimeError(f"suspiciously small page ({len(html)} chars)")
            return html, status
        except Exception as e:
            last_err = e
            name = type(e).__name__
            wait = [8, 20, 60, 120][min(attempt, 3)]
            if "429" in str(e) or "503" in str(e):
                wait = 120
                log(f"RATE-LIMITED on {url}, sleeping 120s")
            else:
                log(f"fetch error attempt {attempt+1}/{MAX_RETRIES} {url}: {e}")
            time.sleep(wait)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    raise last_err


def unescape_flight(s):
    out = []
    i = 0
    n = len(s)
    simple = {'"': '"', "\\": "\\", "n": "\n", "t": "\t",
              "r": "\r", "/": "/", "b": "\b", "f": "\f"}
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            out.append(simple.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def flight_blob(html):
    pushes = re.findall(r"self\.__next_f\.push\(\[1,(.*?)\)</script>", html, re.S)
    parts = []
    for p in pushes:
        try:
            parts.append(json.loads(p))
        except Exception:
            parts.append(p)
    return unescape_flight("".join(parts))


def brace_match(s, i):
    """Return the {...} object starting at index i, or None."""
    depth = 0
    instr = False
    esc = False
    for j in range(i, len(s)):
        c = s[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[i:j + 1]
    return None


def enclosing_object(s, idx):
    """Brace-match the object enclosing position idx."""
    depth = 0
    instr = False
    esc = False
    start = None
    i = idx - 1
    while i >= 0:
        c = s[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "}":
                depth += 1
            elif c == "{":
                if depth == 0:
                    start = i
                    break
                depth -= 1
        i -= 1
    if start is None:
        return None
    return brace_match(s, start)


def parse_movie_page(html, url, movie_id):
    u = flight_blob(html)
    # Primary: top-level {date, week, district} object
    for m in re.finditer(r'"district"\s*:', u):
        j = m.end()
        while j < len(u) and u[j] in " \t\n":
            j += 1
        if u[j:j + 9] != '{"movie":':
            continue
        raw = enclosing_object(u, m.start())
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if isinstance(d, dict) and {"date", "week", "district"} <= set(d.keys()):
            got_id = d["date"].get("movie", {}).get("id")
            if got_id is not None and int(got_id) != int(movie_id):
                log(f"ID MISMATCH {url}: sitemap {movie_id} vs page {got_id}")
                return None
            return d
    # Fallback: single view object containing "cast"
    idx = u.find('"cast":[')
    if idx > 0:
        raw = enclosing_object(u, idx)
        if raw:
            try:
                d = json.loads(raw)
                if isinstance(d, dict) and "cast" in d and "movie" in d:
                    return {"date": d}
            except Exception:
                pass
    return None


def collect_people(data, people):
    """Dedupe cast/crew slugs from all three views. Defensive on shapes."""
    if not isinstance(data, dict):
        return
    views = data.get("views", data)
    if not isinstance(views, dict):
        return
    for view in ("date", "week", "district"):
        v = views.get(view)
        if not isinstance(v, dict):
            continue
        cast = v.get("cast")
        if isinstance(cast, list):
            for c in cast:
                if isinstance(c, dict) and c.get("slug"):
                    people[c["slug"]] = c.get("name")
        crew = v.get("crew")
        if isinstance(crew, list):
            for cr in crew:
                if not isinstance(cr, dict):
                    continue
                ps = cr.get("people")
                if isinstance(ps, list):
                    for p in ps:
                        if isinstance(p, dict) and p.get("slug"):
                            people[p["slug"]] = p.get("name")


def get_sitemap_movies():
    html, _ = fetch(f"{BASE}/sitemap.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", html)
    movies = []
    for loc in locs:
        m = re.match(r"https://fridaymatinee\.in/boxoffice/(.+)-(\d+)$", loc)
        if m:
            movies.append({"id": int(m.group(2)), "slug": m.group(1),
                           "url": loc})
    movies.sort(key=lambda x: x["id"])
    return movies


def main():
    os.makedirs(MOVIES_DIR, exist_ok=True)
    log("movie crawl starting")
    movies = get_sitemap_movies()
    log(f"sitemap: {len(movies)} movies")
    with open(os.path.join(ROOT, "sitemap_movies.json"), "w") as f:
        json.dump(movies, f, indent=1)

    people = {}
    done, failed, skipped = 0, [], 0
    total = len(movies)
    for n, mv in enumerate(movies, 1):
        out = os.path.join(MOVIES_DIR, f"{mv['id']}.json")
        if os.path.exists(out):
            skipped += 1
            # still collect people slugs from existing file
            try:
                d = json.load(open(out))
                collect_people(d, people)
            except Exception:
                pass
            continue
        try:
            html, _ = fetch(mv["url"])
            data = parse_movie_page(html, mv["url"], mv["id"])
            if not data:
                failed.append(mv["id"])
                log(f"PARSE FAIL {mv['id']} {mv['url']}")
            else:
                record = {
                    "id": mv["id"],
                    "slug": mv["slug"],
                    "source_url": mv["url"],
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "views": data,
                }
                with open(out, "w") as f:
                    json.dump(record, f, ensure_ascii=False, indent=1)
                collect_people(record, people)
                done += 1
        except Exception as e:
            failed.append(mv["id"])
            log(f"FETCH FAIL {mv['id']} {mv['url']}: {type(e).__name__}: {e}")
        if n % 50 == 0:
            log(f"progress {n}/{total} done={done} skipped={skipped} failed={len(failed)}")
        time.sleep(DELAY_MIN + random.random() * (DELAY_MAX - DELAY_MIN))

    with open(os.path.join(ROOT, "people_queue.json"), "w") as f:
        json.dump([{"slug": s, "name": n} for s, n in sorted(people.items())],
                  f, indent=1, ensure_ascii=False)
    log(f"movie crawl finished: done={done} skipped={skipped} "
        f"failed={len(failed)} unique_people={len(people)}")
    if failed:
        log(f"failed ids: {failed}")


if __name__ == "__main__":
    main()
