// app.js
//
// This file handles the  browser logic.
// It listens for user input, sends the question to the backend API,
// reads the JSON response, and renders the summary and wine cards.
//


const API_BASE_URL = "http://127.0.0.1:8000";
const QUERY_ENDPOINT = `${API_BASE_URL}/query`;

const form = document.getElementById("query-form");
const questionInput = document.getElementById("question-input");
const askButton = document.getElementById("ask-button");
const statusSection = document.getElementById("status-section");

const responseSection = document.getElementById("response-section");
const summaryText = document.getElementById("summary-text");

const metaRow = document.getElementById("meta-row");
const responseTypeEl = document.getElementById("response-type");
const matchCountEl = document.getElementById("match-count");
const rankingBasisEl = document.getElementById("ranking-basis");

const resultsSection = document.getElementById("results-section");
const resultsGrid = document.getElementById("results-grid");

const exampleChips = document.querySelectorAll(".example-chip");

/**
 * Show a small status message above the response area.
 */
function setStatus(message, type = "info") {
  statusSection.textContent = message;
  statusSection.className = `status-section ${type}`;
}

/**
 * Clear the current status message.
 */
function clearStatus() {
  statusSection.textContent = "";
  statusSection.className = "status-section";
}

/**
 * Hide all response content before the next request.
 */
function resetResponseUI() {
  responseSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  metaRow.classList.add("hidden");

  summaryText.textContent = "";
  responseTypeEl.textContent = "";
  matchCountEl.textContent = "";
  rankingBasisEl.textContent = "";
  resultsGrid.innerHTML = "";
}

/**
 * Return a fallback text when a field is missing.
 */
function safeText(value, fallback = "Not available") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

/**
 * Format price consistently for display.
 */
function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Price unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(Number(value));
}

/**
 * Build one wine result card.
 */
function createWineCard(wine) {
  const card = document.createElement("article");
  card.className = "wine-card";

  const imageWrapper = document.createElement("div");
  imageWrapper.className = "wine-image-wrapper";

  if (wine.image_url) {
    const img = document.createElement("img");
    img.className = "wine-image";
    img.src = wine.image_url;
    img.alt = `${safeText(wine.name, "Wine bottle")} bottle image`;
    img.loading = "lazy";
    imageWrapper.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "wine-image-placeholder";
    placeholder.textContent = "No image";
    imageWrapper.appendChild(placeholder);
  }

  const body = document.createElement("div");
  body.className = "wine-card-body";

  const title = document.createElement("h3");
  title.className = "wine-name";
  title.textContent = safeText(wine.name);

  const producer = document.createElement("p");
  producer.className = "wine-producer";
  producer.textContent = safeText(wine.producer, "Unknown producer");

  const facts = document.createElement("div");
  facts.className = "wine-facts";

  const factLines = [
    `Price: ${formatPrice(wine.price)}`,
    `Color: ${safeText(wine.color)}`,
    `Country: ${safeText(wine.country)}`,
    `Region: ${safeText(wine.region)}`,
    `Varietal: ${safeText(wine.varietal)}`,
    `Vintage: ${safeText(wine.vintage)}`,
    `Best score: ${safeText(wine.best_score)}`,
    `Average score: ${safeText(wine.avg_score)}`,
    `Rating count: ${safeText(wine.rating_count, "0")}`
  ];

  factLines.forEach((line) => {
    const p = document.createElement("p");
    p.textContent = line;
    facts.appendChild(p);
  });

  body.appendChild(title);
  body.appendChild(producer);
  body.appendChild(facts);

  if (wine.reference_url) {
    const link = document.createElement("a");
    link.className = "wine-link";
    link.href = wine.reference_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open bottle page";
    body.appendChild(link);
  }

  card.appendChild(imageWrapper);
  card.appendChild(body);

  return card;
}

/**
 * Render the backend response into the page.
 */
function renderResponse(data) {
  responseSection.classList.remove("hidden");

  summaryText.textContent = safeText(data.summary, "No summary returned.");

  responseTypeEl.textContent = safeText(data.response_type);
  matchCountEl.textContent = `${safeText(data.returned_count, 0)} shown / ${safeText(data.total_matches, 0)} total`;
  rankingBasisEl.textContent = safeText(data.ranking_basis_text, "Not provided");
  metaRow.classList.remove("hidden");

  resultsGrid.innerHTML = "";

  if (data.show_results && Array.isArray(data.wines) && data.wines.length > 0) {
    data.wines.forEach((wine) => {
      resultsGrid.appendChild(createWineCard(wine));
    });
    resultsSection.classList.remove("hidden");
  } else {
    resultsSection.classList.add("hidden");
  }
}

/**
 * Send the user's question to the backend.
 */
async function submitQuestion(question) {
  resetResponseUI();
  setStatus("Searching the collection...", "loading");
  askButton.disabled = true;

  try {
    const response = await fetch(QUERY_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question,
        limit: 5
      })
    });

    const data = await response.json();

    if (!response.ok) {
      // FastAPI errors usually return { detail: ... }
      const detail = data?.detail || "The backend returned an error.";
      throw new Error(detail);
    }

    renderResponse(data);
    clearStatus();
  } catch (error) {
    setStatus(`Request failed: ${error.message}`, "error");
  } finally {
    askButton.disabled = false;
  }
}

/**
 * Handle form submission.
 */
form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = questionInput.value.trim();
  if (!question) {
    setStatus("Enter a question before submitting.", "error");
    return;
  }

  await submitQuestion(question);
});

/**
 * Let example chips fill the input and submit quickly.
 */
exampleChips.forEach((chip) => {
  chip.addEventListener("click", async () => {
    const question = chip.dataset.question || "";
    questionInput.value = question;
    await submitQuestion(question);
  });
});
window.wineAssistantUI = {
  submitQuestion,
  setStatus,
  clearStatus,
  questionInput
};