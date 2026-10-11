const categories = ["nature", "medical", "bioengineering"];
const labels = { nature: "Nature", medical: "Medical", bioengineering: "Bioengineering" };
const resultsByCategory = new Map();
const savedSearches = new Map();
let activeCategory = "all";
let loadGeneration = 0;

const list = document.querySelector("#publication-list");
const status = document.querySelector("#field-status");
const emptyState = document.querySelector("#empty-state");

function setMetric(id, value) {
  document.querySelector(`#${id}`).textContent = value.toLocaleString();
}

function makeLink(href, label, newTab = true) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  if (newTab) {
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
  return link;
}

function createPublication(paper, category, index) {
  const article = document.createElement("article");
  article.className = "publication";

  const paperIndex = document.createElement("div");
  paperIndex.className = "paper-index";
  paperIndex.textContent = String(index + 1).padStart(2, "0");

  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "paper-title";
  title.append(makeLink(paper.url, paper.title || "Untitled publication", true));
  body.append(title);

  const meta = document.createElement("div");
  meta.className = "paper-meta";
  const tag = document.createElement("span");
  tag.className = "category-tag";
  tag.textContent = labels[category] || savedSearches.get(category)?.name || "Saved search";
  meta.append(tag);
  if (paper.journal) meta.append(document.createTextNode(paper.journal));
  if (paper.year) meta.append(document.createTextNode(paper.year));
  if (paper.authors?.length) meta.append(document.createTextNode(paper.authors.join(", ")));
  body.append(meta);

  if (paper.abstract) {
    const abstract = document.createElement("p");
    abstract.className = "paper-abstract";
    abstract.textContent = paper.abstract;
    body.append(abstract);
  } else {
    const missing = document.createElement("p");
    missing.className = "abstract-missing";
    missing.textContent = "Abstract not available in PubMed record";
    body.append(missing);
  }

  const links = document.createElement("div");
  links.className = "paper-links";
  links.append(makeLink(paper.url, "PUBMED"));
  if (paper.doi) links.append(makeLink(`https://doi.org/${paper.doi}`, "DOI"));
  article.append(paperIndex, body, links);
  return article;
}

function render() {
  list.replaceChildren();
  const query = document.querySelector("#search").value.trim().toLocaleLowerCase();
  const papers = [];
  for (const [category, data] of resultsByCategory) {
    if (activeCategory !== "all" && category !== activeCategory) continue;
    for (const paper of data.publications || []) {
      const searchable = [paper.title, paper.abstract, paper.journal, ...(paper.authors || [])].join(" ").toLocaleLowerCase();
      if (!query || searchable.includes(query)) papers.push({ paper, category });
    }
  }

  papers.forEach(({ paper, category }, index) => list.append(createPublication(paper, category, index)));
  emptyState.hidden = papers.length !== 0;

  const loaded = [...resultsByCategory.values()];
  setMetric("total-matches", loaded.reduce((sum, data) => sum + data.total_matches, 0));
  setMetric("extracted-count", loaded.reduce((sum, data) => sum + data.extracted_count, 0));
  setMetric("abstract-count", loaded.reduce((sum, data) => sum + data.abstract_count, 0));
  const errors = loaded.filter((data) => data.error).length;
  const loadedPapers = loaded.reduce((sum, data) => sum + data.extracted_count, 0);
  status.textContent = errors
    ? `${loaded.length - errors} OF ${loaded.length} SEARCHES LOADED · ${loadedPapers} RECORDS`
    : `${loaded.length} SEARCHES · ${loadedPapers} RECORDS EXTRACTED`;
}

function selectCategory(category) {
  activeCategory = category;
  document.querySelectorAll(".tab").forEach((tab) => {
    const selected = tab.dataset.category === category;
    tab.classList.toggle("selected", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  render();
}

function renderSavedSearchTabs() {
  const container = document.querySelector("#custom-search-tabs");
  container.replaceChildren();
  for (const [id, search] of savedSearches) {
    const tab = document.createElement("button");
    tab.className = "tab";
    tab.dataset.category = id;
    tab.type = "button";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(activeCategory === id));
    tab.textContent = search.name;
    tab.title = `${search.name}: ${search.query}`;
    tab.addEventListener("click", () => selectCategory(id));
    container.append(tab);
  }
}

async function loadSavedSearches(refreshNow = false) {
  const response = await fetch("/api/searches");
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);

  savedSearches.clear();
  for (const search of payload.searches) {
    let current = search;
    if (refreshNow) {
      const refreshed = await fetch(`/api/searches/${encodeURIComponent(search.id)}/refresh`, { method: "POST" });
      const refreshedPayload = await refreshed.json();
      if (refreshed.ok) current = refreshedPayload.search;
    }
    savedSearches.set(current.id, current);
    if (current.results) resultsByCategory.set(current.id, current.results);
  }
  renderSavedSearchTabs();
}

async function syncSavedSearches() {
  try {
    const response = await fetch("/api/searches");
    const payload = await response.json();
    if (!response.ok) return;
    let changed = false;
    for (const search of payload.searches) {
      const previous = savedSearches.get(search.id);
      if (previous?.refreshed_at !== search.refreshed_at) changed = true;
      savedSearches.set(search.id, search);
      if (search.results) resultsByCategory.set(search.id, search.results);
    }
    if (changed) {
      renderSavedSearchTabs();
      render();
      const latest = payload.searches.map((search) => search.refreshed_at).filter(Boolean).sort().at(-1);
      if (latest) {
        document.querySelector("#updated-at").textContent = new Date(latest).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      }
    }
  } catch {
    // Keep the last successful result set visible if a background sync fails.
  }
}

async function loadCategory(category, limit, query, generation) {
  const parameters = new URLSearchParams({ category, limit: String(limit) });
  if (query) parameters.set("q", query);
  try {
    const response = await fetch(`/api/search?${parameters}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    if (generation === loadGeneration) resultsByCategory.set(category, payload);
  } catch (error) {
    if (generation === loadGeneration) resultsByCategory.set(category, { error: error.message, total_matches: 0, extracted_count: 0, abstract_count: 0, publications: [] });
  }
}

async function refreshSearches(refreshSaved = false) {
  const generation = ++loadGeneration;
  resultsByCategory.clear();
  list.replaceChildren();
  emptyState.hidden = true;
  status.textContent = "SEARCHING EUROPE PMC FOR RECENT RECORDS…";
  for (const id of ["total-matches", "extracted-count", "abstract-count"]) setMetric(id, 0);

  const limit = Number(document.querySelector("#limit").value);
  const query = document.querySelector("#search").value.trim();
  await Promise.all(categories.map((category) => loadCategory(category, limit, query, generation)));
  try {
    await loadSavedSearches(refreshSaved);
  } catch (error) {
    status.textContent = `SAVED SEARCHES UNAVAILABLE · ${error.message}`;
  }
  if (generation !== loadGeneration) return;

  const errors = [...resultsByCategory.values()].filter((result) => result.error);
  document.querySelector("#updated-at").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  render();
  if (errors.length === categories.length) {
    list.replaceChildren();
    const note = document.createElement("p");
    note.className = "error-note";
    note.textContent = `${errors[0].error} Check your internet connection and refresh.`;
    list.append(note);
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    selectCategory(tab.dataset.category);
  });
});

document.querySelector("#refresh").addEventListener("click", () => refreshSearches(true));
document.querySelector("#limit").addEventListener("change", refreshSearches);
document.querySelector("#search").addEventListener("input", render);
document.querySelector("#global-search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  button.textContent = "Saving and extracting…";
  try {
    const response = await fetch("/api/searches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.querySelector("#search-name").value,
        query: document.querySelector("#search-query").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    const saved = payload.search;
    savedSearches.set(saved.id, saved);
    if (saved.results) resultsByCategory.set(saved.id, saved.results);
    renderSavedSearchTabs();
    selectCategory(saved.id);
    form.reset();
    document.querySelector("#updated-at").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (error) {
    status.textContent = `SEARCH NOT SAVED · ${error.message}`;
  } finally {
    button.disabled = false;
    button.innerHTML = "＋ Save &amp; extract";
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    document.querySelector("#search").focus();
  }
});

refreshSearches();
window.setInterval(syncSavedSearches, 60_000);