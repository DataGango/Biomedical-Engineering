const topic = document.body.dataset.specialty;
const publicationList = document.querySelector("#specialty-publications");
const status = document.querySelector("#specialty-status");
const emptyState = document.querySelector("#specialty-empty");

function externalLink(href, text) {
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.textContent = text;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function publicationElement(paper, index) {
  const article = document.createElement("article");
  article.className = "publication";
  const number = document.createElement("div");
  number.className = "paper-index";
  number.textContent = String(index + 1).padStart(2, "0");

  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "paper-title";
  title.append(externalLink(paper.url, paper.title || "Untitled publication"));
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
  links.append(externalLink(paper.url, paper.pmid ? "PUBMED RECORD" : "EUROPE PMC RECORD"));
  if (paper.doi) links.append(externalLink(`https://doi.org/${paper.doi}`, "DOI"));
  article.append(number, body, links);
  return article;
}

async function searchPublications(event) {
  event?.preventDefault();
  const button = document.querySelector("#specialty-refresh");
  button.disabled = true;
  status.textContent = "SEARCHING EUROPE PMC…";
  publicationList.replaceChildren();
  emptyState.hidden = true;
  const params = new URLSearchParams({
    topic,
    years: document.querySelector("#specialty-years").value,
    limit: document.querySelector("#specialty-limit").value,
    q: document.querySelector("#specialty-query").value.trim(),
  });
  try {
    const response = await fetch(`/api/specialty?${params}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    document.querySelector("#specialty-total").textContent = payload.total_matches.toLocaleString();
    document.querySelector("#specialty-extracted").textContent = payload.extracted_count.toLocaleString();
    document.querySelector("#specialty-abstracts").textContent = payload.abstract_count.toLocaleString();
    document.querySelector("#specialty-updated").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    payload.publications.forEach((paper, index) => publicationList.append(publicationElement(paper, index)));
    emptyState.hidden = payload.publications.length > 0;
    status.textContent = `${payload.total_matches.toLocaleString()} MATCHES · ${payload.extracted_count} RECORDS FETCHED · ${payload.abstract_count} ABSTRACTS · EUROPE PMC`;
  } catch (error) {
    status.textContent = `SEARCH FAILED · ${error.message}`;
    emptyState.hidden = false;
  } finally {
    button.disabled = false;
  }
}

document.querySelector("#specialty-search-form").addEventListener("submit", searchPublications);
document.querySelector("#specialty-refresh").addEventListener("click", searchPublications);
searchPublications();
