#!/usr/bin/env python3
"""FMBO people crawler — cast/crew detail pages from fridaymatinee.in.

Reads people_queue.json (built by crawl_movies.py), fetches each
/people/<slug> page's server-rendered HTML, and extracts:
  - person: name, photo, role
  - tabs: per-role film counts (actor/producer/director/...)
  - films: filmography with per-film Kerala gross (deduped)

Same politeness rules as crawl_movies.py. Resumable via people/<slug>.json.
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
PEOPLE_DIR = os.path.join(ROOT, "people")
LOG = os.path.join(ROOT, "crawl.log")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DELAY_MIN, DELAY_MAX = 2.5, 4.0
MAX_RETRIES = 4


def log(msg):
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def fetch(url):
    """Returns (html, status) via curl subprocess (reliable vs urllib here)."""
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


def parse_person_page(html, url, slug):
    u = flight_blob(html)
    # person object
    person = {}
    m = re.search(r'"person":\{', u)
    if m:
        raw = brace_match(u, m.end() - 1)
        if raw:
            try:
                p = json.loads(raw)
                person = {k: p.get(k) for k in ("name", "photo", "role")}
            except Exception:
                pass
    if not person.get("name"):
        return None
    # tabs
    tabs = []
    for tm in re.finditer(r'"key":"(\w+)","label":"([^"]+)","count":(\d+)', u):
        tabs.append({"key": tm.group(1), "label": tm.group(2),
                     "count": int(tm.group(3))})
    # filmography bars (each film rendered twice: chart + list) -> dedupe
    seen = set()
    films = []
    for hm in re.finditer(r'"href":"(/boxoffice/[^"]+)","aria-label":"([^"]+)"', u):
        href, label = hm.group(1), hm.group(2)
        if href in seen:
            continue
        seen.add(href)
        im = re.match(r"/boxoffice/(.+)-(\d+)$", href)
        lm = re.match(r"^(.*),\s(\d{4}):\s(.+)$", label)
        films.append({
            "movie_id": int(im.group(2)) if im else None,
            "movie_slug": im.group(1) if im else None,
            "title": lm.group(1) if lm else label,
            "year": int(lm.group(2)) if lm else None,
            "kerala_gross": lm.group(3) if lm else None,
        })
    return {"person": person, "tabs": tabs, "films": films}


def main():
    os.makedirs(PEOPLE_DIR, exist_ok=True)
    queue_path = os.path.join(ROOT, "people_queue.json")
    if not os.path.exists(queue_path):
        log("people crawl: no people_queue.json yet, exiting")
        sys.exit(1)
    queue = json.load(open(queue_path))
    log(f"people crawl starting: {len(queue)} people")
    done, failed, skipped = 0, [], 0
    total = len(queue)
    for n, entry in enumerate(queue, 1):
        slug = entry["slug"]
        out = os.path.join(PEOPLE_DIR, f"{slug}.json")
        if os.path.exists(out):
            skipped += 1
            continue
        url = f"{BASE}/people/{slug}"
        try:
            html, _ = fetch(url)
            data = parse_person_page(html, url, slug)
            if not data:
                failed.append(slug)
                log(f"PARSE FAIL {slug} {url}")
            else:
                record = {
                    "slug": slug,
                    "name": entry.get("name"),
                    "source_url": url,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    **data,
                }
                with open(out, "w") as f:
                    json.dump(record, f, ensure_ascii=False, indent=1)
                done += 1
        except Exception as e:
            failed.append(slug)
            log(f"FETCH FAIL {slug} {url}: {type(e).__name__}: {e}")
        if n % 100 == 0:
            log(f"people progress {n}/{total} done={done} "
                f"skipped={skipped} failed={len(failed)}")
        time.sleep(DELAY_MIN + random.random() * (DELAY_MAX - DELAY_MIN))
    log(f"people crawl finished: done={done} skipped={skipped} "
        f"failed={len(failed)}")
    if failed:
        log(f"failed slugs: {failed[:50]}")


if __name__ == "__main__":
    main()
