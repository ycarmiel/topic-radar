"use strict";

// ── Card labels per lens ─────────────────────────────────────
const LENS_LABELS = {
  general:    { overview: "Overview",        keypoints: "Key Points",             trends: "Trends & Context",  gaps: "Gaps & Caveats" },
  scientific: { overview: "Abstract",        keypoints: "Key Findings",           trends: "Research Trends",   gaps: "Limitations & Gaps" },
  startup:    { overview: "Summary",         keypoints: "Opportunities",          trends: "Market Trends",     gaps: "Risks & Challenges" },
  vc:         { overview: "Market Overview", keypoints: "Investment Highlights",  trends: "Market Trends",     gaps: "Due Diligence Notes" },
};

// ── DOM refs ─────────────────────────────────────────────────
const searchForm    = document.getElementById("search-form");
const topicInput    = document.getElementById("topic-input");
const searchBtn     = document.getElementById("search-btn");
const stopBtn       = document.getElementById("stop-btn");
const statusBar     = document.getElementById("status-bar");
const emptyState    = document.getElementById("empty-state");

const overviewText  = document.getElementById("overview-text");
const keypointsList = document.getElementById("keypoints-list");
const trendsText    = document.getElementById("trends-text");
const gapsText      = document.getElementById("gaps-text");
const sourceList    = document.getElementById("source-list");

const labelOverview  = document.getElementById("label-overview");
const labelKeypoints = document.getElementById("label-keypoints");
const labelTrends    = document.getElementById("label-trends");
const labelGaps      = document.getElementById("label-gaps");

const historyList   = document.getElementById("history-list");

const cardSources   = document.getElementById("card-sources");
const contentCards  = ["card-overview","card-keypoints","card-trends","card-gaps"]
  .map(id => document.getElementById(id));
const allCards      = [cardSources, ...contentCards];

// ── Active request controller ─────────────────────────────────
let activeController = null;

// ── Helpers ───────────────────────────────────────────────────
function getLens() {
  return (document.querySelector("input[name='lens']:checked") || {}).value || "general";
}

function setCardLabels(lens) {
  const L = LENS_LABELS[lens] || LENS_LABELS.general;
  labelOverview.textContent  = L.overview;
  labelKeypoints.textContent = L.keypoints;
  labelTrends.textContent    = L.trends;
  labelGaps.textContent      = L.gaps;
}

// ── Search ────────────────────────────────────────────────────
searchForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const topic = topicInput.value.trim();
  if (topic) startResearch(topic, getLens());
});

async function startResearch(topic, lens) {
  // Cancel any in-flight request
  if (activeController) { activeController.abort(); activeController = null; }

  resetDashboard();
  setCardLabels(lens);
  setStatus(`<span class="spinner"></span>Researching "${esc(topic)}"…`);
  setLoading(true);

  activeController = new AbortController();

  try {
    const resp = await fetch(
      `/api/stream?topic=${encodeURIComponent(topic)}&lens=${encodeURIComponent(lens)}`,
      { signal: activeController.signal }
    );

    if (!resp.ok) { showError(`Server error ${resp.status}`); return; }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buf += decoder.decode(value, { stream: true });

      // Flush complete SSE messages (delimited by \n\n)
      let boundary;
      while ((boundary = buf.indexOf("\n\n")) !== -1) {
        const chunk = buf.slice(0, boundary);
        buf = buf.slice(boundary + 2);
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ")) handleData(line.slice(6));
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      showError("Connection lost. Please try again.");
    }
  } finally {
    activeController = null;
    setLoading(false);
  }
}

function handleData(raw) {
  if (raw === "[DONE]") {
    setStatus("Done.", "success");
    return;
  }

  let msg;
  try { msg = JSON.parse(raw); } catch { return; }

  switch (msg.type) {
    case "status":
      setStatus(`<span class="spinner"></span>${esc(msg.text)}`);
      break;

    case "source":
      appendSource(msg.data);
      break;

    case "structured":
      populateCards(msg.data);
      showContentCards();
      break;

    case "history_id":
      loadHistory();
      break;

    case "error":
      showError(msg.message);
      break;
  }
}

// ── Populate cards ────────────────────────────────────────────
function populateCards(s) {
  overviewText.textContent = s.overview || "";
  trendsText.textContent   = s.trends   || "";
  gapsText.textContent     = s.gaps_and_caveats || "";

  keypointsList.innerHTML = "";
  (s.key_points || []).forEach(pt => {
    const li = document.createElement("li");
    li.textContent = pt;
    keypointsList.appendChild(li);
  });

  // Sources from structured (fill any not already streamed)
  if (s.sources && s.sources.length && !sourceList.children.length) {
    s.sources.slice(0, 5).forEach(appendSource);
  }
}

function appendSource(src) {
  if (!src.url || document.querySelector(`[data-url="${CSS.escape(src.url)}"]`)) return;
  showSourcesCard();

  const host = (() => {
    try { return new URL(src.url).hostname.replace("www.", ""); } catch { return src.url; }
  })();

  const a = document.createElement("a");
  a.className   = "source-chip";
  a.href        = esc(src.url);
  a.target      = "_blank";
  a.rel         = "noopener";
  a.dataset.url = src.url;
  a.innerHTML   = `<span class="chip-title">${esc(src.title || host)}</span>
                   <span class="chip-url">${esc(host)}</span>`;
  sourceList.appendChild(a);
}

// ── Card visibility ───────────────────────────────────────────
function showSourcesCard() {
  emptyState.classList.add("hidden");
  cardSources.classList.remove("hidden");
}

function showContentCards() {
  emptyState.classList.add("hidden");
  contentCards.forEach(c => c.classList.remove("hidden"));
}

// ── History ───────────────────────────────────────────────────
async function loadHistory() {
  try {
    const entries = await fetch("/api/history").then(r => r.json());
    historyList.innerHTML = "";
    if (!entries.length) {
      historyList.innerHTML = '<li class="history-empty">No searches yet.</li>';
      return;
    }
    entries.forEach(e => {
      const li   = document.createElement("li");
      li.className = "history-item";
      const lens = e.lens || "general";
      li.innerHTML = `
        <div class="h-lens-dot ${esc(lens)}"></div>
        <div>
          <div class="h-topic" title="${esc(e.topic)}">${esc(e.topic)}</div>
          <div class="h-date">${fmtDate(e.created_at)}</div>
        </div>`;
      li.addEventListener("click", () => loadEntry(e.id, li));
      historyList.appendChild(li);
    });
  } catch (err) { console.error(err); }
}

async function loadEntry(id, itemEl) {
  document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
  if (itemEl) itemEl.classList.add("active");
  try {
    const entry = await fetch(`/api/history/${id}`).then(r => r.json());
    topicInput.value = entry.topic;

    const lens = entry.summary?.lens || "general";
    const pill = document.querySelector(`input[name='lens'][value='${lens}']`);
    if (pill) pill.checked = true;

    resetDashboard();
    setCardLabels(lens);
    populateCards(entry.summary);
    showSourcesCard();
    showContentCards();
    setStatus(`Loaded: "${esc(entry.topic)}"`, "success");
  } catch { setStatus("Failed to load.", "error"); }
}

loadHistory();

// ── UI helpers ────────────────────────────────────────────────
function resetDashboard() {
  overviewText.textContent = "";
  keypointsList.innerHTML  = "";
  trendsText.textContent   = "";
  gapsText.textContent     = "";
  sourceList.innerHTML     = "";
  statusBar.textContent    = "";
  statusBar.className      = "status";
  allCards.forEach(c => c.classList.add("hidden"));
  emptyState.classList.remove("hidden");
}

function setStatus(html, type = "") {
  statusBar.innerHTML = html;
  statusBar.className = `status ${type}`.trim();
}

function showError(message) {
  document.getElementById("error-banner")?.remove();
  const banner = document.createElement("div");
  banner.id        = "error-banner";
  banner.className = "error-banner";
  banner.innerHTML = `
    <span class="error-icon">⚠</span>
    <span class="error-msg">${esc(message)}</span>
    <button class="error-close" onclick="this.parentElement.remove()">✕</button>`;
  document.querySelector(".layout").prepend(banner);
  setStatus("", "");
}

function setLoading(on) {
  searchBtn.disabled  = on;
  topicInput.disabled = on;
  stopBtn.classList.toggle("hidden", !on);
}

stopBtn.addEventListener("click", () => {
  if (activeController) { activeController.abort(); activeController = null; }
  setLoading(false);
  setStatus("Stopped.", "");
});

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleString(undefined, { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
  } catch { return iso; }
}

function esc(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
