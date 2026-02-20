"use strict";

// ── Content type metadata ──────────────────────────────────────────────────────
const CONTENT_META = {
  papers:      { label: "📄 Research Papers",  emptyMsg: "No research papers found." },
  news:        { label: "📰 News & Articles",   emptyMsg: "No articles found." },
  discussions: { label: "💬 Discussions",        emptyMsg: "No discussions found." },
  videos:      { label: "🎥 Videos",            emptyMsg: "No videos found." },
  code:        { label: "💻 Code",              emptyMsg: "No code results found." },
};

const INTENT_STYLES = {
  academic:    { label: "Academic",    cls: "bg-purple-50 text-purple-700 border-purple-200" },
  tutorial:    { label: "Tutorial",    cls: "bg-green-50  text-green-700  border-green-200"  },
  business:    { label: "Business",    cls: "bg-amber-50  text-amber-700  border-amber-200"  },
  exploratory: { label: "Exploratory", cls: "bg-blue-50   text-blue-700   border-blue-200"   },
};

// ── DOM refs (results page) ────────────────────────────────────────────────────
const loadingState      = document.getElementById("loading-state");
const errorStateEl      = document.getElementById("error-state");
const errorMessageEl    = document.getElementById("error-message");
const resultsContainer  = document.getElementById("results-container");
const intentBadgeEl     = document.getElementById("intent-badge");
const resultCountEl     = document.getElementById("result-count");
const sectionCountEl    = document.getElementById("section-count");
const timeRangeBadgeEl  = document.getElementById("time-range-badge");
const summaryTextEl     = document.getElementById("summary-text");
const themesRowEl       = document.getElementById("themes-row");
const themesListEl      = document.getElementById("themes-list");
const trendsRowEl       = document.getElementById("trends-row");
const trendsListEl      = document.getElementById("trends-list");
const sectionsContainer = document.getElementById("sections-container");
const showAllRowEl      = document.getElementById("show-all-row");
const showAllBtnEl      = document.getElementById("show-all-btn");

// ── Auto-fetch on results page ─────────────────────────────────────────────────
if (typeof QUERY !== "undefined" && QUERY) {
  fetchResults(QUERY);
}

// ── Fetch ──────────────────────────────────────────────────────────────────────
async function fetchResults(query) {
  setUiState("loading");

  try {
    const resp = await fetch("/api/search", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ query }),
    });

    const data = await resp.json();
    if (!resp.ok || data.error) throw new Error(data.error || `HTTP ${resp.status}`);

    renderResults(data);
  } catch (err) {
    setUiState("error", err.message || "An unexpected error occurred.");
  }
}

// ── Render ─────────────────────────────────────────────────────────────────────
function renderResults(data) {
  // Intent badge
  const intentMeta = INTENT_STYLES[data.intent] || INTENT_STYLES.exploratory;
  if (intentBadgeEl) {
    intentBadgeEl.textContent = `${intentMeta.label} search`;
    intentBadgeEl.className =
      `px-2.5 py-1 text-xs font-medium rounded-full border ${intentMeta.cls}`;
  }

  // Time range badge
  if (timeRangeBadgeEl && data.time_range) {
    timeRangeBadgeEl.textContent = `📅 ${data.time_range}`;
    timeRangeBadgeEl.classList.remove("hidden");
  }

  // Executive summary
  if (data.summary) {
    if (summaryTextEl) summaryTextEl.textContent = data.summary.overview || "";

    if (data.summary.key_themes?.length && themesListEl) {
      themesListEl.innerHTML = data.summary.key_themes
        .map(t => `<span class="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full">${esc(t)}</span>`)
        .join("");
      themesRowEl?.classList.remove("hidden");
    }

    if (data.summary.notable_trends?.length && trendsListEl) {
      trendsListEl.innerHTML = data.summary.notable_trends
        .map(t => `<li>${esc(t)}</li>`)
        .join("");
      trendsRowEl?.classList.remove("hidden");
    }
  }

  // Result sections
  const sections = data.sections || [];
  const totalResults = sections.reduce((n, s) => n + s.results.length, 0);

  if (resultCountEl) resultCountEl.textContent = totalResults;
  if (sectionCountEl) sectionCountEl.textContent = sections.length;

  if (sectionsContainer) {
    sectionsContainer.innerHTML = "";
    sections.forEach((section, idx) => {
      sectionsContainer.appendChild(buildSection(section, idx === 0));
    });
  }

  if (showAllRowEl && sections.length > 1) {
    showAllRowEl.classList.remove("hidden");
  }

  setUiState("results");
}

// ── Section builder ────────────────────────────────────────────────────────────
function buildSection(section, expanded) {
  const meta = CONTENT_META[section.type] || { label: section.type };

  const wrapper = document.createElement("div");
  wrapper.className = "mb-7";

  // Section header
  const header = document.createElement("div");
  header.className = "flex items-center justify-between mb-3";
  header.innerHTML = `
    <h2 class="font-semibold text-gray-900 flex items-center gap-2 text-sm">
      ${esc(meta.label)}
      <span class="text-xs font-normal text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
        ${section.results.length}
      </span>
    </h2>
    <button
      class="toggle-btn text-xs text-gray-400 hover:text-gray-600 transition-colors
             px-2 py-1 rounded hover:bg-gray-100"
      aria-expanded="${expanded}"
    >
      ${expanded ? "Hide" : "Show"}
    </button>
  `;

  // Section body (collapsible)
  const body = document.createElement("div");
  body.className = `section-body ${expanded ? "" : "collapsed"}`;
  body.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      ${section.results.map(r => buildCard(r)).join("")}
    </div>
  `;

  // Toggle logic
  const toggleBtn = header.querySelector(".toggle-btn");
  toggleBtn.addEventListener("click", () => {
    const isCollapsed = body.classList.toggle("collapsed");
    toggleBtn.textContent = isCollapsed ? "Show" : "Hide";
    toggleBtn.setAttribute("aria-expanded", String(!isCollapsed));
  });

  wrapper.appendChild(header);
  wrapper.appendChild(body);
  return wrapper;
}

// ── Card builder ───────────────────────────────────────────────────────────────
function buildCard(result) {
  const domain = safeHostname(result.url);
  const summary = result.ai_summary || result.snippet || "";

  return `
    <a
      href="${esc(result.url)}"
      target="_blank"
      rel="noopener noreferrer"
      class="result-card block bg-white border border-gray-200 rounded-xl p-5
             shadow-sm hover:border-blue-300 group"
      aria-label="${esc(result.title)}"
    >
      <div class="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
        <span>${esc(domain)}</span>
        ${result.published_date
          ? `<span aria-hidden="true">·</span><span>${esc(result.published_date)}</span>`
          : ""}
      </div>
      <h3 class="font-medium text-gray-900 group-hover:text-blue-600 transition-colors
                 line-clamp-2 mb-2 text-sm leading-snug">
        ${esc(result.title)}
      </h3>
      <p class="text-xs text-gray-500 line-clamp-3 leading-relaxed">
        ${esc(summary)}
      </p>
      ${result.relevance_explanation ? `
        <div class="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400 italic">
          ${esc(result.relevance_explanation)}
        </div>
      ` : ""}
    </a>
  `;
}

// ── Show all ───────────────────────────────────────────────────────────────────
if (showAllBtnEl) {
  showAllBtnEl.addEventListener("click", () => {
    document.querySelectorAll(".section-body").forEach(el => {
      el.classList.remove("collapsed");
    });
    document.querySelectorAll(".toggle-btn").forEach(btn => {
      btn.textContent = "Hide";
      btn.setAttribute("aria-expanded", "true");
    });
    showAllRowEl?.classList.add("hidden");
  });
}

// ── UI state ───────────────────────────────────────────────────────────────────
function setUiState(state, errorMsg = "") {
  loadingState?.classList.toggle("hidden", state !== "loading");
  errorStateEl?.classList.toggle("hidden", state !== "error");
  resultsContainer?.classList.toggle("hidden", state !== "results");

  if (state === "error" && errorMessageEl) {
    errorMessageEl.textContent = errorMsg;
  }
}

// ── Utilities ──────────────────────────────────────────────────────────────────
function safeHostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url || "";
  }
}

function esc(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
