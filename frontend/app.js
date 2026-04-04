/*
app.js

This file handles the main frontend behavior for the wine assistant.
It sends user questions to the backend API and renders the returned
summary and wine results.

Why this file exists:
- It gives typed input and voice input one shared backend request path.
- It keeps rendering logic separate from speech input and speech output.
- It exposes a small shared UI API for voice.js and tts.js.
*/

const API_BASE_URL = "http://127.0.0.1:8000";
const QUERY_ENDPOINT = `${API_BASE_URL}/query`;

const form = document.getElementById("query-form");
const questionInput = document.getElementById("question-input");
const askButton = document.getElementById("ask-button");
const statusSection = document.getElementById("status-section");

const responseSection = document.getElementById("response-section");
const summaryText = document.getElementById("summary-text");

const followupSection = document.getElementById("followup-section");
const followupTitle = document.getElementById("followup-title");
const followupChips = document.getElementById("followup-chips");

const metaRow = document.getElementById("meta-row");
const responseTypeEl = document.getElementById("response-type");
const matchCountEl = document.getElementById("match-count");
const rankingBasisEl = document.getElementById("ranking-basis");

const resultsSection = document.getElementById("results-section");
const resultsGrid = document.getElementById("results-grid");

const exampleChips = document.querySelectorAll(".example-chip");

/**
 * Show a status message above the response area.
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
 * Normalize extra whitespace.
 */
function normalizeQuestionText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

/**
 * Hide all response content before a new request.
 */
function resetResponseUI() {
  responseSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  metaRow.classList.add("hidden");
  followupSection.classList.add("hidden");

  summaryText.textContent = "";
  responseTypeEl.textContent = "";
  matchCountEl.textContent = "";
  rankingBasisEl.textContent = "";
  resultsGrid.innerHTML = "";
  followupTitle.textContent = "Try one of these next:";
  followupChips.innerHTML = "";
}

/**
 * Return a fallback display value for missing fields.
 */
function safeText(value, fallback = "Not available") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

/**
 * Format numeric price values for display.
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
 * Create one wine result card.
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
 * Return suggestion config based on response state.
 */
function getFollowupConfig(data) {
  const responseType = data?.response_type || "";
  const missingFields = data?.query?.missing_fields || [];

  if (responseType === "too_many_matches") {
    return {
      title: "Narrow it down:",
      suggestions: [
        { label: "Under $30", value: "under $30", mode: "budget" },
        { label: "Red wines", value: "red", mode: "color" },
        { label: "From France", value: "from France", mode: "append" },
        { label: "Cabernet Sauvignon", value: "Cabernet Sauvignon", mode: "varietal" }
      ]
    };
  }

  if (responseType === "clarification" && missingFields.includes("budget")) {
    return {
      title: "Add a budget:",
      suggestions: [
        { label: "Under $25", value: "under $25", mode: "budget" },
        { label: "Under $50", value: "under $50", mode: "budget" },
        { label: "Between $30 and $60", value: "between $30 and $60", mode: "budget" }
      ]
    };
  }

  if (responseType === "clarification" && missingFields.includes("color")) {
    return {
      title: "Choose a style:",
      suggestions: [
        { label: "Red", value: "red", mode: "color" },
        { label: "White", value: "white", mode: "color" },
        { label: "Sparkling", value: "sparkling", mode: "color" },
        { label: "Rosé", value: "rosé", mode: "color" }
      ]
    };
  }

  if (responseType === "clarification" && missingFields.includes("varietal")) {
    return {
      title: "Pick a grape:",
      suggestions: [
        { label: "Chardonnay", value: "Chardonnay", mode: "varietal" },
        { label: "Pinot Noir", value: "Pinot Noir", mode: "varietal" },
        { label: "Cabernet Sauvignon", value: "Cabernet Sauvignon", mode: "varietal" },
        { label: "Sauvignon Blanc", value: "Sauvignon Blanc", mode: "varietal" }
      ]
    };
  }

  if (responseType === "no_results") {
    return {
      title: "Try a broader search:",
      suggestions: [
        { label: "Under $50", value: "under $50", mode: "budget" },
        { label: "Red wines", value: "red", mode: "color" },
        { label: "From France", value: "from France", mode: "append" },
        { label: "Cabernet Sauvignon", value: "Cabernet Sauvignon", mode: "varietal" }
      ]
    };
  }

  return {
    title: "",
    suggestions: []
  };
}

/**
 * Replace an existing budget phrase, or append a new one.
 */
function applyBudgetSuggestion(question, budgetPhrase) {
  let next = question;

  const budgetPatterns = [
    /\bbetween\s+\$?\d+(?:\.\d+)?\s+(?:and|to)\s+\$?\d+(?:\.\d+)?\b/i,
    /\b(?:under|below|less than|cheaper than|up to|max|maximum of|over|above|more than|at least|min|minimum of)\s+\$?\d+(?:\.\d+)?\b/i
  ];

  let replaced = false;

  budgetPatterns.forEach((pattern) => {
    if (!replaced && pattern.test(next)) {
      next = next.replace(pattern, budgetPhrase);
      replaced = true;
    }
  });

  if (!replaced) {
    next = `${next} ${budgetPhrase}`;
  }

  return normalizeQuestionText(next);
}

/**
 * Apply a color suggestion in a more natural way.
 */
function applyColorSuggestion(question, color) {
  let next = question;

  if (/\b(red|white|sparkling|rose|rosé)\s+wines?\b/i.test(next)) {
    next = next.replace(/\b(red|white|sparkling|rose|rosé)\s+(wine|wines)\b/i, `${color} $2`);
    return normalizeQuestionText(next);
  }

  if (/\ba wine\b/i.test(next)) {
    next = next.replace(/\ba wine\b/i, `a ${color} wine`);
    return normalizeQuestionText(next);
  }

  if (/\bwines\b/i.test(next)) {
    next = next.replace(/\bwines\b/i, `${color} wines`);
    return normalizeQuestionText(next);
  }

  if (/\bwine\b/i.test(next)) {
    next = next.replace(/\bwine\b/i, `${color} wine`);
    return normalizeQuestionText(next);
  }

  return normalizeQuestionText(`${next} ${color}`);
}

/**
 * Apply a varietal suggestion in a more natural way.
 */
function applyVarietalSuggestion(question, varietal) {
  let next = question;

  if (/\bby grape\b/i.test(next)) {
    next = next.replace(/\bby grape\b/i, varietal);
    return normalizeQuestionText(next);
  }

  if (/\ba wine\b/i.test(next)) {
    next = next.replace(/\ba wine\b/i, `a ${varietal}`);
    return normalizeQuestionText(next);
  }

  if (/\bwines\b/i.test(next)) {
    next = next.replace(/\bwines\b/i, `${varietal} wines`);
    return normalizeQuestionText(next);
  }

  return normalizeQuestionText(`${next} ${varietal}`);
}

/**
 * Build the next question when a follow-up chip is clicked.
 */
function buildFollowupQuestion(data, suggestion) {
  const currentQuestion = normalizeQuestionText(
    data?.query?.original_question || questionInput.value || ""
  );

  if (!currentQuestion) {
    return suggestion.value;
  }

  switch (suggestion.mode) {
    case "budget":
      return applyBudgetSuggestion(currentQuestion, suggestion.value);

    case "color":
      return applyColorSuggestion(currentQuestion, suggestion.value);

    case "varietal":
      return applyVarietalSuggestion(currentQuestion, suggestion.value);

    case "append":
    default:
      return normalizeQuestionText(`${currentQuestion} ${suggestion.value}`);
  }
}

/**
 * Render dynamic follow-up chips for clarification and refinement states.
 */
function renderFollowupSuggestions(data) {
  const config = getFollowupConfig(data);

  followupChips.innerHTML = "";

  if (!config.suggestions.length) {
    followupSection.classList.add("hidden");
    return;
  }

  followupTitle.textContent = config.title;

  config.suggestions.forEach((suggestion) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "followup-chip";
    button.textContent = suggestion.label;

    button.addEventListener("click", async () => {
      const nextQuestion = buildFollowupQuestion(data, suggestion);
      questionInput.value = nextQuestion;
      await submitQuestion(nextQuestion);
    });

    followupChips.appendChild(button);
  });

  followupSection.classList.remove("hidden");
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

  renderFollowupSuggestions(data);

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
 * Submit a question to the backend.
 * This function is intentionally shared by typed input and voice input.
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
      const detail = data?.detail || "The backend returned an error.";
      throw new Error(detail);
    }

    renderResponse(data);

    window.wineAssistantUI.lastResponse = data;

    window.dispatchEvent(
      new CustomEvent("wine-response-ready", {
        detail: data
      })
    );

    clearStatus();
  } catch (error) {
    setStatus(`Request failed: ${error.message}`, "error");
  } finally {
    askButton.disabled = false;
  }
}

/**
 * Handle typed form submission.
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
 * Let example chips quickly populate and submit a question.
 */
exampleChips.forEach((chip) => {
  chip.addEventListener("click", async () => {
    const question = chip.dataset.question || "";
    questionInput.value = question;
    await submitQuestion(question);
  });
});

/**
 * Shared UI API used by voice.js and tts.js.
 */
window.wineAssistantUI = {
  submitQuestion,
  setStatus,
  clearStatus,
  questionInput,
  lastResponse: null
};