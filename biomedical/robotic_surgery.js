const paperList = document.querySelector("#robot-publications");
const paperStatus = document.querySelector("#robot-status");
const paperEmpty = document.querySelector("#robot-empty");
const nobelList = document.querySelector("#nobel-list");
const nobelStatus = document.querySelector("#nobel-status");

function link(href, text) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.textContent = text;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function showPaper(paper, index) {
  const article = document.createElement("article");
  article.className = "publication";
  const number = document.createElement("div");
  number.className = "paper-index";
  number.textContent = String(index + 1).padStart(2, "0");

  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "paper-title";
  title.append(link(paper.url, paper.title || "Untitled publication"));
  body.append(title);

  const meta = document.createElement("div");
  meta.className = "paper-meta";
  for (const value of [paper.journal, paper.year, (paper.authors || []).join(", ")]) {
    if (value) meta.append(document.createTextNode(value));
  }
  body.append(meta);
  const abstract = document.createElement("p");
  abstract.className = paper.abstract ? "paper-abstract" : "abstract-missing";
  abstract.textContent = paper.abstract || "Abstract not available in this record.";
  body.append(abstract);

  const links = document.createElement("div");
  links.className = "paper-links";
  links.append(link(paper.url, paper.pmid ? "PUBMED RECORD" : "EUROPE PMC RECORD"));
  if (paper.doi) links.append(link(`https://doi.org/${paper.doi}`, "DOI"));
  article.append(number, body, links);
  return article;
}

async function searchPapers(event) {
  event?.preventDefault();
  const button = document.querySelector("#robot-refresh");
  button.disabled = true;
  paperStatus.textContent = "SEARCHING EUROPE PMC…";
  paperList.replaceChildren();
  paperEmpty.hidden = true;
  const params = new URLSearchParams({
    years: document.querySelector("#robot-years").value,
    limit: document.querySelector("#robot-limit").value,
    q: document.querySelector("#robot-query").value.trim(),
  });
  try {
    const response = await fetch(`/api/robotic-surgery?${params}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    document.querySelector("#robot-total").textContent = payload.total_matches.toLocaleString();
    document.querySelector("#robot-extracted").textContent = payload.extracted_count.toLocaleString();
    document.querySelector("#robot-abstracts").textContent = payload.abstract_count.toLocaleString();
    document.querySelector("#robot-updated").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    payload.publications.forEach((paper, index) => paperList.append(showPaper(paper, index)));
    paperEmpty.hidden = payload.publications.length > 0;
    paperStatus.textContent = `${payload.total_matches.toLocaleString()} MATCHES · ${payload.extracted_count} RECORDS FETCHED · ${payload.abstract_count} ABSTRACTS · EUROPE PMC`;
  } catch (error) {
    paperStatus.textContent = `SEARCH FAILED · ${error.message}`;
    paperEmpty.hidden = false;
  } finally {
    button.disabled = false;
  }
}

function showPrize(prize) {
  const article = document.createElement("article");
  article.className = "nobel-prize";
  const year = document.createElement("div");
  year.className = "nobel-year";
  year.textContent = prize.year;
  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "nobel-title";
  title.textContent = prize.category;
  body.append(title);
  for (const laureate of prize.laureates) {
    const detail = document.createElement("p");
    detail.className = "nobel-laureates";
    detail.textContent = laureate.motivation ? `${laureate.name}: ${laureate.motivation}` : laureate.name;
    body.append(detail);
  }
  const links = document.createElement("div");
  links.className = "nobel-links";
  links.append(link(prize.url, "PRIZE SUMMARY"), link(prize.source_url, "OFFICIAL API RECORD"));
  body.append(links);
  article.append(year, body);
  return article;
}

async function loadNobelPrizes() {
  try {
    const response = await fetch("/api/nobel-medicine?limit=10");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    payload.prizes.forEach((prize) => nobelList.append(showPrize(prize)));
    nobelStatus.textContent = `${payload.prizes.length} RECENT MEDICINE PRIZES · SOURCE: OFFICIAL NOBEL PRIZE API`;
  } catch (error) {
    nobelStatus.textContent = `NOBEL DATA UNAVAILABLE · ${error.message}`;
    const source = link("https://www.nobelprize.org/prizes/medicine/", "Open the official Nobel Prize in Physiology or Medicine page.");
    nobelList.append(source);
  }
}

document.querySelector("#robot-search-form").addEventListener("submit", searchPapers);
document.querySelector("#robot-refresh").addEventListener("click", searchPapers);
searchPapers();
loadNobelPrizes();