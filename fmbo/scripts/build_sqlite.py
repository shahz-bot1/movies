import json, sqlite3, pathlib
base = pathlib.Path(__file__).resolve().parent.parent
db_path = base / "fmbo.sqlite"
if db_path.exists():
    db_path.unlink()
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.executescript("""
CREATE TABLE movies(id INTEGER PRIMARY KEY, slug TEXT, title TEXT, released TEXT, language TEXT, imdb_id TEXT, is_rerelease INTEGER, total_gross INTEGER, total_days INTEGER, source_url TEXT, captured_at TEXT);
CREATE TABLE people(slug TEXT PRIMARY KEY, name TEXT, role TEXT, photo_url TEXT, source_url TEXT);
CREATE TABLE person_films(person_slug TEXT, movie_id INTEGER, movie_slug TEXT, title TEXT, year TEXT, kerala_gross_text TEXT);
CREATE TABLE cast_members(movie_id INTEGER, person_slug TEXT, name TEXT, character TEXT);
CREATE TABLE crew_members(movie_id INTEGER, role TEXT, person_slug TEXT, name TEXT);
CREATE TABLE boxoffice_daily(movie_id INTEGER, label TEXT, gross INTEGER, sold INTEGER, shows INTEGER, occ REAL, cumul INTEGER);
CREATE INDEX idx_pf_person ON person_films(person_slug);
CREATE INDEX idx_pf_movie ON person_films(movie_id);
CREATE INDEX idx_bo_movie ON boxoffice_daily(movie_id);
""")
idx = json.loads((base/"index.json").read_text())
for r in idx:
    cur.execute("INSERT OR REPLACE INTO movies VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (r.get("id"), r.get("slug"), r.get("title"), r.get("released"), r.get("language"), r.get("imdbId"), 1 if r.get("isRerelease") else 0, r.get("totalGross"), r.get("totalDays"), r.get("source_url"), r.get("captured_at")))
for mf in sorted((base/"movies").glob("*.json")):
    m = json.loads(mf.read_text())
    mid = m.get("id")
    view = (m.get("views") or {}).get("date") or {}
    for c in view.get("cast") or []:
        cur.execute("INSERT INTO cast_members VALUES (?,?,?,?)", (mid, c.get("slug"), c.get("name"), c.get("character")))
    for crew in view.get("crew") or []:
        role = crew.get("role")
        for p in crew.get("people") or []:
            cur.execute("INSERT INTO crew_members VALUES (?,?,?,?)", (mid, role, p.get("slug"), p.get("name")))
    for b in view.get("boxoffice") or []:
        cur.execute("INSERT INTO boxoffice_daily VALUES (?,?,?,?,?,?,?)", (mid, b.get("label"), b.get("gross"), b.get("sold"), b.get("shows"), b.get("occ"), b.get("cumul")))
for pf in sorted((base/"people").glob("*.json")):
    p = json.loads(pf.read_text())
    person = p.get("person") or {}
    cur.execute("INSERT OR REPLACE INTO people VALUES (?,?,?,?,?)", (p.get("slug"), p.get("name") or person.get("name"), person.get("role"), person.get("photo"), p.get("source_url")))
    for f in p.get("films") or []:
        cur.execute("INSERT INTO person_films VALUES (?,?,?,?,?,?)", (p.get("slug"), f.get("movie_id"), f.get("movie_slug"), f.get("title"), f.get("year"), f.get("kerala_gross")))
con.commit()
for t in ["movies","people","person_films","cast_members","crew_members","boxoffice_daily"]:
    print(t, cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("top_gross", cur.execute("SELECT title,total_gross FROM movies ORDER BY total_gross DESC LIMIT 3").fetchall())
con.close()
print(db_path)
