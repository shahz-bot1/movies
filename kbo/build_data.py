#!/usr/bin/env python3
"""Build optimized KBO web data from the FMBO capture.

Source:  ~/workspace/movies/fmbo/{movies,people}/*.json
Output:  ~/workspace/movies/kbo/data/
  movies.json          browse/search index, one light row per movie
  movie-bundles/b<N>.json   {"<id>": detail, ...} ~100 movies each
  people.json          people index (slug, name, photo, roles, totals)
  people-bundles/b<N>.json  {"<slug>": person record, ...} ~500 each

Detail shape (deduplicated): the source stores the same movie/cast/crew
payload in three views; here it is stored once, with the three
box-office series separated: daily / weekly / districts + summary.
"""
import glob
import json
import os
import re

SRC = os.path.expanduser("~/workspace/movies/fmbo")
OUT = os.path.expanduser("~/workspace/movies/kbo/data")
MOVIES_PER_BUNDLE = 100
PEOPLE_PER_BUNDLE = 500


def parse_gross(s):
    """'₹4.0 Cr' -> 40000000, '₹63.5L' -> 6350000, '₹4.0K' -> 4000."""
    if not s:
        return None
    m = re.match(r"₹([\d.]+)\s*(Cr|L|K)?", s.replace(",", ""))
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2)
    if unit == "Cr":
        v *= 1e7
    elif unit == "L":
        v *= 1e5
    elif unit == "K":
        v *= 1e3
    return int(v)


def movie_detail(rec):
    v = rec["views"]["date"]
    wk = rec["views"].get("week", {})
    di = rec["views"].get("district", {})
    return {
        "movie": v["movie"],
        "omdb": v.get("omdb"),
        "cast": v.get("cast", []),
        "crew": v.get("crew", []),
        "companies": v.get("companies", []),
        "ott": v.get("ott"),
        "otherReleases": v.get("otherReleases", {}),
        "daily": v.get("boxoffice", []),
        "weekly": wk.get("boxoffice", []),
        "districts": di.get("boxoffice", []),
        "summary": v.get("summary", {}),
        "archive": v.get("archive"),
    }


def main():
    os.makedirs(os.path.join(OUT, "movie-bundles"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "people-bundles"), exist_ok=True)

    index = []
    details = {}
    for path in sorted(glob.glob(os.path.join(SRC, "movies", "*.json")),
                       key=lambda p: int(os.path.basename(p)[:-5])):
        rec = json.load(open(path))
        d = movie_detail(rec)
        m, s = d["movie"], d["summary"]
        details[str(rec["id"])] = d
        index.append({
            "id": rec["id"], "slug": rec["slug"], "title": m["title"],
            "poster": m.get("img"), "released": m.get("released"),
            "language": m.get("language"), "imdbId": m.get("imdbId"),
            "isRerelease": m.get("isRerelease"),
            "totalGross": s.get("totalGross"), "totalShows": s.get("totalShows"),
            "totalDays": s.get("totalDays"), "avgOcc": s.get("avgOcc"),
        })
    json.dump(index, open(os.path.join(OUT, "movies.json"), "w"),
              ensure_ascii=False, separators=(",", ":"))

    ids = sorted(details.keys(), key=int)
    for i in range(0, len(ids), MOVIES_PER_BUNDLE):
        chunk = {k: details[k] for k in ids[i:i + MOVIES_PER_BUNDLE]}
        json.dump(chunk, open(os.path.join(OUT, "movie-bundles",
                                           f"b{i // MOVIES_PER_BUNDLE}.json"), "w"),
                  ensure_ascii=False, separators=(",", ":"))

    pindex = []
    precords = {}
    for path in glob.glob(os.path.join(SRC, "people", "*.json")):
        rec = json.load(open(path))
        films = []
        total = 0
        for f in rec.get("films", []):
            g = parse_gross(f.get("kerala_gross"))
            films.append({**f, "gross_inr": g})
            if g:
                total += g
        precords[rec["slug"]] = {
            "person": rec["person"], "tabs": rec.get("tabs", []), "films": films,
        }
        roles = [t["label"].lower() for t in rec.get("tabs", [])]
        pindex.append({
            "slug": rec["slug"], "name": rec["person"]["name"],
            "photo": rec["person"].get("photo"), "role": rec["person"].get("role"),
            "roles": roles, "filmCount": len(films), "keralaGross": total,
        })
    pindex.sort(key=lambda x: x["name"].lower())
    json.dump(pindex, open(os.path.join(OUT, "people.json"), "w"),
              ensure_ascii=False, separators=(",", ":"))

    slugs = [p["slug"] for p in pindex]
    for i in range(0, len(slugs), PEOPLE_PER_BUNDLE):
        chunk = {s: precords[s] for s in slugs[i:i + PEOPLE_PER_BUNDLE]}
        json.dump(chunk, open(os.path.join(OUT, "people-bundles",
                                           f"b{i // PEOPLE_PER_BUNDLE}.json"), "w"),
                  ensure_ascii=False, separators=(",", ":"))

    total_size = 0
    for root, _, files in os.walk(OUT):
        total_size += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    print(f"movies: {len(index)} indexed, {len(details)} details in "
          f"{(len(ids) + MOVIES_PER_BUNDLE - 1) // MOVIES_PER_BUNDLE} bundles")
    print(f"people: {len(pindex)} indexed in "
          f"{(len(slugs) + PEOPLE_PER_BUNDLE - 1) // PEOPLE_PER_BUNDLE} bundles")
    print(f"kbo/data total: {total_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
