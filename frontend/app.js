/*
app.js

This file handles the main frontend behavior for the wine assistant.
It sends user questions to the backend API and renders the returned
summary and wine results.
*/

const API_BASE_URL = "http://127.0.0.1:8000";
const QUERY_ENDPOINT = `${API_BASE_URL}/query`;

const DEFAULT_PAGE_SIZE = 12;

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

const paginationSection = document.getElementById("pagination-section");
const prevPageButton = document.getElementById("prev-page-button");
const nextPageButton = document.getElementById("next-page-button");
const pageIndicator = document.getElementById("page-indicator");

const exampleChips = document.querySelectorAll(".example-chip");

const appState = {
  currentQuestion: "",
  currentPage: 1,
  currentPageSize: DEFAULT_PAGE_SIZE,
  isLoading: false
};


function setStatus(message, type = "info") {
  statusSection.textContent = message;
  statusSection.className = `status-section ${type}`;
}


function clearStatus() {
  statusSection.textContent = "";
  statusSection.className = "status-section";
}


function normalizeQuestionText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}


function resetResponseUI() {
  responseSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  metaRow.classList.add("hidden");
  followupSection.classList.add("hidden");
  paginationSection.classList.add("hidden");

  summaryText.textContent = "";
  responseTypeEl.textContent = "";
  matchCountEl.textContent = "";
  rankingBasisEl.textContent = "";
  resultsGrid.innerHTML = "";
  followupTitle.textContent = "Try one of these next:";
  followupChips.innerHTML = "";
  pageIndicator.textContent = "Page 1 of 1";
}


function safeText(value, fallback = "Not available") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}


function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Price unavailable";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(Number(value));
}


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


function getFollowupConfig(data) {
  const responseType = data?.response_type || "";
  const suggestions = Array.isArray(data?.followup_suggestions)
    ? data.followup_suggestions
    : [];

  if (responseType === "clarification") {
    return {
      title: "Add one of these details:",
      suggestions
    };
  }

  if (responseType === "no_results") {
    return {
      title: "Try one of these grounded alternatives:",
      suggestions
    };
  }

  if (data?.needs_refinement) {
    return {
      title: "Narrow it down:",
      suggestions
    };
  }

  return {
    title: "Try one of these next:",
    suggestions
  };
}


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


function applyColorSuggestion(question, color) {
  let next = question;

  if (/\b(red|white|sparkling|rose)\s+wines?\b/i.test(next)) {
    next = next.replace(/\b(red|white|sparkling|rose)\s+(wine|wines)\b/i, `${color} $2`);
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

      appState.currentQuestion = nextQuestion;
      appState.currentPage = 1;

      await submitQuestion(nextQuestion, 1);
    });

    followupChips.appendChild(button);
  });

  followupSection.classList.remove("hidden");
}


function renderPagination(data) {
  const totalPages = Number(data?.total_pages || 0);
  const page = Number(data?.page || 1);

  if (!data?.show_results || totalPages <= 1) {
    paginationSection.classList.add("hidden");
    return;
  }

  pageIndicator.textContent = `Page ${page} of ${totalPages}`;
  prevPageButton.disabled = !data?.has_prev_page || appState.isLoading;
  nextPageButton.disabled = !data?.has_next_page || appState.isLoading;

  paginationSection.classList.remove("hidden");
}


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

  renderPagination(data);
}


async function submitQuestion(question, page = 1, options = {}) {
  const normalizedQuestion = normalizeQuestionText(question);
  const shouldAutoSpeak = options.autoSpeak !== false;

  resetResponseUI();
  setStatus("Searching the collection...", "loading");
  askButton.disabled = true;
  appState.isLoading = true;

  try {
    const response = await fetch(QUERY_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        question: normalizedQuestion,
        page,
        page_size: appState.currentPageSize
      })
    });

    const data = await response.json();

    if (!response.ok) {
      const detail = data?.detail || "The backend returned an error.";
      throw new Error(detail);
    }

    appState.currentQuestion = normalizedQuestion;
    appState.currentPage = Number(data?.page || page);
    appState.isLoading = false;
    askButton.disabled = false;

    renderResponse(data);

    window.wineAssistantUI.lastResponse = data;

    window.dispatchEvent(
      new CustomEvent("wine-response-ready", {
        detail: {
          response: data,
          autoSpeak: shouldAutoSpeak
        }
      })
    );

    clearStatus();
  } catch (error) {
    setStatus(`Request failed: ${error.message}`, "error");
  } finally {
    askButton.disabled = false;
    appState.isLoading = false;
  }
}


async function submitCurrentPage(page) {
  if (!appState.currentQuestion) {
    return;
  }

  await submitQuestion(appState.currentQuestion, page, { autoSpeak: false });
}


form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = questionInput.value.trim();
  if (!question) {
    setStatus("Enter a question before submitting.", "error");
    return;
  }

  appState.currentQuestion = question;
  appState.currentPage = 1;

  await submitQuestion(question, 1);
});


exampleChips.forEach((chip) => {
  chip.addEventListener("click", async () => {
    const question = chip.dataset.question || "";
    questionInput.value = question;

    appState.currentQuestion = question;
    appState.currentPage = 1;

    await submitQuestion(question, 1);
  });
});


prevPageButton.addEventListener("click", async () => {
  const previousPage = Math.max(appState.currentPage - 1, 1);
  await submitCurrentPage(previousPage);
});

nextPageButton.addEventListener("click", async () => {
  const nextPage = appState.currentPage + 1;
  await submitCurrentPage(nextPage);
});


window.wineAssistantUI = {
  submitQuestion,
  setStatus,
  clearStatus,
  questionInput,
  lastResponse: null
};
