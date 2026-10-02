"use strict";
const DATA = "data/";
const MOVIES_PER_BUNDLE = 100, PEOPLE_PER_BUNDLE = 500;
const state = { movies: null, people: null, moviePos: new Map(), personPos: new Map(),
  bundles: new Map(), movieFilter: { q: "", lang: "All", sort: "gross", shown: 60 },
  peopleFilter: { q: "", sort: "gross", shown: 80 } };

const $app = document.getElementById("app");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const inr = n => n == null ? "—" : (n >= 1e7 ? "₹" + (n / 1e7).toFixed(2) + " Cr" : n >= 1e5 ? "₹" + (n / 1e5).toFixed(1) + " L" : n >= 1e3 ? "₹" + (n / 1e3).toFixed(1) + "K" : "₹" + Math.round(n));
const num = n => n == null ? "—" : Number(n).toLocaleString("en-IN");
const poster = (url, size) => url ? url.replace("/t/p/original/", `/t/p/${size}/`).replace("/t/p/w185/", `/t/p/${size}/`) : "";
const CAPTURE_DATE = "2026-10-01";

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + " " + r.status);
  return r.json();
}
async function loadIndexes() {
  if (!state.movies) {
    state.movies = await getJSON(DATA + "movies.json");
    state.movies.forEach((m, i) => state.moviePos.set(m.id, i));
  }
  if (!state.people) {
    state.people = await getJSON(DATA + "people.json");
    state.people.forEach((p, i) => state.personPos.set(p.slug, i));
  }
}
async function bundle(kind, idx) {
  const key = kind + idx;
  if (!state.bundles.has(key))
    state.bundles.set(key, await getJSON(`${DATA}${kind}-bundles/b${idx}.json`));
  return state.bundles.get(key);
}
async function movieDetail(id) {
  const pos = state.moviePos.get(id);
  if (pos == null) return null;
  const b = await bundle("movie", Math.floor(pos / MOVIES_PER_BUNDLE));
  return b[String(id)] || null;
}
async function personDetail(slug) {
  const pos = state.personPos.get(slug);
  if (pos == null) return null;
  const b = await bundle("people", Math.floor(pos / PEOPLE_PER_BUNDLE));
  return b[slug] || null;
}

/* ---------- charts ---------- */
function barChart(entries, labelFn, maxBars) {
  const list = maxBars && entries.length > maxBars ? entries.filter((_, i) => i % Math.ceil(entries.length / maxBars) === 0) : entries;
  const max = Math.max(...entries.map(e => e.gross || 0), 1);
  const W = 720, H = 180, bw = W / Math.max(list.length, 1);
  const bars = list.map((e, i) => {
    const h = Math.max(2, (e.gross / max) * (H - 24));
    return `<rect class="bar" x="${(i * bw + 1).toFixed(1)}" y="${(H - h).toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="2"><title>${esc(labelFn(e))}: ${inr(e.gross)} · ${num(e.shows)} shows</title></rect>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img">${bars}</svg>`;
}
function hbarChart(entries) {
  const max = Math.max(...entries.map(e => e.gross || 0), 1);
  const rows = entries.map(e => {
    const w = Math.max(1, (e.gross / max) * 100);
    return `<div style="display:grid;grid-template-columns:110px 1fr 90px;gap:8px;align-items:center;margin:5px 0">
      <div style="font-size:13px">${esc(e.label)}</div>
      <div style="background:var(--surface2);border-radius:6px;height:14px"><div style="width:${w}%;height:100%;background:var(--accent);border-radius:6px"></div></div>
      <div style="font-size:13px;font-weight:700;text-align:right">${inr(e.gross)}</div></div>`;
  }).join("");
  return rows;
}

/* ---------- shared bits ---------- */
function movieCard(m) {
  return `<a class="card" href="#/movie/${m.id}">
    <img class="poster" loading="lazy" src="${esc(poster(m.poster, "w185"))}" alt="">
    <div class="cbody"><div class="ct">${esc(m.title)}</div>
    <div class="cm">${esc(m.released || "")} · ${esc(m.language || "")}</div>
    <div class="cg">${inr(m.totalGross)}</div></div></a>`;
}
function personCard(p) {
  return `<a class="card person-card" href="#/person/${esc(p.slug)}" style="padding:14px 8px">
    <img loading="lazy" src="${esc(p.photo || "")}" alt="">
    <div class="pn">${esc(p.name)}</div><div class="pc">${esc(p.role || "")}</div>
    <div class="pc">${p.filmCount} films · ${inr(p.keralaGross)}</div></a>`;
}
function setNav(name) {
  document.querySelectorAll(".topnav a").forEach(a => a.classList.toggle("active", a.dataset.nav === name));
}

/* ---------- views ---------- */
async function viewHome() {
  setNav("");
  await loadIndexes();
  const released = state.movies.filter(m => m.released && m.released <= CAPTURE_DATE && m.totalGross);
  const top = [...released].sort((a, b) => b.totalGross - a.totalGross).slice(0, 12);
  const recent = [...released].filter(m => m.released >= "2026-07-01").sort((a, b) => b.totalGross - a.totalGross).slice(0, 12);
  const coming = state.movies.filter(m => m.released && m.released > CAPTURE_DATE).sort((a, b) => a.released.localeCompare(b.released)).slice(0, 12);
  const totalGross = released.reduce((s, m) => s + (m.totalGross || 0), 0);
  const langs = new Set(state.movies.map(m => (m.language || "").toLowerCase())).size;
  $app.innerHTML = `
    <section class="hero"><h1>Kerala Box Office</h1>
      <p>Collections, daily charts and cast records for ${state.movies.length} tracked films.</p></section>
    <section class="stat-strip">
      <div class="stat-card"><div class="v">${state.movies.length}</div><div class="k">Films tracked</div></div>
      <div class="stat-card"><div class="v">${inr(totalGross)}</div><div class="k">Combined Kerala gross</div></div>
      <div class="stat-card"><div class="v">${num(state.people.length)}</div><div class="k">People indexed</div></div>
      <div class="stat-card"><div class="v">${langs}</div><div class="k">Languages</div></div>
    </section>
    <h2 class="section">Top at the box office <a class="more" href="#/movies">All movies →</a></h2>
    <div class="grid">${recent.map(movieCard).join("")}</div>
    <h2 class="section">Coming soon</h2>
    <div class="grid">${coming.map(movieCard).join("") || '<div class="empty">Nothing scheduled in the archive.</div>'}</div>
    <h2 class="section">All-time top grossers</h2>
    <div class="grid">${top.map(movieCard).join("")}</div>`;
}
async function viewMovies() {
  setNav("movies");
  await loadIndexes();
  const langs = [...new Set(state.movies.map(m => m.language).filter(Boolean))].sort();
  const f = state.movieFilter;
  $app.innerHTML = `
    <h2 class="section">All Movies</h2>
    <div class="toolbar">
      <input id="f-q" type="search" placeholder="Search title…" value="${esc(f.q)}">
      <select id="f-sort">
        <option value="gross">Top gross</option><option value="new">Newest</option>
        <option value="old">Oldest</option><option value="title">Title A–Z</option>
      </select>
    </div>
    <div class="chips" id="f-langs"><button class="chip" data-lang="All">All</button>
      ${langs.map(l => `<button class="chip" data-lang="${esc(l)}">${esc(l)}</button>`).join("")}</div>
    <p class="count-note" id="f-count"></p>
    <div class="grid" id="f-grid"></div>
    <button class="btn-more hidden" id="f-more">Load more</button>`;
  const $q = document.getElementById("f-q"), $sort = document.getElementById("f-sort"),
    $grid = document.getElementById("f-grid"), $count = document.getElementById("f-count"),
    $more = document.getElementById("f-more");
  $sort.value = f.sort;
  document.querySelectorAll("#f-langs .chip").forEach(c => c.classList.toggle("active", c.dataset.lang === f.lang));
  function filtered() {
    let list = state.movies.filter(m =>
      (f.lang === "All" || m.language === f.lang) &&
      (!f.q || m.title.toLowerCase().includes(f.q.toLowerCase())));
    if (f.sort === "gross") list.sort((a, b) => (b.totalGross || 0) - (a.totalGross || 0));
    if (f.sort === "new") list.sort((a, b) => (b.released || "").localeCompare(a.released || ""));
    if (f.sort === "old") list.sort((a, b) => (a.released || "").localeCompare(b.released || ""));
    if (f.sort === "title") list.sort((a, b) => a.title.localeCompare(b.title));
    return list;
  }
  function render() {
    const list = filtered();
    $count.textContent = `${list.length} films`;
    $grid.innerHTML = list.slice(0, f.shown).map(movieCard).join("") || '<div class="empty">No films match.</div>';
    $more.classList.toggle("hidden", f.shown >= list.length);
  }
  $q.addEventListener("input", () => { f.q = $q.value; f.shown = 60; render(); });
  $sort.addEventListener("change", () => { f.sort = $sort.value; render(); });
  document.querySelectorAll("#f-langs .chip").forEach(c =>
    c.addEventListener("click", () => {
      f.lang = c.dataset.lang; f.shown = 60;
      document.querySelectorAll("#f-langs .chip").forEach(x => x.classList.toggle("active", x === c));
      render();
    }));
  $more.addEventListener("click", () => { f.shown += 60; render(); });
  render();
}
function boTable(entries, firstCol) {
  if (!entries.length) return '<div class="empty">No data.</div>';
  const rows = entries.map(e => `<tr><td>${esc(e.label)}</td><td>${inr(e.gross)}</td><td>${num(e.shows)}</td><td>${num(e.sold)}</td><td>${e.occ ?? "—"}%</td><td>${inr(e.cumul)}</td></tr>`).join("");
  return `<div class="scroll-x"><table class="data"><thead><tr><th>${firstCol}</th><th>Gross</th><th>Shows</th><th>Tickets</th><th>Occ</th><th>Cumulative</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
async function viewMovie(id) {
  setNav("movies");
  await loadIndexes();
  const d = await movieDetail(id);
  if (!d) { $app.innerHTML = '<div class="empty">Movie not found.</div>'; return; }
  const m = d.movie, s = d.summary || {}, o = d.omdb || {};
  const ratings = o.ratings || {};
  const ratingChips = [
    ratings.imdb?.value ? `IMDb ${ratings.imdb.value}★ (${num(ratings.imdb.votes)})` : null,
    o.genre, o.runtime, o.rated,
  ].filter(Boolean).map(x => `<span class="chip" style="cursor:default">${esc(x)}</span>`).join("");
  const cast = (d.cast || []).map(c => `
    <a class="person-card" href="#/person/${esc(c.slug)}">
      <img loading="lazy" src="${esc(c.profile_picture_url || "")}" alt="">
      <div class="pn">${esc(c.name)}</div><div class="pc">${esc(c.character || "")}</div></a>`).join("");
  const crew = (d.crew || []).map(c => `
    <div class="crew-item"><div class="r">${esc(c.role)}</div>
      <div class="n">${(c.people || []).map(p => `<a href="#/person/${esc(p.slug)}">${esc(p.name)}</a>`).join(", ")}</div></div>`).join("");
  const companies = (d.companies || []).map(c => `<span class="chip" style="cursor:default">${esc(c.name)}</span>`).join(" ");
  const others = Object.entries(d.otherReleases || {}).sort().flatMap(([date, list]) =>
    list.map(x => `<a class="chip" href="#/movie/${x.id}" title="${esc(date)}">${esc(x.title)}</a>`)).join(" ");
  const ott = d.ott && (d.ott.releaseDate || (d.ott.platforms || []).length)
    ? `<p class="meta-line">OTT: <b>${esc(d.ott.releaseDate || "")}</b> ${(d.ott.platforms || []).map(esc).join(", ")}</p>` : "";
  $app.innerHTML = `
    <div class="detail-head">
      <img class="poster" src="${esc(poster(m.img, "w500"))}" alt="">
      <div>
        <h1>${esc(m.title)}</h1>
        <div class="meta-line"><span><b>${esc(m.language || "")}</b></span><span>Released <b>${esc(m.released || "")}</b></span>
        ${m.isRerelease ? "<span>Re-release</span>" : ""}
        ${m.imdbId ? `<a href="https://www.imdb.com/title/${esc(m.imdbId)}/" target="_blank" rel="noopener">IMDb ↗</a>` : ""}</div>
        <div class="chips" style="margin-top:10px">${ratingChips}</div>
        ${o.director ? `<p class="meta-line" style="margin-top:10px">Director <b>${esc(o.director)}</b></p>` : ""}
        ${o.plot ? `<p class="plot">${esc(o.plot)}</p>` : ""}
        ${ott}
        <div class="kpis">
          <div class="kpi"><div class="v">${inr(s.totalGross)}</div><div class="k">Kerala gross</div></div>
          <div class="kpi"><div class="v">${num(s.totalShows)}</div><div class="k">Shows</div></div>
          <div class="kpi"><div class="v">${num(s.totalSold)}</div><div class="k">Tickets sold</div></div>
          <div class="kpi"><div class="v">${s.avgOcc ?? "—"}%</div><div class="k">Avg occupancy</div></div>
          <div class="kpi"><div class="v">${s.totalDays ?? "—"}</div><div class="k">Days tracked</div></div>
          ${s.openingDay ? `<div class="kpi"><div class="v">${inr(s.openingDay.gross)}</div><div class="k">Opening day</div></div>` : ""}
        </div>
      </div>
    </div>
    ${d.archive ? `<div class="panel"><h3>Archived title</h3><p class="meta-line">Detailed daily collections for this title are archived on the source (archived ${esc(d.archive.archivedAt || "")}); summary totals above are complete.</p></div>` : ""}
    <div class="panel"><h3>Daily collections</h3>${barChart(d.daily || [], e => e.label)}${boTable(d.daily || [], "Date")}</div>
    <div class="panel"><h3>Weekly collections</h3>${barChart(d.weekly || [], e => "Week of " + e.label)}${boTable(d.weekly || [], "Week of")}</div>
    <div class="panel"><h3>Collections by district</h3>${hbarChart([...(d.districts || [])].sort((a, b) => b.gross - a.gross))}</div>
    ${cast ? `<h2 class="section">Cast</h2><div class="people-row">${cast}</div>` : ""}
    ${crew ? `<h2 class="section">Crew</h2><div class="crew-grid">${crew}</div>` : ""}
    ${companies ? `<h2 class="section">Production</h2><div class="chips">${companies}</div>` : ""}
    ${others ? `<h2 class="section">Released the same week</h2><div class="chips">${others}</div>` : ""}`;
}
async function viewPeople() {
  setNav("people");
  await loadIndexes();
  const f = state.peopleFilter;
  $app.innerHTML = `
    <h2 class="section">People</h2>
    <div class="toolbar"><input id="p-q" type="search" placeholder="Search name…" value="${esc(f.q)}">
      <select id="p-sort"><option value="gross">Top Kerala gross</option><option value="films">Most films</option><option value="name">Name A–Z</option></select></div>
    <p class="count-note" id="p-count"></p>
    <div class="grid" id="p-grid"></div>
    <button class="btn-more hidden" id="p-more">Load more</button>`;
  const $q = document.getElementById("p-q"), $sort = document.getElementById("p-sort"),
    $grid = document.getElementById("p-grid"), $count = document.getElementById("p-count"),
    $more = document.getElementById("p-more");
  $sort.value = f.sort;
  function filtered() {
    let list = state.people.filter(p => !f.q || p.name.toLowerCase().includes(f.q.toLowerCase()));
    if (f.sort === "gross") list.sort((a, b) => b.keralaGross - a.keralaGross);
    if (f.sort === "films") list.sort((a, b) => b.filmCount - a.filmCount);
    if (f.sort === "name") list.sort((a, b) => a.name.localeCompare(b.name));
    return list;
  }
  function render() {
    const list = filtered();
    $count.textContent = `${list.length} people`;
    $grid.innerHTML = list.slice(0, f.shown).map(personCard).join("") || '<div class="empty">No people match.</div>';
    $more.classList.toggle("hidden", f.shown >= list.length);
  }
  $q.addEventListener("input", () => { f.q = $q.value; f.shown = 80; render(); });
  $sort.addEventListener("change", () => { f.sort = $sort.value; render(); });
  $more.addEventListener("click", () => { f.shown += 80; render(); });
  render();
}
async function viewPerson(slug) {
  setNav("people");
  await loadIndexes();
  const d = await personDetail(slug);
  if (!d) { $app.innerHTML = '<div class="empty">Person not found.</div>'; return; }
  const p = d.person;
  const films = [...(d.films || [])].sort((a, b) => (b.year || 0) - (a.year || 0) || (b.gross_inr || 0) - (a.gross_inr || 0));
  const total = films.reduce((s, f) => s + (f.gross_inr || 0), 0);
  const biggest = films.reduce((a, f) => ((f.gross_inr || 0) > (a?.gross_inr || 0) ? f : a), null);
  const rows = films.map(f => `<tr><td><a href="#/movie/${f.movie_id}">${esc(f.title)}</a></td><td>${f.year ?? "—"}</td><td>${esc(f.kerala_gross || "—")}</td></tr>`).join("");
  $app.innerHTML = `
    <div class="detail-head" style="grid-template-columns:160px 1fr">
      <img class="poster" style="border-radius:50%;aspect-ratio:1" src="${esc(p.photo || "")}" alt="">
      <div><h1>${esc(p.name)}</h1>
        <div class="meta-line"><span><b>${esc(p.role || "")}</b></span></div>
        <div class="chips" style="margin-top:10px">${(d.tabs || []).map(t => `<span class="chip" style="cursor:default">${esc(t.label)} · ${t.count}</span>`).join("")}</div>
        <div class="kpis">
          <div class="kpi"><div class="v">${films.length}</div><div class="k">Films tracked</div></div>
          <div class="kpi"><div class="v">${inr(total)}</div><div class="k">Kerala gross (as cast/crew)</div></div>
          ${biggest ? `<div class="kpi"><div class="v">${esc(biggest.title)}</div><div class="k">Biggest film · ${inr(biggest.gross_inr)}</div></div>` : ""}
        </div></div>
    </div>
    <div class="panel"><h3>Filmography</h3><div class="scroll-x"><table class="data">
      <thead><tr><th>Film</th><th>Year</th><th>Kerala gross</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}
async function viewStats() {
  setNav("stats");
  await loadIndexes();
  const topFilms = [...state.movies].filter(m => m.totalGross).sort((a, b) => b.totalGross - a.totalGross).slice(0, 25);
  const topPeople = [...state.people].sort((a, b) => b.keralaGross - a.keralaGross).slice(0, 25);
  const byLang = {};
  state.movies.forEach(m => { const k = (m.language || "Unknown"); byLang[k] = byLang[k] || { n: 0, g: 0 }; byLang[k].n++; byLang[k].g += m.totalGross || 0; });
  const langRows = Object.entries(byLang).sort((a, b) => b[1].g - a[1].g)
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td>${inr(v.g)}</td></tr>`).join("");
  $app.innerHTML = `
    <h2 class="section">Stats</h2>
    <div class="panel"><h3>Top 25 films by Kerala gross</h3><div class="scroll-x"><table class="data">
      <thead><tr><th>Film</th><th>Released</th><th>Gross</th></tr></thead><tbody>
      ${topFilms.map(m => `<tr><td><a href="#/movie/${m.id}">${esc(m.title)}</a></td><td>${esc(m.released || "")}</td><td>${inr(m.totalGross)}</td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="panel"><h3>Top 25 people by Kerala gross</h3><div class="scroll-x"><table class="data">
      <thead><tr><th>Person</th><th>Films</th><th>Gross</th></tr></thead><tbody>
      ${topPeople.map(p => `<tr><td><a href="#/person/${esc(p.slug)}">${esc(p.name)}</a></td><td>${p.filmCount}</td><td>${inr(p.keralaGross)}</td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="panel"><h3>By language</h3><div class="scroll-x"><table class="data">
      <thead><tr><th>Language</th><th>Films</th><th>Gross</th></tr></thead><tbody>${langRows}</tbody></table></div></div>`;
}

/* ---------- router + search + theme ---------- */
function router() {
  const hash = location.hash || "#/";
  const parts = hash.replace(/^#\//, "").split("/");
  window.scrollTo(0, 0);
  if (parts[0] === "" ) viewHome();
  else if (parts[0] === "movies") viewMovies();
  else if (parts[0] === "movie" && parts[1]) viewMovie(Number(parts[1]));
  else if (parts[0] === "people") viewPeople();
  else if (parts[0] === "person" && parts[1]) viewPerson(decodeURIComponent(parts[1]));
  else if (parts[0] === "stats") viewStats();
  else viewHome();
}
window.addEventListener("hashchange", router);

const themeBtn = document.getElementById("theme-toggle");
function applyTheme(t) { document.documentElement.dataset.theme = t; localStorage.setItem("kbo-theme", t); }
applyTheme(localStorage.getItem("kbo-theme") || "dark");
themeBtn.addEventListener("click", () =>
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

const searchInput = document.getElementById("search");
const searchResults = document.getElementById("search-results");
let searchTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    const q = searchInput.value.trim().toLowerCase();
    if (q.length < 2) { searchResults.classList.add("hidden"); return; }
    await loadIndexes();
    const ms = state.movies.filter(m => m.title.toLowerCase().includes(q)).slice(0, 6);
    const ps = state.people.filter(p => p.name.toLowerCase().includes(q)).slice(0, 6);
    if (!ms.length && !ps.length) {
      searchResults.innerHTML = '<div class="empty" style="padding:14px">No matches.</div>';
    } else {
      searchResults.innerHTML =
        ms.map(m => `<a href="#/movie/${m.id}"><img src="${esc(poster(m.poster, "w185"))}" alt=""><span><span class="sr-t">${esc(m.title)}</span><br><span class="sr-s">${esc(m.released || "")} · ${inr(m.totalGross)}</span></span></a>`).join("") +
        ps.map(p => `<a href="#/person/${esc(p.slug)}"><img src="${esc(p.photo || "")}" alt=""><span><span class="sr-t">${esc(p.name)}</span><br><span class="sr-s">${esc(p.role || "")} · ${p.filmCount} films</span></span></a>`).join("");
    }
    searchResults.classList.remove("hidden");
  }, 180);
});
searchInput.addEventListener("keydown", e => {
  if (e.key === "Enter") {
    const first = searchResults.querySelector("a");
    if (first) location.hash = first.getAttribute("href");
  }
});
document.addEventListener("click", e => {
  if (!e.target.closest(".search-wrap")) searchResults.classList.add("hidden");
});
searchResults.addEventListener("click", () => searchResults.classList.add("hidden"));

loadIndexes().then(router).catch(err => {
  $app.innerHTML = `<div class="empty">Failed to load data: ${esc(err.message)}</div>`;
});
