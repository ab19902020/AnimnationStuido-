/* Animation Studio: the page. Plain JavaScript, no build step. Views: episodes (list and the scene editor),
   characters (upload, cut drawings from sheets, fix faces), backgrounds, jobs. Everything heavy is a job on the
   server (studio/web/jobs.py); the page polls it. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = $("#app");
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
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(k));
  return el;
}
async function api(method, url, body, raw) {
  const opt = { method, headers: {} };
  if (raw) { opt.body = raw; }
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, opt);
  const j = await r.json().catch(() => ({}));
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
const VIEWS = { episodes: viewEpisodes, episode: viewEpisode, characters: viewCharacters, character: viewCharacter,
  backgrounds: viewBackgrounds, jobs: viewJobs };
async function route() {
  const [v, arg] = (location.hash.slice(1) || "episodes").split("/");
  $$("nav a").forEach(a => a.classList.toggle("on", a.dataset.view === v || (v === "episode" && a.dataset.view === "episodes") || (v === "character" && a.dataset.view === "characters")));
  JOBS.watchers.clear();
  app.innerHTML = "";
  try { await (VIEWS[v] || viewEpisodes)(arg && decodeURIComponent(arg)); }
  catch (e) { app.append(h("div", { class: "empty" }, e.message)); }
}
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------- episodes
async function viewEpisodes() {
  const eps = await api("GET", "/api/episodes");
  const title = h("input", { type: "text", placeholder: "The title of the new episode" });
  app.append(
    h("h1", {}, "Episodes"),
    h("p", { class: "sub" }, "Pick a set, cast it, write the lines and give everyone a voice: the engine cuts the characters out, syncs their lips, directs the camera, mixes the sound and renders the film."),
    h("div", { class: "panel row" }, title, h("button", { class: "btn primary", onclick: () => safe(async () => {
      const r = await api("POST", "/api/episodes", { title: title.value });
      location.hash = "episode/" + r.slug;
    }) }, "New episode")),
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
    app.append(h("h1", {}, x ? x.title : slug), h("p", { class: "sub" }, e.message),
      x && x.video ? h("video", { src: fileUrl(x.video), controls: true }) : null);
    return;
  }
  let outputs = {};
  let selected = ep.cast[0] ? ep.cast[0].id : null;
  let saveTimer = null;
  const save = (now) => {
    clearTimeout(saveTimer);
    const go = async () => { const r = await safe(() => api("PUT", `/api/episodes/${slug}`, ep)); ep.lines = r.lines; $("#saved").textContent = "Saved"; renderLines(); };
    $("#saved").textContent = "Saving...";
    if (now) return go();
    saveTimer = setTimeout(go, 600);
  };

  // header
  const fld = (label, key, ph) => h("label", { class: "f" }, label, h("input", { type: "text", value: ep[key] || "", placeholder: ph, oninput: e => { ep[key] = e.target.value; save(); } }));
  app.append(
    h("div", { class: "row" }, h("h1", {}, ep.title || slug), h("span", { class: "spacer" }), h("span", { id: "saved", class: "hint" }, "Saved"),
      h("button", { class: "btn ghost small", onclick: () => { if (confirm("Delete this episode and everything made for it?")) safe(async () => { await api("DELETE", `/api/episodes/${slug}`); location.hash = "episodes"; }); } }, "Delete")),
    h("p", { class: "sub" }, `episodes/${slug}/`),
    h("div", { class: "panel" }, h("div", { class: "fields" },
      fld("Title", "title", "The title card"), fld("Show", "show", "Above the title (optional)"),
      fld("Tagline", "tagline", "Under the title (optional)"), fld("Opening caption", "place", "Where we are (optional)"))));

  const cols = h("div", { class: "cols" });
  const left = h("div"), right = h("div");
  cols.append(left, right);
  app.append(cols);

  // ---- the set and the staging
  const stage = h("div", { class: "stage" });
  const stagePanel = h("div", { class: "panel" },
    h("div", { class: "row" }, h("h2", {}, "The set"), h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: pickBackground }, "Change set")),
    stage, h("p", { class: "hint" }, "Drag the characters to where they stand; their feet go where you drop them. The size slider on each one sets how tall they stand. The camera works out the shots from this."));
  left.append(stagePanel);

  function drawingKey(c) { return c.drawing || "front"; }
  function actorImg(c) {
    const ch = charOf(c.id);
    const d = ch && ch.drawings.find(x => x.name === drawingKey(c));
    return d && d.built ? thumbUrl(`build/film/${c.id}/${drawingKey(c)}.png`, 700, true) : charThumb(c.id);
  }
  function renderStage() {
    stage.innerHTML = "";
    stage.style.backgroundImage = ep.background ? `url(${thumbUrl(`library/backgrounds/${ep.background}.png`, 720)})` : "";
    for (const c of ep.cast) {
      const ch = charOf(c.id);
      const a = h("div", { class: "actor" + (c.id === selected ? " sel" : ""), style: { left: `${c.x * 100}%`, top: `${(c.floor - c.height) * 100}%`, height: `${c.height * 100}%` } },
        h("img", { src: actorImg(c), alt: c.id }), h("div", { class: "lbl" }, ch ? ch.name : c.id));
      a.onpointerdown = e => {
        e.preventDefault(); selected = c.id; renderCast(); $$(".actor", stage).forEach(x => x.classList.remove("sel")); a.classList.add("sel");
        a.setPointerCapture(e.pointerId);
        const r = stage.getBoundingClientRect();
        const move = ev => {
          c.x = Math.min(0.98, Math.max(0.02, (ev.clientX - r.left) / r.width));
          c.floor = Math.min(1.2, Math.max(c.height * 0.3, (ev.clientY - r.top) / r.height));
          c.x = Math.round(c.x * 1000) / 1000; c.floor = Math.round(c.floor * 1000) / 1000;
          a.style.left = `${c.x * 100}%`; a.style.top = `${(c.floor - c.height) * 100}%`;
        };
        a.onpointermove = move;
        a.onpointerup = () => { a.onpointermove = null; save(); };
      };
      stage.append(a);
    }
  }
  function pickBackground() {
    const grid = h("div", { class: "grid wide" }, LIB.backgrounds.filter(b => b.orientation === "landscape").map(b =>
      h("div", { class: "card" + (b.id === ep.background ? " sel" : ""), onclick: () => { ep.background = b.id; save(); renderStage(); closeModal(); } },
        h("div", { class: "pic land", style: { backgroundImage: `url(${thumbUrl(b.path, 240)})` } }),
        h("div", { class: "meta" }, h("div", { class: "name" }, b.title), h("div", { class: "small" }, b.id)))));
    modal("Choose the set", h("div", {}, h("p", { class: "hint" }, "Landscape sets only: the film is 16:9. Add your own on the Backgrounds page."), grid), true);
  }

  // ---- the cast
  const castPanel = h("div", { class: "panel" });
  right.append(castPanel);
  function renderCast() {
    castPanel.innerHTML = "";
    castPanel.append(h("div", { class: "row" }, h("h2", {}, "Cast"), h("span", { class: "spacer" }), h("button", { class: "btn small primary", onclick: addCast }, "+ Add character")));
    if (!ep.cast.length) castPanel.append(h("div", { class: "empty" }, "Nobody is in this scene yet."));
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
        const has = v.file && (ep._files || []).includes(v.file);
        const inp = h("input", { type: "file", accept: "audio/*", class: "hidden", onchange: e => uploadVoice(c, e.target.files[0]) });
        voiceBits = [h("label", { class: "f" }, "Recording", h("div", { class: "row" },
          h("span", { class: "tag " + (has ? "ok" : "bad") }, has ? v.file : "none yet"),
          h("button", { class: "btn small", onclick: () => inp.click() }, has ? "Replace" : "Upload"), inp)),
          h("div", { class: "hint", style: { gridColumn: "1 / -1" } }, "One file with all of this character's lines, read in script order. Each line is found in it by speech recognition and cut word-exact.")];
      }
      const row = h("div", { class: "castrow" + (c.id === selected ? " sel" : ""), onclick: e => { if (selected !== c.id) { selected = c.id; renderStage(); $$(".castrow", castPanel).forEach(r => r.classList.remove("sel")); row.classList.add("sel"); } } },
        h("div", { class: "face", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
        h("div", {},
          h("div", { class: "row" }, h("strong", {}, ch.name), ch.style === "provisional" ? h("span", { class: "tag warn" }, "stand-in kit") : null, h("span", { class: "spacer" }),
            h("button", { class: "btn small ghost", title: "Remove from the scene", onclick: () => { ep.cast = ep.cast.filter(x => x !== c); save(); renderCast(); renderStage(); renderLines(); } }, "Remove")),
          h("div", { class: "fields" },
            h("label", { class: "f" }, "Drawing", drawSel),
            h("label", { class: "f" }, `Size ${Math.round(c.height * 100)}%`, h("input", { type: "range", min: 0.15, max: 1.4, step: 0.01, value: c.height,
              oninput: e => { c.height = +e.target.value; e.target.previousSibling.textContent = `Size ${Math.round(c.height * 100)}%`; renderStage(); save(); } })),
            h("label", { class: "f" }, "Voice from", kindSel), ...voiceBits,
            h("label", { class: "f" }, "Caption", h("input", { type: "text", value: c.caption || "", placeholder: ch.role || "Under their name", oninput: e => set("caption", e.target.value) })),
            h("label", { class: "f" }, "Resting face", h("select", { onchange: e => set("mood", e.target.value) },
              h("option", { value: "" }, "neutral"), LIB.tones.map(t => h("option", { value: t, selected: t === c.mood }, t)))))));
      castPanel.append(row);
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
      const xs = [0.3, 0.7, 0.5, 0.15, 0.85, 0.4, 0.6];
      ep.cast.push({ id: c.id, drawing: c.drawings[0].name, x: xs[n % xs.length], floor: 0.93, height: 0.62,
        voice: { kind: "tts", voice: Object.keys(LIB.voices)[n % 4] || "bm_george", speed: 1.0 }, caption: "", mood: "" });
      selected = c.id;
      save(); renderCast(); renderStage(); renderLines(); closeModal();
    } }, h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, c.name), h("div", { class: "small" }, c.role),
        c.drawings.some(d => d.built) ? h("span", { class: "tag ok" }, "ready") : h("span", { class: "tag" }, "cut on first use")))));
    modal("Add a character to the scene", h("div", {}, h("p", { class: "hint" }, "Characters with drawings to film. Upload new ones on the Characters page."), grid), true);
  }

  // ---- the script
  const linesPanel = h("div", { class: "panel" });
  app.append(linesPanel);
  function renderLines() {
    linesPanel.innerHTML = "";
    const durs = outputs.lines || {};
    linesPanel.append(h("div", { class: "row" }, h("h2", {}, "Script"), h("span", { class: "spacer" }),
      h("button", { class: "btn small", onclick: pasteScript }, "Paste a script"),
      h("button", { class: "btn small primary", onclick: () => { ep.lines.push({ who: lastOther(), to: "", text: "", tone: "", pause: "" }); save(); renderLines(); const ins = $$(".line input[type=text]", linesPanel); ins.length && ins[ins.length - 1].focus(); } }, "+ Add line")));
    if (!ep.cast.length) { linesPanel.append(h("div", { class: "empty" }, "Cast the scene first, then write who says what.")); return; }
    const list = h("div", { class: "lines" });
    list.append(h("div", { class: "line hint" }, h("span"), h("span", {}, "Who"), h("span", {}, "Line"), h("span", {}, "Said to"), h("span", {}, "Delivery"), h("span", {}, "Pause"), h("span")));
    ep.lines.forEach((ln, i) => {
      const set = (k, val) => { ln[k] = val; save(); };
      const nameOf = id => (charOf(id) || { name: id }).name;
      list.append(h("div", { class: "line" },
        h("span", { class: "num" }, ln.id || `L${String(i + 1).padStart(3, "0")}`),
        h("select", { onchange: e => set("who", e.target.value) }, ep.cast.map(c => h("option", { value: c.id, selected: c.id === ln.who }, nameOf(c.id)))),
        h("div", {}, h("input", { type: "text", value: ln.text, placeholder: "What they say", oninput: e => set("text", e.target.value),
          onkeydown: e => { if (e.key === "Enter") { ep.lines.splice(i + 1, 0, { who: otherThan(ln.who), to: "", text: "", tone: "", pause: "" }); save(); renderLines(); $$(".line input[type=text]", linesPanel)[i + 1].focus(); } } }),
          durs[ln.id] ? h("span", { class: "dur" }, ` ${fmtT(durs[ln.id].dur)}`) : null),
        h("select", { onchange: e => set("to", e.target.value) }, h("option", { value: "" }, "(worked out)"),
          ep.cast.filter(c => c.id !== ln.who).map(c => h("option", { value: c.id, selected: c.id === ln.to }, nameOf(c.id))),
          h("option", { value: "cam", selected: ln.to === "cam" }, "the camera")),
        h("select", { onchange: e => set("tone", e.target.value) }, h("option", { value: "" }, "(from the text)"), LIB.tones.map(t => h("option", { value: t, selected: t === ln.tone }, t))),
        h("input", { type: "number", min: 0, max: 10, step: 0.1, value: ln.pause ?? "", placeholder: "auto", title: "Seconds of silence before the line", oninput: e => set("pause", e.target.value) }),
        h("div", { class: "row", style: { gap: "2px" } },
          h("button", { class: "btn small ghost", title: "Move up", disabled: !i, onclick: () => { [ep.lines[i - 1], ep.lines[i]] = [ep.lines[i], ep.lines[i - 1]]; save(); renderLines(); } }, "↑"),
          h("button", { class: "btn small ghost", title: "Delete", onclick: () => { ep.lines.splice(i, 1); save(); renderLines(); } }, "✕"))));
    });
    linesPanel.append(list);
  }
  const otherThan = id => (ep.cast.find(c => c.id !== id) || ep.cast[0] || {}).id;
  const lastOther = () => ep.lines.length ? otherThan(ep.lines[ep.lines.length - 1].who) : (ep.cast[0] || {}).id;
  function pasteScript() {
    const ta = h("textarea", { rows: 14, style: { width: "100%" }, placeholder: "MICAH: Have you seen the state of this kitchen?\nCARRICK: I have. I made it like that on purpose.\n\nOne line each, NAME: what they say. [L001] numbers and (stage directions) are ignored." });
    modal("Paste a script", h("div", {}, ta, h("div", { class: "row", style: { marginTop: "10px" } },
      h("label", { class: "row hint" }, h("input", { type: "checkbox", id: "replace" }), "Replace the lines already there"), h("span", { class: "spacer" }),
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
          out.push({ who: hit[0], to: "", text: m[2].trim(), tone: "", pause: "" });
        }
        if ($("#replace").checked) ep.lines = out; else ep.lines.push(...out);
        save(true); closeModal(); renderLines();
        toast(`${out.length} lines added` + (missing.size ? `; not in the cast: ${[...missing].join(", ")}` : ""), missing.size > 0);
      } }, "Add the lines"))));
  }

  // ---- making it
  const makePanel = h("div", { class: "panel" });
  const jobBox = h("div");
  const outBox = h("div");
  left.append(makePanel);
  makePanel.append(h("h2", {}, "Make it"),
    h("p", { class: "hint" }, "Stills are quick frames to check the shots. A draft renders the whole film at 960 x 540; the final is 1920 x 1080 with a contact sheet and a lip-sync sheet. The first run cuts out the characters and fetches the speech models, so it takes longest."),
    h("div", { class: "row" },
      h("input", { type: "text", id: "still-t", placeholder: "Stills at (s), e.g. 3 8.5 12 (blank: every shot)", style: { flex: "1 1 220px" } }),
      h("button", { class: "btn", onclick: () => run("stills") }, "Stills"),
      h("button", { class: "btn primary", onclick: () => run("draft") }, "Make draft"),
      h("button", { class: "btn", onclick: () => run("final") }, "Make final")),
    jobBox);
  app.append(h("div", { class: "panel" }, h("h2", {}, "The film"), outBox));

  async function run(kind) {
    await save(true);
    let r;
    if (kind === "stills") {
      const ts = ($("#still-t").value.match(/[\d.]+/g) || []).map(Number);
      r = await safe(() => api("POST", `/api/episodes/${slug}/stills`, { times: ts.length ? ts : ["auto"] }));
    } else r = await safe(() => api("POST", `/api/episodes/${slug}/make`, { quality: kind }));
    follow(r.job);
  }
  function follow(id) {
    watch(id, j => {
      jobBox.innerHTML = ""; jobBox.append(jobView(j));
      const log = $("pre.log", jobBox); if (log) log.scrollTop = log.scrollHeight;
      if (j.state === "done") { toast(j.title + ": done"); refreshOutputs(); }
      if (j.state === "failed") toast(j.error, true);
    });
  }
  async function refreshOutputs() {
    outputs = await api("GET", `/api/episodes/${slug}/outputs`);
    const stills = await api("GET", `/api/episodes/${slug}/stills`);
    outBox.innerHTML = "";
    const vids = [];
    if (outputs.video) vids.push(h("div", {}, h("h3", {}, "Final (1080p)"), h("video", { src: fileUrl(outputs.video.path) + `?v=${outputs.video.mtime}`, controls: true })));
    if (outputs.preview) vids.push(h("div", {}, h("h3", {}, "Draft"), h("video", { src: fileUrl(outputs.preview.path) + `?v=${outputs.preview.mtime}`, controls: true })));
    if (!vids.length && !stills.length) outBox.append(h("div", { class: "empty" }, "Nothing made yet: try some stills, then a draft."));
    outBox.append(h("div", { class: "grid wide", style: { gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))" } }, vids));
    for (const [k, label] of [["contact", "Contact sheet: three frames of every shot"], ["lips", "Lip sync: the mouths on the stressed words"]]) {
      if (outputs[k]) outBox.append(h("h3", { style: { marginTop: "14px" } }, label), h("img", { class: "sheetimg", src: fileUrl(outputs[k].path) + `?v=${outputs[k].mtime}`, onclick: e => window.open(e.target.src) }));
    }
    if (stills.length) outBox.append(h("h3", { style: { marginTop: "14px" } }, "Stills"), h("div", { class: "shots" }, stills.map(s =>
      h("figure", {}, h("img", { src: fileUrl(s.path) + `?v=${s.mtime}`, onclick: e => window.open(e.target.src) }), h("figcaption", {}, fmtT(s.t))))));
    renderLines();
  }

  renderStage(); renderCast(); renderLines();
  await refreshOutputs();
  const live = (await api("GET", "/api/jobs")).find(j => j.ref === slug && ["running", "queued"].includes(j.state));
  if (live) follow(live.id);
}

// ---------------------------------------------------------------- characters
async function viewCharacters() {
  await loadLib();
  const name = h("input", { type: "text", placeholder: "Full name, e.g. Roy Keane" });
  const role = h("input", { type: "text", placeholder: "Role (pundit, manager...)" });
  const zone = dropZone("Drop a drawing of the character here, or click to choose one (PNG on white or transparent; a model sheet works too, you pick the drawing after)", "image/*", (f) => safe(async () => {
    if (!name.value.trim()) { name.focus(); throw new Error("Give the character a name first"); }
    toast("Uploading...");
    const r = await api("POST", `/api/characters?name=${encodeURIComponent(name.value)}&role=${encodeURIComponent(role.value)}&filename=${encodeURIComponent(f.name)}`, undefined, f);
    location.hash = "character/" + r.id;
  }));
  app.append(h("h1", {}, "Characters"),
    h("p", { class: "sub" }, "Every character in the library. A new one is cut out of its picture whole (never chopped into limbs), upscaled 4x and given face landmarks so the eyes, brows and mouth can act."),
    h("div", { class: "panel" }, h("h2", {}, "Add a character"), h("div", { class: "fields", style: { marginBottom: "10px" } }, name, role), zone),
    h("div", { class: "grid" }, LIB.characters.map(c => h("div", { class: "card", onclick: () => location.hash = "character/" + c.id },
      h("div", { class: "pic", style: { backgroundImage: `url(${charThumb(c.id)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, c.name), h("div", { class: "small" }, c.role || " "),
        !c.drawings.length ? h("span", { class: "tag" }, "no drawings yet") : c.drawings.some(d => d.built) ? h("span", { class: "tag ok" }, "ready") : h("span", { class: "tag" }, `${c.drawings.length} to cut`),
        c.style === "provisional" ? h("span", { class: "tag warn" }, "stand-in") : null)))));
}

async function viewCharacter(cid) {
  await loadLib();
  const c = charOf(cid);
  if (!c) throw new Error("No such character");
  const sheets = await api("GET", `/api/characters/${cid}/sheets`);
  app.append(h("div", { class: "row" }, h("a", { href: "#characters", class: "hint" }, "← Characters")),
    h("h1", {}, c.name), h("p", { class: "sub" }, `library/characters/${cid}/ · ${c.role || "character"}${c.style === "provisional" ? " · stand-in kit (off-style)" : ""}`));
  const jobBox = h("div");
  const draws = h("div", { class: "grid wide" });
  app.append(h("div", { class: "panel" }, h("div", { class: "row" }, h("h2", {}, "Drawings to film"), h("span", { class: "spacer" }),
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
  const title = h("input", { type: "text", placeholder: "What it is, e.g. Old Trafford tunnel" });
  const setting = h("select", {}, LIB.settings.map(s => h("option", { value: s }, s)));
  const crop = h("input", { type: "checkbox", checked: true });
  const zone = dropZone("Drop an empty set here (no characters in it), or click to choose one. Landscape, 1920 x 1080 or bigger is best.", "image/*", f => safe(async () => {
    if (!title.value.trim()) { title.focus(); throw new Error("Name the set first"); }
    toast("Uploading...");
    const r = await api("POST", `/api/backgrounds?title=${encodeURIComponent(title.value)}&setting=${setting.value}&crop=${crop.checked ? 1 : 0}&filename=${encodeURIComponent(f.name)}`, undefined, f);
    toast("Filed as " + r.id); title.value = ""; route();
  }));
  app.append(h("h1", {}, "Backgrounds"),
    h("p", { class: "sub" }, "Empty sets. The camera moves inside them: the wide shows the whole set, the close-ups a blurred piece of it behind the speaker."),
    h("div", { class: "panel" }, h("h2", {}, "Add a set"), h("div", { class: "fields", style: { marginBottom: "10px" } }, title, setting,
      h("label", { class: "row hint" }, crop, "Crop to 16:9")), zone),
    h("div", { class: "grid wide" }, LIB.backgrounds.map(b => h("div", { class: "card", onclick: () => window.open(fileUrl(b.path)) },
      h("div", { class: "pic land", style: { backgroundImage: `url(${thumbUrl(b.path, 240)})` } }),
      h("div", { class: "meta" }, h("div", { class: "name" }, b.title), h("div", { class: "small" }, b.id),
        b.orientation === "portrait" ? h("span", { class: "tag warn" }, "portrait: not usable full-frame") : null)))));
}

// ---------------------------------------------------------------- jobs
async function viewJobs() {
  const list = await api("GET", "/api/jobs");
  app.append(h("h1", {}, "Jobs"), h("p", { class: "sub" }, "What the engine is doing and has done since the server started. One job runs at a time: a render uses every core."));
  if (!list.length) app.append(h("div", { class: "empty" }, "Nothing yet."));
  for (const j of list) {
    const box = h("div", { class: "panel" }, jobView(j, route));
    app.append(box);
    if (["running", "queued"].includes(j.state)) watch(j.id, jj => { box.innerHTML = ""; box.append(jobView(jj, route)); });
  }
}

route();
pollJobs();
