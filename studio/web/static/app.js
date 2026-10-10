/* Animation Studio: the page. Plain JavaScript, no build step. Views: episodes (list and the scene editor),
   characters (upload, cut drawings from sheets, fix faces), backgrounds, jobs. Everything heavy is a job on the
   server (studio/web/jobs.py); the page polls it. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = $("#app");
const put = (...kids) => app.append(...kids.flat(Infinity).filter(k => k !== null && k !== undefined && k !== false));
let LIB = { characters: [], backgrounds: [], settings: [], voices: {}, tones: [] };

// ---------------------------------------------------------------- helpers
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat(Infinity)) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(k));
  return el;
}
async function api(method, url, body, raw) {
  const opt = { method, headers: {} };
  if (raw) { opt.body = raw; }
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, opt);
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && !url.startsWith("/api/login")) { if (!$(".login")) viewLogin(); throw new Error("Log in first"); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(msg, err) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 7000 : 3200);
}
async function safe(fn) { try { return await fn(); } catch (e) { toast(e.message, true); throw e; } }
const fileUrl = p => "/file/" + p.split("/").map(encodeURIComponent).join("/");
const thumbUrl = (p, hh = 320, alpha) => `/thumb?path=${encodeURIComponent(p)}&h=${hh}${alpha ? "&alpha=1" : ""}`;
const charThumb = id => `/charthumb/${id}?v=${Date.now() >> 16}`;
const charOf = id => LIB.characters.find(c => c.id === id);
const fmtT = s => s == null ? "" : `${s.toFixed(2)}s`;

function modal(title, body, wide) {
  const m = $("#modal");
  const b = $(".modal-body", m);
  b.innerHTML = "";
  b.append(h("h2", {}, title), body);
  $(".modal-box", m).style.width = wide ? "min(1200px, 100%)" : "min(760px, 100%)";
  m.classList.remove("hidden");
  return m;
}
function closeModal() { $("#modal").classList.add("hidden"); $(".modal-body", $("#modal")).innerHTML = ""; }
$("#modal .modal-x").onclick = closeModal;
$("#modal").addEventListener("mousedown", e => { if (e.target.id === "modal") closeModal(); });

function dropZone(text, accept, onFile) {
  const inp = h("input", { type: "file", accept, class: "hidden" });
  const z = h("div", { class: "drop" }, text, inp);
  z.onclick = () => inp.click();
  inp.onchange = () => inp.files[0] && onFile(inp.files[0], z);
  z.ondragover = e => { e.preventDefault(); z.classList.add("over"); };
  z.ondragleave = () => z.classList.remove("over");
  z.ondrop = e => { e.preventDefault(); z.classList.remove("over"); e.dataTransfer.files[0] && onFile(e.dataTransfer.files[0], z); };
  return z;
}

async function loadLib() { LIB = await api("GET", "/api/library"); }

// ---------------------------------------------------------------- jobs
const JOBS = { list: [], watchers: new Map() };   // job id -> callback(job) on every poll
async function pollJobs() {
  try {
    JOBS.list = await api("GET", "/api/jobs");
    const busy = JOBS.list.filter(j => j.state === "running" || j.state === "queued").length;
    const b = $("#jobs-badge");
    b.textContent = busy; b.classList.toggle("hidden", !busy);
    for (const [id, cb] of JOBS.watchers) {
      const j = await api("GET", `/api/jobs/${id}?tail=40`);
      cb(j);
      if (!["running", "queued"].includes(j.state)) JOBS.watchers.delete(id);
    }
  } catch (e) { /* the server may be restarting */ }
  setTimeout(pollJobs, JOBS.watchers.size ? 1500 : 4000);
}
function watch(id, cb) { JOBS.watchers.set(id, cb); }

function jobView(j, onCancel) {
  const steps = h("div", { class: "steps" }, j.steps.map((s, i) => h("span", {
    class: i < j.step || j.state === "done" ? "done" : i === j.step ? (j.state === "failed" ? "bad" : j.state === "running" ? "now" : "") : ""
  }, s)));
  const state = { queued: "Waiting for the engine", running: "Working", done: "Done", failed: "Failed", cancelled: "Cancelled" }[j.state];
  return h("div", {},
    h("div", { class: "row" }, h("strong", {}, j.title), h("span", { class: "tag " + (j.state === "done" ? "ok" : j.state === "failed" ? "bad" : "warn") }, state),
      h("span", { class: "spacer" }),
      ["running", "queued"].includes(j.state) ? h("button", { class: "btn small", onclick: async () => { await api("POST", `/api/jobs/${j.id}/cancel`); onCancel && onCancel(); } }, "Cancel") : null),
    steps, j.error ? h("div", { class: "tag bad" }, j.error) : null,
    h("pre", { class: "log" }, (j.log || []).join("\n")));
}

// ---------------------------------------------------------------- router
const VIEWS = { produce: viewProduce, shows: viewShows, show: viewShow, episodes: viewEpisodes, episode: viewEpisode, characters: viewCharacters, character: viewCharacter,
  backgrounds: viewBackgrounds, jobs: viewJobs };
async function route() {
  document.body.classList.remove("locked");
  const [v, arg] = (location.hash.slice(1) || "produce").split("/");
  $$("nav a").forEach(a => a.classList.toggle("on", a.dataset.view === v || (v === "episode" && a.dataset.view === "episodes") || (v === "character" && a.dataset.view === "characters") || ((v === "show" || v === "shows") && a.dataset.view === "episodes")));
  JOBS.watchers.clear();
  app.innerHTML = "";
  try { await (VIEWS[v] || viewProduce)(arg && decodeURIComponent(arg)); }
  catch (e) { if (e.message !== "Log in first") put(h("div", { class: "empty" }, e.message)); }
}
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- episodes
const KIND = name => {
  const e = (name.match(/\.[a-z0-9]+$/i) || [""])[0].toLowerCase();
  if ([".md", ".txt", ".fountain", ".docx", ".pdf"].includes(e)) return "script / notes";
  if ([".png", ".jpg", ".jpeg", ".webp"].includes(e)) return "picture";
  if ([".wav", ".mp3", ".m4a", ".flac", ".ogg"].includes(e)) return "recording";
  if (e === ".zip") return "zip";
  return "other";
};

// a pack's files, sent in 8 MB pieces: a phone's upload survives a dropped connection (each piece is retried and
// the server says how much it already has) and no host limit on a request's size gets in the way
async function uploadPack(base, files, status) {
  const CH = 8 * 1024 * 1024;
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    let off = 0, tries = 0;
    while (off < f.size || (f.size === 0 && off === 0)) {
      const pct = f.size ? Math.round(100 * off / f.size) : 0;
      status(`Uploading ${i + 1} of ${files.length}: ${f.name} (${pct}%)`);
      try {
        const r = await api("POST", `${base}/pack?filename=${encodeURIComponent(f.name)}&offset=${off}&total=${f.size}`, undefined, f.slice(off, off + CH));
        off = r.offset; tries = 0;
        if (r.file || f.size === 0) break;
      } catch (e) {
        if (++tries > 6 || /log in|too big|no such/.test(e.message)) throw e;
        status(`Connection lost: trying again (${tries})...`);
        await new Promise(res => setTimeout(res, 1500 * tries));
      }
    }
  }
  status("Uploaded.");
}

function filePicker(title, sub) {
  let files = [];
  const list = h("div", { class: "packlist" });
  const inp = h("input", { type: "file", multiple: true, class: "hidden" });
  const zone = h("div", { class: "drop big" }, h("div", { class: "drop-title" }, title), h("div", {}, sub), inp);
  const listeners = [];
  const add = fs => { for (const f of fs) if (!files.some(x => x.name === f.name && x.size === f.size)) files.push(f); show(); };
  zone.onclick = () => inp.click();
  inp.onchange = () => { add(inp.files); inp.value = ""; };
  zone.ondragover = e => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = e => { e.preventDefault(); zone.classList.remove("over"); add(e.dataTransfer.files); };
  function show() {
    list.innerHTML = "";
    const count = {};
    files.forEach(f => count[KIND(f.name)] = (count[KIND(f.name)] || 0) + 1);
    const mb = files.reduce((a, f) => a + f.size, 0) / 1048576;
    list.append(h("div", { class: "row" }, Object.entries(count).map(([k, n]) => h("span", { class: "tag ok" }, `${n} ${k}${n > 1 ? "s" : ""}`)),
      files.length ? h("span", { class: "hint" }, `${mb.toFixed(mb < 10 ? 1 : 0)} MB`) : null,
      files.length ? h("button", { class: "btn small ghost", onclick: () => { files = []; show(); } }, "Clear") : null));
    if (files.length) list.append(h("div", { class: "hint filenames" }, files.map(f => f.name).join(" · ")));
    listeners.forEach(fn => fn(files));
  }
  return { el: h("div", {}, zone, list), files: () => files, onChange: fn => listeners.push(fn) };
}

const QUALITY = () => h("select", {}, h("option", { value: "final" }, "Final film (1920 x 1080)"), h("option", { value: "draft" }, "Quick draft (960 x 540)"));

// an episode's directive and assets -> produced (in a show when given)
function packPanel(show, shows) {
  const pick = filePicker(show ? `New episode of ${show.title}` : "The director's zip and production notes",
    "The director's zip (script, notes, voice recordings, any pictures) and the production notes, as they came. Tap to choose files.");
  const showSel = !show && shows && shows.length ? h("select", {}, h("option", { value: "" }, "Not part of a show"),
    shows.map(x => h("option", { value: x.slug }, `Episode of ${x.title}`))) : null;
  const title = h("input", { type: "text", placeholder: "Title (optional: read from the script)" });
  const quality = QUALITY();
  const status = h("div", { class: "hint" });
  const go = h("button", { class: "btn primary", disabled: true }, "Produce the episode");
  pick.onChange(fs => go.disabled = !fs.length);
  go.onclick = () => safe(async () => {
    go.disabled = true;
    const { slug } = await api("POST", "/api/productions", { title: title.value, show: show ? show.slug : (showSel ? showSel.value : "") });
    await uploadPack(`/api/episodes/${slug}`, pick.files(), t => status.textContent = t);
    const r = await api("POST", `/api/episodes/${slug}/produce`, { quality: quality.value });
    sessionStorage.setItem("follow-" + slug, r.job);
    location.hash = "episode/" + slug;
  }).catch(() => { go.disabled = false; });
  return h("div", { class: "panel hero" },
    h("h2", {}, show ? "Produce an episode" : "Produce it"),
    h("p", { class: "hint" }, show
      ? `Characters and sets from ${show.title} are used automatically, with the voices they always have. Only upload what's new for this episode: the script, plus pictures of new characters, new sets and the actors' recordings.`
      : "The studio finds the script among the documents (scenes, lines, deliveries, stage directions), casts every speaker from the cast library, gives each scene its set, gives each recording to whoever it is named for or whoever's lines it hears, stages the scenes, then cuts out the characters, syncs the lips, directs, mixes and renders. Anyone it can't find, it asks you for."),
    pick.el, h("div", { class: "row", style: { marginTop: "10px" } }, title, showSel, quality, h("span", { class: "spacer" }), go), status);
}

// ---------------------------------------------------------------- shows
async function viewShows() {
  const shows = await api("GET", "/api/shows");
  const pick = filePicker("Drop the show's directive here",
    "The show bible or directive (who's in it, where it's set), a picture of each character named after them, and the sets. Or one zip. Tap to choose files.");
  const title = h("input", { type: "text", placeholder: "Show title (optional: read from the directive)" });
  const status = h("div", { class: "hint" });
  const go = h("button", { class: "btn primary", disabled: true }, "Create the show");
  pick.onChange(fs => go.disabled = !fs.length);
  go.onclick = () => safe(async () => {
    go.disabled = true;
    const { slug } = await api("POST", "/api/shows", { title: title.value });
    await uploadPack(`/api/shows/${slug}`, pick.files(), t => status.textContent = t);
    const r = await api("POST", `/api/shows/${slug}/read`);
    sessionStorage.setItem("follow-show-" + slug, r.job);
    location.hash = "show/" + slug;
  }).catch(() => { go.disabled = false; });
  put(h("h1", {}, "Shows"),
    h("p", { class: "sub" }, "A show keeps its cast, sets and voices. Set it up once from its directive, then each episode is just its script."),
    h("div", { class: "grid wide" }, shows.map(sh => h("div", { class: "card", onclick: () => location.hash = "show/" + sh.slug },
      h("div", { class: "showcast" }, sh.cast.slice(0, 5).map(id => h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(id)})` } }))),
      h("div", { class: "meta" }, h("div", { class: "name" }, sh.title), h("div", { class: "small" }, sh.tagline || " "),
        h("span", { class: "tag" }, `${sh.cast.length} cast`), h("span", { class: "tag" }, `${sh.sets.length} set${sh.sets.length === 1 ? "" : "s"}`),
        h("span", { class: "tag ok" }, `${sh.episodes.length} episode${sh.episodes.length === 1 ? "" : "s"}`))))),
    shows.length ? null : h("div", { class: "empty" }, "No shows yet: create one below."),
    h("div", { class: "panel hero" }, h("h2", {}, "Create a show"), pick.el,
      h("div", { class: "row", style: { marginTop: "10px" } }, title, h("span", { class: "spacer" }), go), status));
}

async function viewShow(slug) {
  await loadLib();
  let sh = await api("GET", `/api/shows/${slug}`);
  const jobBox = h("div");
  const body = h("div");
  put(h("div", { class: "row" }, h("a", { href: "#shows", class: "hint" }, "← Shows")), body);
  async function render() {
    sh = await api("GET", `/api/shows/${slug}`);
    const rep = await api("GET", `/api/shows/${slug}/report`);
    body.innerHTML = "";
    const more = h("input", { type: "file", multiple: true, class: "hidden", onchange: e => safe(async () => {
      const fs = [...e.target.files];
      await uploadPack(`/api/shows/${slug}`, fs, t => toast(t));
      follow((await api("POST", `/api/shows/${slug}/read`)).job);
    }) });
    const fld = (label, key, ph) => h("label", { class: "f" }, label, h("input", { type: "text", value: sh[key] || "", placeholder: ph,
      onchange: e => safe(async () => { sh[key] = e.target.value; await api("PUT", `/api/shows/${slug}`, sh); toast("Saved"); }) }));
    body.append(
      h("div", { class: "row" }, h("h1", {}, sh.title || slug), h("span", { class: "spacer" }),
        h("button", { class: "btn small ghost", onclick: () => { if (confirm("Delete this show? Its episodes are kept.")) safe(async () => { await api("DELETE", `/api/shows/${slug}`); location.hash = "shows"; }); } }, "Delete show")),
      h("p", { class: "sub" }, sh.tagline || `shows/${slug}/`),
      jobBox,
      packPanel(sh),
      h("div", { class: "panel" }, h("h2", {}, "Episodes"),
        sh.episodes.length ? h("div", { class: "grid wide" }, sh.episodes.map(e => h("div", { class: "card", onclick: () => location.hash = "episode/" + e.slug },
          e.video || e.preview ? h("video", { src: fileUrl(e.video || e.preview) + "#t=6", preload: "metadata", muted: true, playsinline: true, style: { aspectRatio: "16/9", borderRadius: 0 } }) : h("div", { class: "pic land", style: { background: "#26292f" } }),
          h("div", { class: "meta" }, h("div", { class: "name" }, e.title),
            e.video ? h("span", { class: "tag ok" }, "finished") : e.preview ? h("span", { class: "tag warn" }, "draft") : h("span", { class: "tag" }, "not made yet")))))
          : h("div", { class: "empty" }, "No episodes yet: produce the first one above.")),
      h("div", { class: "panel" }, h("div", { class: "row" }, h("h2", {}, "Cast"), h("span", { class: "spacer" }),
          h("button", { class: "btn small", onclick: () => more.click() }, "Add to the show"), more),
        h("p", { class: "hint" }, "Add pictures (named after the character), sets or an updated directive: the show is read again."),
        h("div", { class: "grid" }, sh.cast.map(c => {
          const ch = charOf(c.id) || { name: c.id };
          const v = c.voice || {};
          return h("div", { class: "card", onclick: () => location.hash = "character/" + c.id },
            h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
            h("div", { class: "meta" }, h("div", { class: "name" }, ch.name),
              h("select", { onclick: e => e.stopPropagation(), onchange: e => safe(async () => { c.voice = { kind: "tts", voice: e.target.value, speed: 1.0 }; await api("PUT", `/api/shows/${slug}`, sh); toast(`${ch.name}'s stand-in voice: ${LIB.voices[e.target.value]}`); }) },
                Object.entries(LIB.voices).map(([k, n]) => h("option", { value: k, selected: k === v.voice }, n)))));
        })),
        rep && (rep.missing || []).length ? h("div", { class: "tag bad", style: { marginTop: "8px", padding: "6px 10px" } }, `Named in the directive but no picture or library character: ${rep.missing.join(", ")}`) : null,
        rep && (rep.warnings || []).length ? rep.warnings.map(w => h("div", { class: "hint" }, "• " + w)) : null),
      h("div", { class: "panel" }, h("h2", {}, "Sets"), h("div", { class: "grid wide" }, (sh.sets || []).map(b => h("div", { class: "card", onclick: () => window.open(fileUrl(`library/backgrounds/${b}.png`)) },
        h("div", { class: "pic land", style: { backgroundImage: `url(${thumbUrl(`library/backgrounds/${b}.png`, 240)})` } }), h("div", { class: "meta" }, h("div", { class: "small" }, b))))),
        (sh.sets || []).length ? null : h("div", { class: "hint" }, "No sets of its own yet: episodes use the library's.")),
      h("div", { class: "panel" }, h("h2", {}, "Show details"), h("div", { class: "fields" }, fld("Title", "title", "On every title card"), fld("Tagline", "tagline", "")),
        h("div", { class: "hint", style: { marginTop: "8px" } }, "Directive: " + ((sh.pack || []).join(", ") || "none"))));
  }
  function follow(id) {
    watch(id, async j => {
      jobBox.innerHTML = ""; jobBox.append(h("div", { class: "panel" }, jobView(j)));
      if (j.state === "done") { jobBox.innerHTML = ""; toast("The show is ready"); await loadLib(); render(); }
      if (j.state === "failed") toast(j.error, true);
    });
  }
  await render();
  const want = sessionStorage.getItem("follow-show-" + slug);
  const live = (await api("GET", "/api/jobs")).find(j => j.ref === slug && (j.id === want || ["running", "queued"].includes(j.state)));
  if (live) follow(live.id);
}

// ---------------------------------------------------------------- login
function viewLogin() {
  const pw = h("input", { type: "password", placeholder: "Password", autocomplete: "current-password" });
  const go = () => safe(async () => { await api("POST", "/api/login", { password: pw.value }); route(); });
  pw.onkeydown = e => { if (e.key === "Enter") go(); };
  app.innerHTML = "";
  document.body.classList.add("locked");
  put(h("div", { class: "login" }, h("img", { src: "/static/icon-192.png", alt: "" }), h("h1", {}, "Animation Studio"),
    h("p", { class: "sub" }, "Enter the studio's password."), pw, h("button", { class: "btn primary", onclick: go }, "Open the studio")));
  setTimeout(() => pw.focus(), 50);
}

async function viewEpisodes() {
  const eps = await api("GET", "/api/episodes");
  const title = h("input", { type: "text", placeholder: "Title of an episode to build by hand" });
  put(
    h("h1", {}, "Episodes"),
    h("p", { class: "sub" }, "Everything produced, newest first. New production: the Produce tab."),
    h("div", { class: "row", style: { marginBottom: "14px" } }, h("a", { class: "btn", href: "#produce" }, "+ New production"), h("a", { class: "btn", href: "#shows" }, "Shows")),
    h("div", { class: "panel row" }, title, h("button", { class: "btn", onclick: () => safe(async () => {
      const r = await api("POST", "/api/episodes", { title: title.value });
      location.hash = "episode/" + r.slug;
    }) }, "New empty episode"), h("span", { class: "hint" }, "Or start empty and set it up yourself: pick sets, cast, write lines.")),
    h("div", { class: "grid wide" }, eps.map(e => h("div", { class: "card", onclick: () => location.hash = "episode/" + e.slug },
      e.video || e.preview ? h("video", { src: fileUrl(e.video || e.preview) + "#t=6", preload: "metadata", muted: true, style: { aspectRatio: "16/9", borderRadius: 0 } }) : h("div", { class: "pic land", style: { background: "#26292f" } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, e.title),
        h("span", { class: "tag" + (e.web ? " ok" : "") }, e.web ? "web studio" : "directed by hand"),
        e.video ? h("span", { class: "tag ok" }, "finished") : e.preview ? h("span", { class: "tag warn" }, "draft") : h("span", { class: "tag" }, "not made yet"))))));
}

async function viewEpisode(slug) {
  await loadLib();
  let ep;
  try { ep = await api("GET", `/api/episodes/${slug}`); }
  catch (e) {                                     // a hand-directed episode: watch only
    const all = await api("GET", "/api/episodes");
    const x = all.find(a => a.slug === slug);
    put(h("h1", {}, x ? x.title : slug), h("p", { class: "sub" }, e.message),
      x && x.video ? h("video", { src: fileUrl(x.video), controls: true }) : null);
    return;
  }
  let outputs = {};
  let cur = 0;                                    // the scene being staged
  let selected = null;
  let saveTimer = null;
  const save = (now) => {
    clearTimeout(saveTimer);
    const go = async () => { const r = await safe(() => api("PUT", `/api/episodes/${slug}`, ep)); ep.lines = r.lines; $("#saved").textContent = "Saved"; renderLines(); };
    $("#saved").textContent = "Saving...";
    if (now) return go();
    saveTimer = setTimeout(go, 600);
  };
  const scene = () => ep.scenes[cur];
  const nameOf = id => (charOf(id) || { name: id }).name;

  // who stands in a scene: its staged cast and everyone who speaks in it, spread out where not placed
  function staged(k) {
    const sc = ep.scenes[k];
    sc.stage = sc.stage || {};
    for (const ln of ep.lines) if (ln.scene === k && ln.who && !sc.stage[ln.who]) {
      const before = k && ep.scenes[k - 1].background === sc.background && (ep.scenes[k - 1].stage || {})[ln.who];
      sc.stage[ln.who] = before ? { ...before } : {};        // the same set as before: they stay where they were
    }
    const ids = Object.keys(sc.stage).filter(id => ep.cast.some(c => c.id === id));
    const free = ids.filter(id => sc.stage[id].x === undefined);
    free.forEach((id, i) => { sc.stage[id].x = free.length === 1 ? 0.5 : +(0.22 + 0.56 * i / (free.length - 1)).toFixed(3); });
    for (const id of ids) { sc.stage[id].floor ??= 0.93; sc.stage[id].height ??= 0.62; }
    return ids;
  }

  // header
  const fld = (label, key, ph) => h("label", { class: "f" }, label, h("input", { type: "text", value: ep[key] || "", placeholder: ph, oninput: e => { ep[key] = e.target.value; save(); } }));
  put(
    h("div", { class: "row" }, h("h1", {}, ep.title || slug), h("span", { class: "spacer" }), h("span", { id: "saved", class: "hint" }, "Saved"),
      h("button", { class: "btn ghost small", onclick: () => { if (confirm("Delete this episode and everything made for it?")) safe(async () => { await api("DELETE", `/api/episodes/${slug}`); location.hash = "episodes"; }); } }, "Delete")),
    h("p", { class: "sub" }, `episodes/${slug}/`));
  const reportBox = h("div");
  put(reportBox);
  const makePanel = h("div", { class: "panel" });
  put(makePanel);
  put(h("div", { class: "panel" }, h("div", { class: "fields" },
    fld("Title", "title", "The title card"), fld("Show", "show", "Above the title (optional)"), fld("Tagline", "tagline", "Under the title (optional)"))));

  const cols = h("div", { class: "cols" });
  const left = h("div"), right = h("div");
  cols.append(left, right);
  put(cols);

  // ---- the import report
  async function renderReport() {
    const r = await api("GET", `/api/episodes/${slug}/report`);
    reportBox.innerHTML = "";
    if (!r || !r.script && !(r.missing || []).length) return;
    const chars = Object.entries(r.characters || {}).map(([n, c]) => h("div", {}, h("strong", {}, n), ` = ${c.name} `, h("span", { class: "tag" }, c.source)));
    const voices = Object.entries(r.voices || {}).map(([n, vs]) => h("div", {}, h("strong", {}, n), ": ",
      vs.map(v => v.stand_in ? h("span", { class: "tag warn" }, `stand-in voice (${LIB.voices[v.stand_in] || v.stand_in})`) : h("span", { class: "tag ok" }, `${v.file} (${v.by})`))));
    const more = h("input", { type: "file", multiple: true, class: "hidden", onchange: e => safe(async () => {
      await uploadPack(`/api/episodes/${slug}`, [...e.target.files], t => toast(t)); toast("Added to the pack: produce again to use them");
    }) });
    reportBox.append(h("div", { class: "panel" },
      h("div", { class: "row" }, h("h2", {}, "What the studio worked out from the pack"), h("span", { class: "spacer" }),
        h("button", { class: "btn small", onclick: () => more.click() }, "Add files to the pack"), more,
        h("button", { class: "btn small", title: "Reads the pack again: the cast, sets and lines are worked out afresh", onclick: () => produce("final") }, "Read the pack again and produce")),
      (r.missing || []).length ? h("div", { class: "missing" }, h("strong", {}, "Not in the cast library yet: add a picture of each, then produce again."),
        r.missing.map(n => {
          const nm = h("input", { type: "text", value: n[0] + n.slice(1).toLowerCase(), placeholder: "Their full name" });
          const f = h("input", { type: "file", accept: "image/*", class: "hidden", onchange: e => safe(async () => {
            const file = e.target.files[0]; if (!file) return;
            await api("POST", `/api/characters?name=${encodeURIComponent(nm.value)}&filename=${encodeURIComponent(file.name)}`, undefined, file);
            toast(`${nm.value} added`); await loadLib(); row.remove();
          }) });
          const row = h("div", { class: "row" }, h("span", { class: "tag bad" }, n), nm, h("button", { class: "btn small", onclick: () => f.click() }, "Add their picture"), f);
          return row;
        }), h("button", { class: "btn primary small", onclick: () => produce("final") }, "Produce again")) : null,
      h("div", { class: "cols", style: { marginTop: "8px" } },
        h("div", {}, h("h3", {}, "Script"), h("div", {}, r.script || "none"), h("h3", { style: { marginTop: "10px" } }, "Cast"), chars,
          h("h3", { style: { marginTop: "10px" } }, "Scenes"), (r.scenes || []).map((s, i) => h("div", {}, `${i + 1}. ${s.name || s.location || "scene"} → `, h("span", { class: "tag" }, s.set)))),
        h("div", {}, h("h3", {}, "Voices"), voices,
          (r.warnings || []).length ? [h("h3", { style: { marginTop: "10px" } }, "Notes"), r.warnings.map(w => h("div", { class: "hint" }, "• " + w))] : null))));
  }

  // ---- the set and the staging
  const sceneTabs = h("div", { class: "row tabs" });
  const sceneFields = h("div", { class: "fields", style: { margin: "10px 0" } });
  const stage = h("div", { class: "stage" });
  const sizeRow = h("div", { class: "row", style: { marginTop: "8px" } });
  left.append(h("div", { class: "panel" },
    h("div", { class: "row" }, h("h2", {}, "Scenes and sets"), h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: pickBackground }, "Change set"),
      h("button", { class: "btn small", onclick: () => { ep.scenes.push({ name: "", background: scene().background, place: "", stage: {} }); cur = ep.scenes.length - 1; save(); renderStage(); renderLines(); } }, "+ Scene")),
    sceneTabs, sceneFields, stage, sizeRow,
    h("p", { class: "hint" }, "Drag the characters to where they stand in this scene; their feet go where you drop them. The camera works out every shot from this.")));

  function drawingKey(c) { return c.drawing || "front"; }
  function actorImg(c) {
    const ch = charOf(c.id);
    const d = ch && ch.drawings.find(x => x.name === drawingKey(c));
    return d && d.built ? thumbUrl(`build/film/${c.id}/${drawingKey(c)}.png`, 700, true) : charThumb(c.id);
  }
  function renderStage() {
    cur = Math.min(cur, ep.scenes.length - 1);
    sceneTabs.innerHTML = "";
    ep.scenes.forEach((sc, k) => sceneTabs.append(h("button", { class: "btn small" + (k === cur ? " primary" : ""), onclick: () => { cur = k; selected = null; renderStage(); } },
      `${k + 1}${sc.name ? " · " + sc.name : ""}`)));
    if (ep.scenes.length > 1) sceneTabs.append(h("span", { class: "spacer" }), h("button", { class: "btn small ghost", onclick: () => {
      if (!confirm("Delete this scene? Its lines move to the scene before it.")) return;
      ep.lines.forEach(ln => { if (ln.scene === cur) ln.scene = Math.max(0, cur - 1); else if (ln.scene > cur) ln.scene -= 1; });
      ep.scenes.splice(cur, 1); cur = Math.max(0, cur - 1); save(); renderStage(); renderLines();
    } }, "Delete scene"));
    sceneFields.innerHTML = "";
    const sc = scene();
    sceneFields.append(
      h("label", { class: "f" }, "Scene name", h("input", { type: "text", value: sc.name || "", oninput: e => { sc.name = e.target.value; save(); } })),
      h("label", { class: "f" }, "Caption on its opening shot", h("input", { type: "text", value: sc.place || "", placeholder: "Where we are (optional)", oninput: e => { sc.place = e.target.value; save(); } })),
      h("label", { class: "f" }, "Set", h("div", { class: "hint" }, sc.background || "none chosen")));
    stage.innerHTML = "";
    stage.style.backgroundImage = sc.background ? `url(${thumbUrl(`library/backgrounds/${sc.background}.png`, 720)})` : "";
    const ids = staged(cur);
    for (const id of ids) {
      const c = ep.cast.find(x => x.id === id);
      const p = sc.stage[id];
      const a = h("div", { class: "actor" + (id === selected ? " sel" : ""), style: { left: `${p.x * 100}%`, top: `${(p.floor - p.height) * 100}%`, height: `${p.height * 100}%` } },
        h("img", { src: actorImg(c), alt: id }), h("div", { class: "lbl" }, nameOf(id)));
      a.onpointerdown = e => {
        e.preventDefault(); selected = id; $$(".actor", stage).forEach(x => x.classList.remove("sel")); a.classList.add("sel"); renderSize();
        a.setPointerCapture(e.pointerId);
        const r = stage.getBoundingClientRect();
        a.onpointermove = ev => {
          p.x = Math.round(Math.min(0.98, Math.max(0.02, (ev.clientX - r.left) / r.width)) * 1000) / 1000;
          p.floor = Math.round(Math.min(1.2, Math.max(p.height * 0.3, (ev.clientY - r.top) / r.height)) * 1000) / 1000;
          a.style.left = `${p.x * 100}%`; a.style.top = `${(p.floor - p.height) * 100}%`;
        };
        a.onpointerup = () => { a.onpointermove = null; save(); };
      };
      stage.append(a);
    }
    renderSize();
  }
  function renderSize() {
    sizeRow.innerHTML = "";
    const sc = scene();
    if (!selected || !sc.stage[selected]) { sizeRow.append(h("span", { class: "hint" }, "Click a character to size them or take them out of the scene.")); return; }
    const p = sc.stage[selected];
    const speaks = ep.lines.some(ln => ln.scene === cur && ln.who === selected);
    sizeRow.append(h("strong", {}, nameOf(selected)), h("label", { class: "row hint" }, "Size",
      h("input", { type: "range", min: 0.15, max: 1.4, step: 0.01, value: p.height, oninput: e => {
        p.height = +e.target.value; const a = $$(".actor", stage).find(x => x.classList.contains("sel"));
        if (a) { a.style.height = `${p.height * 100}%`; a.style.top = `${(p.floor - p.height) * 100}%`; } save();
      } })), h("span", { class: "spacer" }),
      speaks ? h("span", { class: "hint" }, "speaks in this scene") : h("button", { class: "btn small ghost", onclick: () => { delete sc.stage[selected]; selected = null; save(); renderStage(); } }, "Take out of this scene"),
      h("select", { onchange: e => { if (e.target.value) { sc.stage[e.target.value] = {}; save(); renderStage(); } } },
        h("option", { value: "" }, "+ Put someone else in"), ep.cast.filter(c => !sc.stage[c.id]).map(c => h("option", { value: c.id }, nameOf(c.id)))));
  }
  function pickBackground() {
    const grid = h("div", { class: "grid wide" }, LIB.backgrounds.filter(b => b.orientation === "landscape").map(b =>
      h("div", { class: "card" + (b.id === scene().background ? " sel" : ""), onclick: () => { scene().background = b.id; save(); renderStage(); closeModal(); } },
        h("div", { class: "pic land", style: { backgroundImage: `url(${thumbUrl(b.path, 240)})` } }),
        h("div", { class: "meta" }, h("div", { class: "name" }, b.title), h("div", { class: "small" }, b.id)))));
    modal(`The set for scene ${cur + 1}`, h("div", {}, h("p", { class: "hint" }, "Landscape sets only: the film is 16:9. Add your own on the Backgrounds page."), grid), true);
  }

  // ---- the cast
  const castPanel = h("div", { class: "panel" });
  right.append(castPanel);
  function renderCast() {
    castPanel.innerHTML = "";
    castPanel.append(h("div", { class: "row" }, h("h2", {}, "Cast"), h("span", { class: "spacer" }), h("button", { class: "btn small primary", onclick: addCast }, "+ Add character")));
    if (!ep.cast.length) castPanel.append(h("div", { class: "empty" }, "Nobody is cast yet."));
    for (const c of ep.cast) {
      const ch = charOf(c.id) || { name: c.id, drawings: [] };
      c.voice = c.voice || { kind: "tts", voice: "bm_george", speed: 1.0 };
      const v = c.voice;
      const set = (k, val) => { c[k] = val; save(); };
      const drawSel = h("select", { onchange: e => { set("drawing", e.target.value); renderStage(); } },
        ch.drawings.map(d => h("option", { value: d.name, selected: d.name === drawingKey(c) }, `${d.name}${d.built ? "" : " (not cut yet)"}`)));
      const kindSel = h("select", { onchange: e => { v.kind = e.target.value; save(); renderCast(); } },
        h("option", { value: "tts", selected: v.kind === "tts" }, "Stand-in voice"), h("option", { value: "recording", selected: v.kind === "recording" }, "Their recording"));
      let voiceBits;
      if (v.kind === "tts") {
        voiceBits = [h("label", { class: "f" }, "Voice", h("select", { onchange: e => { v.voice = e.target.value; save(); } },
          Object.entries(LIB.voices).map(([k, n]) => h("option", { value: k, selected: k === v.voice }, n)))),
          h("label", { class: "f" }, `Pace ${(+v.speed || 1).toFixed(2)}`, h("input", { type: "range", min: 0.8, max: 1.25, step: 0.05, value: v.speed || 1,
            oninput: e => { v.speed = +e.target.value; e.target.previousSibling.textContent = `Pace ${v.speed.toFixed(2)}`; save(); } }))];
      } else {
        const fs = v.files || [];
        const has = fs.length && fs.every(f => (ep._files || []).includes(f));
        const inp = h("input", { type: "file", accept: "audio/*", class: "hidden", onchange: e => uploadVoice(c, e.target.files[0]) });
        voiceBits = [h("label", { class: "f", style: { gridColumn: "1 / -1" } }, "Recordings", h("div", { class: "row" },
          has ? fs.map(f => h("span", { class: "tag ok" }, f)) : h("span", { class: "tag bad" }, "none yet"),
          h("button", { class: "btn small", onclick: () => inp.click() }, has ? "Replace" : "Upload"), inp))];
      }
      castPanel.append(h("div", { class: "castrow" },
        h("div", { class: "face", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
        h("div", {},
          h("div", { class: "row" }, h("strong", {}, ch.name), ch.style === "provisional" ? h("span", { class: "tag warn" }, "stand-in kit") : null,
            h("a", { class: "hint", href: "#character/" + c.id }, "drawings"), h("span", { class: "spacer" }),
            h("button", { class: "btn small ghost", title: "Remove from the episode", onclick: () => {
              ep.cast = ep.cast.filter(x => x !== c); ep.scenes.forEach(s => s.stage && delete s.stage[c.id]); save(); renderCast(); renderStage(); renderLines(); } }, "Remove")),
          h("div", { class: "fields" },
            h("label", { class: "f" }, "Drawing", drawSel), h("label", { class: "f" }, "Voice from", kindSel), ...voiceBits,
            h("label", { class: "f" }, "Caption", h("input", { type: "text", value: c.caption || "", placeholder: ch.role || "Under their name", oninput: e => set("caption", e.target.value) })),
            h("label", { class: "f" }, "Resting face", h("select", { onchange: e => set("mood", e.target.value) },
              h("option", { value: "" }, "neutral"), LIB.tones.map(t => h("option", { value: t, selected: t === c.mood }, t))))))));
    }
  }
  async function uploadVoice(c, f) {
    if (!f) return;
    toast("Uploading " + f.name + "...");
    const r = await safe(() => api("POST", `/api/episodes/${slug}/voice?cid=${c.id}&filename=${encodeURIComponent(f.name)}`, undefined, f));
    ep = await api("GET", `/api/episodes/${slug}`);
    toast("Recording filed as voiceovers/" + r.file);
    renderCast();
  }
  function addCast() {
    const usable = LIB.characters.filter(c => c.drawings.length && !ep.cast.some(x => x.id === c.id));
    const grid = h("div", { class: "grid" }, usable.map(c => h("div", { class: "card", onclick: () => {
      const n = ep.cast.length;
      ep.cast.push({ id: c.id, drawing: c.drawings[0].name, voice: { kind: "tts", voice: Object.keys(LIB.voices)[n % 4] || "bm_george", speed: 1.0 }, caption: "", mood: "" });
      scene().stage = scene().stage || {}; scene().stage[c.id] = {};
      selected = c.id;
      save(); renderCast(); renderStage(); renderLines(); closeModal();
    } }, h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, c.name), h("div", { class: "small" }, c.role),
        c.drawings.some(d => d.built) ? h("span", { class: "tag ok" }, "ready") : h("span", { class: "tag" }, "cut on first use")))));
    modal("Add a character", h("div", {}, h("p", { class: "hint" }, `They join scene ${cur + 1}. Upload new characters on the Characters page.`), grid), true);
  }

  // ---- the script
  const linesPanel = h("div", { class: "panel" });
  put(linesPanel);
  const blank = (k, who) => ({ who, to: "", text: "", tone: "", pause: "", scene: k });
  function renderLines() {
    linesPanel.innerHTML = "";
    const durs = outputs.lines || {};
    linesPanel.append(h("div", { class: "row" }, h("h2", {}, "Script"), h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: pasteScript }, "Paste lines")));
    if (!ep.cast.length) { linesPanel.append(h("div", { class: "empty" }, "Cast the episode first, then write who says what.")); return; }
    const list = h("div", { class: "lines" });
    list.append(h("div", { class: "line hint" }, h("span"), h("span", {}, "Who"), h("span", {}, "Line"), h("span", {}, "Said to"), h("span", {}, "Delivery"), h("span", {}, "Pause"), h("span")));
    ep.scenes.forEach((sc, k) => {
      list.append(h("div", { class: "scenehead row" }, h("strong", {}, `Scene ${k + 1}${sc.name ? " · " + sc.name : ""}`), h("span", { class: "hint" }, sc.background), h("span", { class: "spacer" }),
        h("button", { class: "btn small", onclick: () => {
          const last = ep.lines.map((l, i) => [l, i]).filter(([l]) => l.scene === k).pop();
          const at = last ? last[1] + 1 : ep.lines.filter(l => l.scene < k).length;
          ep.lines.splice(at, 0, blank(k, last ? otherThan(last[0].who) : (ep.cast[0] || {}).id)); save(); renderLines();
        } }, "+ Line")));
      ep.lines.forEach((ln, i) => {
        if (ln.scene !== k) return;
        const set = (key, val) => { ln[key] = val; save(); };
        list.append(h("div", { class: "line" },
          h("span", { class: "num" }, ln.id || ""),
          h("select", { onchange: e => { set("who", e.target.value); renderStage(); } }, ep.cast.map(c => h("option", { value: c.id, selected: c.id === ln.who }, nameOf(c.id)))),
          h("div", {}, h("input", { type: "text", value: ln.text, placeholder: "What they say", oninput: e => set("text", e.target.value),
            onkeydown: e => { if (e.key === "Enter") { ep.lines.splice(i + 1, 0, blank(k, otherThan(ln.who))); save(); renderLines(); } } }),
            durs[ln.id] ? h("span", { class: "dur" }, ` ${fmtT(durs[ln.id].dur)}`) : null),
          h("select", { onchange: e => set("to", e.target.value) }, h("option", { value: "" }, "(worked out)"),
            ep.cast.filter(c => c.id !== ln.who).map(c => h("option", { value: c.id, selected: c.id === ln.to }, nameOf(c.id))),
            h("option", { value: "cam", selected: ln.to === "cam" }, "the camera")),
          h("select", { onchange: e => set("tone", e.target.value) }, h("option", { value: "" }, "(from the text)"), LIB.tones.map(t => h("option", { value: t, selected: t === ln.tone }, t))),
          h("input", { type: "number", min: 0, max: 10, step: 0.1, value: ln.pause ?? "", placeholder: "auto", title: "Seconds of silence before the line", oninput: e => set("pause", e.target.value) }),
          h("div", { class: "row", style: { gap: "2px" } },
            h("button", { class: "btn small ghost", title: "Move up", disabled: !i, onclick: () => {
              const p = ep.lines[i - 1];
              if (p.scene !== ln.scene) ln.scene = p.scene; else [ep.lines[i - 1], ep.lines[i]] = [ln, p];
              save(); renderLines(); renderStage(); } }, "↑"),
            h("button", { class: "btn small ghost", title: "Delete", onclick: () => { ep.lines.splice(i, 1); save(); renderLines(); } }, "✕"))));
      });
    });
    linesPanel.append(list);
  }
  const otherThan = id => (ep.cast.find(c => c.id !== id) || ep.cast[0] || {}).id;
  function pasteScript() {
    const ta = h("textarea", { rows: 14, style: { width: "100%" }, placeholder: "MICAH: Have you seen the state of this kitchen?\nCARRICK: I have. I made it like that on purpose.\n\nOne line each, NAME: what they say. [L001] numbers and (stage directions) are ignored. Whole scripts with scenes: use Produce from a pack on the Episodes page." });
    modal(`Paste lines into scene ${cur + 1}`, h("div", {}, ta, h("div", { class: "row", style: { marginTop: "10px" } },
      h("span", { class: "spacer" }),
      h("button", { class: "btn primary", onclick: () => {
        const names = ep.cast.map(c => { const ch = charOf(c.id) || {}; return [c.id, [c.id, ch.name, ch.short, (ch.name || "").split(" ").slice(-1)[0]].filter(Boolean).map(s => s.toLowerCase().replace(/[^a-z0-9]/g, ""))]; });
        const out = [], missing = new Set();
        for (let raw of ta.value.split("\n")) {
          raw = raw.replace(/^\s*\[[^\]]*\]\s*/, "").replace(/\([^)]*\)/g, "").trim();
          const m = raw.match(/^([^:]{1,40}):\s*(.+)$/);
          if (!m) continue;
          const key = m[1].toLowerCase().replace(/[^a-z0-9]/g, "");
          const hit = names.find(([, ns]) => ns.includes(key));
          if (!hit) { missing.add(m[1].trim()); continue; }
          out.push(blank(cur, hit[0])); out[out.length - 1].text = m[2].trim();
        }
        const last = ep.lines.map((l, i) => [l, i]).filter(([l]) => l.scene <= cur).pop();
        ep.lines.splice(last ? last[1] + 1 : 0, 0, ...out);
        save(true); closeModal(); renderLines(); renderStage();
        toast(`${out.length} lines added` + (missing.size ? `; not in the cast: ${[...missing].join(", ")}` : ""), missing.size > 0);
      } }, "Add the lines"))));
  }

  // ---- making it
  const jobBox = h("div");
  const outBox = h("div");
  makePanel.append(h("div", { class: "row" }, h("h2", {}, "Make it"), h("span", { class: "spacer" }),
      h("input", { type: "text", id: "still-t", placeholder: "Stills at (s): blank = every shot", style: { width: "230px" } }),
      h("button", { class: "btn", onclick: () => run("stills") }, "Stills"),
      h("button", { class: "btn", onclick: () => run("draft") }, "Draft"),
      h("button", { class: "btn primary", onclick: () => run("final") }, "Final film")),
    h("p", { class: "hint" }, "Stills: quick frames to check the shots. Draft: the whole film at 960 x 540. Final: 1920 x 1080 with a contact sheet and a lip-sync sheet."),
    jobBox, outBox);

  async function run(kind) {
    await save(true);
    let r;
    if (kind === "stills") {
      const ts = ($("#still-t").value.match(/[\d.]+/g) || []).map(Number);
      r = await safe(() => api("POST", `/api/episodes/${slug}/stills`, { times: ts.length ? ts : ["auto"] }));
    } else r = await safe(() => api("POST", `/api/episodes/${slug}/make`, { quality: kind }));
    follow(r.job);
  }
  async function produce(quality) {
    if (!confirm("Read the pack again? The cast, sets, staging and lines are worked out afresh from it (changes made here are replaced).")) return;
    const r = await safe(() => api("POST", `/api/episodes/${slug}/produce`, { quality }));
    follow(r.job);
  }
  function follow(id) {
    watch(id, async j => {
      jobBox.innerHTML = ""; jobBox.append(jobView(j));
      const log = $("pre.log", jobBox); if (log) log.scrollTop = log.scrollHeight;
      if (j.steps[0].startsWith("Read the pack") && (j.step > 0 || j.state !== "running") && !jobBox.dataset.reloaded) {
        jobBox.dataset.reloaded = "1";               // the pack is read: show what came of it
        await loadLib(); ep = await api("GET", `/api/episodes/${slug}`); renderAll();
      }
      if (j.state === "done") { toast(j.title + ": done"); refreshOutputs(); }
      if (j.state === "failed") { toast(j.error, true); renderReport(); }
    });
  }
  async function refreshOutputs() {
    outputs = await api("GET", `/api/episodes/${slug}/outputs`);
    const stills = await api("GET", `/api/episodes/${slug}/stills`);
    outBox.innerHTML = "";
    const vids = [];
    if (outputs.video) vids.push(h("div", {}, h("h3", {}, "Final (1080p)"), h("video", { src: fileUrl(outputs.video.path) + `?v=${outputs.video.mtime}`, controls: true }),
      h("a", { class: "btn small", href: fileUrl(outputs.video.path), download: `${slug}.mp4` }, "Download")));
    if (outputs.preview) vids.push(h("div", {}, h("h3", {}, "Draft"), h("video", { src: fileUrl(outputs.preview.path) + `?v=${outputs.preview.mtime}`, controls: true })));
    outBox.append(h("div", { class: "grid wide", style: { gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))" } }, vids));
    for (const [k, label] of [["contact", "Contact sheet: three frames of every shot"], ["lips", "Lip sync: the mouths on the stressed words"]]) {
      if (outputs[k]) outBox.append(h("h3", { style: { marginTop: "14px" } }, label), h("img", { class: "sheetimg", src: fileUrl(outputs[k].path) + `?v=${outputs[k].mtime}`, onclick: e => window.open(e.target.src) }));
    }
    if (stills.length) outBox.append(h("h3", { style: { marginTop: "14px" } }, "Stills"), h("div", { class: "shots" }, stills.map(s =>
      h("figure", {}, h("img", { src: fileUrl(s.path) + `?v=${s.mtime}`, onclick: e => window.open(e.target.src) }), h("figcaption", {}, fmtT(s.t))))));
    renderLines();
  }
  function renderAll() { renderStage(); renderCast(); renderLines(); renderReport(); }

  renderAll();
  await refreshOutputs();
  const want = sessionStorage.getItem("follow-" + slug);
  const live = (await api("GET", "/api/jobs")).find(j => j.ref === slug && (j.id === want || ["running", "queued"].includes(j.state)));
  if (live) follow(live.id);
}

// ---------------------------------------------------------------- characters
// ---------------------------------------------------------------- adding cast and sets, many at once
const nameFromFile = f => f.replace(/\.[a-z0-9]+$/i, "").split(/[\s_\-.]+/)
  .filter(w => w && !/^\d+$/.test(w) && !["kit", "final", "sheet", "model", "character", "char", "front", "full", "body", "new", "v", "copy", "img", "image", "drawing", "art", "pose", "bg", "background", "set", "backdrop"].includes(w.toLowerCase().replace(/\d+$/, "")))
  .map(w => w === w.toLowerCase() || w === w.toUpperCase() ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w).join(" ");

function bulkAdder(kind, onDone) {
  const cast = kind === "cast";
  let rows = [];
  const inp = h("input", { type: "file", multiple: true, accept: "image/*", class: "hidden" });
  const zone = h("div", { class: "drop big" },
    h("div", { class: "drop-title" }, cast ? "Add cast members" : "Add backgrounds"),
    h("div", {}, cast ? "One picture per character, named after them (Carlos Baleba.png): a drawing on white or transparent, or a model sheet. Tap to choose, as many as you like."
      : "Empty sets with nobody in them, named for the place (Carrick's kitchen.png). Landscape, 1920 x 1080 or bigger is best. Tap to choose, as many as you like."), inp);
  const list = h("div", { class: "bulk" });
  const go = h("button", { class: "btn primary hidden" });
  const add = fs => { for (const f of fs) if (f.type.startsWith("image/") || /\.(png|jpe?g|webp)$/i.test(f.name)) rows.push({ file: f, name: nameFromFile(f.name), state: "" }); show(); };
  zone.onclick = () => inp.click();
  inp.onchange = () => { add(inp.files); inp.value = ""; };
  zone.ondragover = e => { e.preventDefault(); zone.classList.add("over"); };
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = e => { e.preventDefault(); zone.classList.remove("over"); add(e.dataTransfer.files); };
  function show() {
    list.innerHTML = "";
    rows.forEach((r, i) => {
      const url = r.url || (r.url = URL.createObjectURL(r.file));
      list.append(h("div", { class: "bulkrow" },
        h("div", { class: "thumb" + (cast ? "" : " land"), style: { backgroundImage: `url(${url})` } }),
        h("div", {}, r.state ? h("strong", {}, r.name) : h("input", { type: "text", value: r.name, placeholder: cast ? "Their full name" : "What the place is", oninput: e => r.name = e.target.value }),
          h("div", { class: "hint" }, r.state || r.file.name)),
        r.state ? (r.link ? h("a", { class: "btn small", href: r.link }, "Open") : null)
          : h("button", { class: "btn small ghost", onclick: () => { rows.splice(i, 1); show(); } }, "✕")));
    });
    const todo = rows.filter(r => !r.state).length;
    go.textContent = cast ? `Add ${todo} cast member${todo === 1 ? "" : "s"}` : `Add ${todo} background${todo === 1 ? "" : "s"}`;
    go.classList.toggle("hidden", !todo);
  }
  go.onclick = async () => {
    go.disabled = true;
    for (const r of rows.filter(r => !r.state)) {
      if (!r.name.trim()) { toast("Give every picture a name", true); continue; }
      r.state = "uploading..."; show();
      try {
        if (cast) {
          const res = await api("POST", `/api/characters?name=${encodeURIComponent(r.name)}&filename=${encodeURIComponent(r.file.name)}`, undefined, r.file);
          r.state = "added: cutting out..."; r.link = "#character/" + res.id;
          watch(res.job, j => { if (j.state === "done") { r.state = "ready"; show(); } if (j.state === "failed") { r.state = "couldn't be cut out: open it"; show(); } });
        } else {
          const res = await api("POST", `/api/backgrounds?title=${encodeURIComponent(r.name)}&setting=auto&filename=${encodeURIComponent(r.file.name)}`, undefined, r.file);
          r.state = "added as " + res.id;
        }
      } catch (e) {
        r.state = /already in/.test(e.message) ? "already in the cast library: used as it is" : "not added: " + e.message;
      }
      show();
    }
    go.disabled = false;
    await loadLib();
    onDone && onDone();
  };
  return h("div", {}, zone, list, h("div", { class: "row", style: { marginTop: "8px" } }, h("span", { class: "spacer" }), go));
}

// ---------------------------------------------------------------- the home page: the three steps of a production
async function viewProduce() {
  await loadLib();
  const shows = await api("GET", "/api/shows").catch(() => []);
  const recent = await api("GET", "/api/episodes");
  put(h("h1", {}, "New production"),
    h("p", { class: "sub" }, "Add the new cast and backgrounds, then hand over the director's zip and production notes: the studio does the rest."),
    h("div", { class: "panel step" }, h("div", { class: "stepnum" }, "1"), h("h2", {}, "New cast members"),
      h("p", { class: "hint" }, "Anyone in this production who isn't in the cast library yet. Already there? Skip this."), bulkAdder("cast")),
    h("div", { class: "panel step" }, h("div", { class: "stepnum" }, "2"), h("h2", {}, "New backgrounds"),
      h("p", { class: "hint" }, "The sets this production needs that aren't in the library yet. Each scene gets the set its heading or slugline names (INT. CARRICK'S KITCHEN finds 'Carrick's kitchen'); a scene that names none gets the newest one."), bulkAdder("sets")),
    h("div", { class: "step-wrap" }, h("div", { class: "stepnum" }, "3"), packPanel(null, shows)),
    recent.filter(e => e.web).length ? h("div", { class: "panel" }, h("h2", {}, "Recent productions"),
      h("div", { class: "grid wide" }, recent.filter(e => e.web).slice(-6).reverse().map(e => h("div", { class: "card", onclick: () => location.hash = "episode/" + e.slug },
        h("div", { class: "meta" }, h("div", { class: "name" }, e.title),
          e.video ? h("span", { class: "tag ok" }, "finished") : e.preview ? h("span", { class: "tag warn" }, "draft") : h("span", { class: "tag" }, "in production")))))) : null);
}

async function viewCharacters() {
  await loadLib();
  put(h("h1", {}, "Cast"),
    h("p", { class: "sub" }, "Every character in the library. A new one is cut out of its picture whole (never chopped into limbs), upscaled 4x and given face landmarks so the eyes, brows and mouth can act."),
    h("div", { class: "panel" }, bulkAdder("cast", route)),
    h("div", { class: "grid" }, LIB.characters.map(c => h("div", { class: "card", onclick: () => location.hash = "character/" + c.id },
      h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, c.name), h("div", { class: "small" }, c.role || " "),
        !c.drawings.length ? h("span", { class: "tag" }, "no drawings yet") : c.drawings.some(d => d.built) ? h("span", { class: "tag ok" }, "ready") : h("span", { class: "tag" }, `${c.drawings.length} to cut`),
        c.drawings.some(d => d.face && !(d.face.eyes === 2 && d.face.mouth)) ? h("span", { class: "tag bad" }, "check face") : null,
        c.style === "provisional" ? h("span", { class: "tag warn" }, "stand-in") : null)))));
}

async function viewCharacter(cid) {
  await loadLib();
  const c = charOf(cid);
  if (!c) throw new Error("No such character");
  const sheets = await api("GET", `/api/characters/${cid}/sheets`);
  put(h("div", { class: "row" }, h("a", { href: "#characters", class: "hint" }, "← Characters")),
    h("h1", {}, c.name), h("p", { class: "sub" }, `library/characters/${cid}/ · ${c.role || "character"}${c.style === "provisional" ? " · stand-in kit (off-style)" : ""}`));
  const jobBox = h("div");
  const draws = h("div", { class: "grid wide" });
  put(h("div", { class: "panel" }, h("div", { class: "row" }, h("h2", {}, "Drawings to film"), h("span", { class: "spacer" }),
    h("button", { class: "btn small primary", onclick: () => newDrawing() }, "+ New drawing from a sheet")),
    h("p", { class: "hint" }, "Green rings should sit on the eyes and the red dots on the mouth (its corners and middle). If they don't, use Fix face."), jobBox, draws));

  function follow(id) {
    watch(id, async j => {
      jobBox.innerHTML = ""; jobBox.append(jobView(j));
      if (j.state === "done") { jobBox.innerHTML = ""; toast("Cut out"); await loadLib(); renderDrawings(); }
      if (j.state === "failed") toast(j.error, true);
    });
  }
  async function renderDrawings() {
    const cc = charOf(cid);
    draws.innerHTML = "";
    if (!cc.drawings.length) draws.append(h("div", { class: "empty" }, "No drawings yet: make one from a sheet."));
    for (const d of cc.drawings) {
      const card = h("div", { class: "card", style: { cursor: "default" } });
      let info = null;
      if (d.built) info = await api("GET", `/api/characters/${cid}/drawing/${d.name}`).catch(() => null);
      card.append(info ? faceOverlay(info, 380) : h("div", { class: "pic", style: { background: "#26292f", display: "flex", alignItems: "center", justifyContent: "center" } }, h("span", { class: "hint" }, "not cut out yet")),
        h("div", { class: "meta" }, h("div", { class: "row" }, h("strong", {}, d.name), h("span", { class: "tag" }, { F: "faces front", L: "faces left", R: "faces right", B: "back" }[d.faces] || d.faces),
          d.face ? h("span", { class: "tag " + (d.face.eyes === 2 && d.face.mouth ? "ok" : "bad") }, d.face.eyes === 2 && d.face.mouth ? "face found" : `face: ${d.face.eyes} eyes${d.face.mouth ? "" : ", no mouth"}`) : null),
          h("div", { class: "small" }, d.source || ""),
          h("div", { class: "row", style: { marginTop: "6px" } },
            h("button", { class: "btn small", onclick: () => safe(async () => follow((await api("POST", `/api/characters/${cid}/build`, { drawing: d.name })).job)) }, d.built ? "Cut again" : "Cut out"),
            d.box ? h("button", { class: "btn small", onclick: () => newDrawing(d) }, "Change box") : null,
            info ? h("button", { class: "btn small", onclick: () => fixFace(d, info) }, "Fix face") : null)));
      draws.append(card);
    }
  }
  function faceOverlay(info, hh) {
    const [w, hgt] = info.meta.size, K = info.meta.scale, [ox, oy] = info.meta.off;
    const P = (x, y) => [(x - ox) * K, (y - oy) * K];
    const svg = [`<svg viewBox="0 0 ${w} ${hgt}" style="height:${hh}px;max-width:100%;display:block;margin:auto">`,
      `<image href="${thumbUrl(info.path, 900, true)}" width="${w}" height="${hgt}"/>`];
    const sw = Math.max(4, w / 160);
    for (const [x, y, rx, ry] of info.marks.eyes || []) { const [px, py] = P(x, y); svg.push(`<ellipse cx="${px}" cy="${py}" rx="${rx * K}" ry="${ry * K}" fill="none" stroke="#2ecc71" stroke-width="${sw}"/>`); }
    if (info.marks.mouth) { const m = info.marks.mouth; for (let i = 0; i < 3; i++) { const [px, py] = P(m[2 * i], m[2 * i + 1]); svg.push(`<circle cx="${px}" cy="${py}" r="${sw * 1.6}" fill="#e2372b"/>`); } }
    svg.push("</svg>");
    return h("div", { style: { background: "#e8e3da", padding: "8px" }, html: svg.join("") });
  }
  function fixFace(d, info) {
    const pts = [];
    const pk = h("div", { class: "picker" });
    const img = h("img", { src: thumbUrl(info.path, 1200, true) });
    pk.append(img);
    const help = h("p", { class: "hint" }, "Click the middle of the left eye, then the right eye, then the middle of the mouth.");
    const saveBtn = h("button", { class: "btn primary", disabled: true, onclick: () => safe(async () => {
      const [w] = info.meta.size, k = w / img.clientWidth;
      const r = await api("POST", `/api/characters/${cid}/face`, { drawing: d.name, eyes: [pts[0], pts[1]].map(p => [p[0] * k, p[1] * k]), mouth: [pts[2][0] * k, pts[2][1] * k] });
      closeModal(); follow(r.job);
    }) }, "Save the face");
    pk.onclick = e => {
      const r = img.getBoundingClientRect();
      if (pts.length >= 3) { pts.length = 0; $$(".pt", pk).forEach(p => p.remove()); }
      pts.push([e.clientX - r.left, e.clientY - r.top]);
      pk.append(h("div", { class: "pt " + (pts.length < 3 ? "eye" : "mouth"), style: { left: `${e.clientX - r.left}px`, top: `${e.clientY - r.top}px` } }));
      saveBtn.disabled = pts.length !== 3;
    };
    modal(`Fix the face: ${d.name}`, h("div", {}, help, pk, h("div", { class: "row", style: { marginTop: "10px" } }, h("span", { class: "spacer" }), saveBtn)), true);
  }
  function newDrawing(existing) {
    let sheet = existing ? sheets.find(s => s.sheet === existing.source) || sheets[0] : sheets[0];
    let box = existing && existing.box ? [...existing.box] : null;
    const nameIn = h("input", { type: "text", value: existing ? existing.name : (c.drawings.length ? `pose${c.drawings.length + 1}` : "front"), placeholder: "front, q34, pointing..." });
    const faces = h("select", {}, ["F", "R", "L", "B"].map(f => h("option", { value: f, selected: existing && existing.faces === f }, { F: "Faces the front", R: "Turned to the right", L: "Turned to the left", B: "From the back" }[f])));
    const pk = h("div", { class: "picker" });
    const sheetSel = h("select", { onchange: e => { sheet = sheets[+e.target.value]; box = null; drawPicker(); } },
      sheets.map((s, i) => h("option", { value: i, selected: s === sheet }, s.sheet)));
    const upl = h("input", { type: "file", accept: "image/*", class: "hidden", onchange: e => safe(async () => {
      const f = e.target.files[0]; if (!f) return;
      const r = await api("POST", `/api/characters/${cid}/sheets?filename=${encodeURIComponent(f.name)}`, undefined, f);
      sheets.splice(0, sheets.length, ...(await api("GET", `/api/characters/${cid}/sheets`)));
      closeModal(); newDrawing(); toast("Filed as " + r.sheet);
    }) });
    function drawPicker() {
      pk.innerHTML = "";
      if (!sheet) { pk.append(h("div", { class: "empty" }, "No sheets yet: upload one.")); return; }
      const img = h("img", { src: fileUrl(sheet.path) });
      const bx = h("div", { class: "box" });
      pk.append(img, bx);
      const show = () => {
        if (!box) { bx.style.display = "none"; return; }
        const k = img.clientWidth / sheet.size[0];
        Object.assign(bx.style, { display: "block", left: `${box[0] * k}px`, top: `${box[1] * k}px`, width: `${(box[2] - box[0]) * k}px`, height: `${(box[3] - box[1]) * k}px` });
      };
      img.onload = show;
      pk.onpointerdown = e => {
        e.preventDefault();
        const r = img.getBoundingClientRect(), k = sheet.size[0] / r.width;
        const x0 = (e.clientX - r.left) * k, y0 = (e.clientY - r.top) * k;
        pk.setPointerCapture(e.pointerId);
        pk.onpointermove = ev => {
          const x1 = Math.min(sheet.size[0], Math.max(0, (ev.clientX - r.left) * k)), y1 = Math.min(sheet.size[1], Math.max(0, (ev.clientY - r.top) * k));
          box = [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)].map(Math.round);
          show();
        };
        pk.onpointerup = () => { pk.onpointermove = null; };
      };
      show();
    }
    drawPicker();
    modal(existing ? `Change the box: ${existing.name}` : "A new drawing to film", h("div", {},
      h("p", { class: "hint" }, "Drag a box round one whole drawing of the character on the sheet: the head, the body and the feet, with a little paper round it and nothing of the drawings next to it. Prefer one with the mouth closed. The whole picture is used if you don't draw a box."),
      h("div", { class: "fields" }, h("label", { class: "f" }, "Sheet", sheetSel), h("label", { class: "f" }, "Name", nameIn), h("label", { class: "f" }, "Which way it faces", faces),
        h("label", { class: "f" }, "Another sheet", h("button", { class: "btn small", onclick: () => upl.click() }, "Upload a sheet"), upl)),
      h("div", { style: { margin: "12px 0" } }, pk),
      h("div", { class: "row" }, h("span", { class: "spacer" }), h("button", { class: "btn primary", onclick: () => safe(async () => {
        if (!sheet) throw new Error("Upload a sheet first");
        const r = await api("POST", `/api/characters/${cid}/drawings`, { name: nameIn.value, sheet: sheet.sheet, box: box || [0, 0, sheet.size[0], sheet.size[1]], faces: faces.value });
        closeModal(); await loadLib(); renderDrawings(); follow(r.job);
      }) }, "Cut it out"))), true);
  }
  await renderDrawings();
  const live = (await api("GET", "/api/jobs")).find(j => j.ref === cid && ["running", "queued"].includes(j.state));
  if (live) follow(live.id);
}

// ---------------------------------------------------------------- backgrounds
async function viewBackgrounds() {
  await loadLib();
  put(h("h1", {}, "Backgrounds"),
    h("p", { class: "sub" }, "Empty sets, newest first. The camera moves inside them: the wide shows the whole set, the close-ups a blurred piece of it behind the speaker."),
    h("div", { class: "panel" }, bulkAdder("sets", route)),
    h("div", { class: "grid wide" }, LIB.backgrounds.map(b => h("div", { class: "card", onclick: () => window.open(fileUrl(b.path)) },
      h("div", { class: "pic land", style: { backgroundImage: `url(${thumbUrl(b.path, 240)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, b.title), h("div", { class: "small" }, b.id),
        b.orientation === "portrait" ? h("span", { class: "tag warn" }, "portrait: not usable full-frame") : null)))));
}

// ---------------------------------------------------------------- jobs
async function viewJobs() {
  const list = await api("GET", "/api/jobs");
  put(h("h1", {}, "Jobs"), h("p", { class: "sub" }, "What the engine is doing and has done since the server started. One job runs at a time: a render uses every core."));
  if (!list.length) put(h("div", { class: "empty" }, "Nothing yet."));
  for (const j of list) {
    const box = h("div", { class: "panel" }, jobView(j, route));
    put(box);
    if (["running", "queued"].includes(j.state)) watch(j.id, jj => { box.innerHTML = ""; box.append(jobView(jj, route)); });
  }
}

route();
pollJobs();
