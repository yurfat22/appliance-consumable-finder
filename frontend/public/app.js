const form = document.getElementById("search-form");
const modelInput = document.getElementById("model");
const results = document.getElementById("results");
const suggestionsList = document.getElementById("suggestions-list");

const apiBase = window.API_BASE_URL || "http://localhost:8000";

// ==================== AUTOCOMPLETE ====================

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

class Autocomplete {
  constructor(inputEl, listEl, onSelect) {
    this.input = inputEl;
    this.list = listEl;
    this.onSelect = onSelect;
    this.highlightedIndex = -1;
    this.suggestions = [];
    this.debounceTimer = null;
    this.abortController = null;

    this.bindEvents();
  }

  bindEvents() {
    this.input.addEventListener("input", () => this.handleInput());
    this.input.addEventListener("keydown", (e) => this.handleKeydown(e));
    this.input.addEventListener("blur", () => this.handleBlur());
    this.input.addEventListener("focus", () => this.handleFocus());

    document.addEventListener("click", (e) => {
      if (!this.input.contains(e.target) && !this.list.contains(e.target)) {
        this.hide();
      }
    });
  }

  handleInput() {
    const query = this.input.value.trim();

    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    if (this.abortController) this.abortController.abort();

    if (query.length < MIN_QUERY_LENGTH) {
      this.hide();
      return;
    }

    this.showLoading();
    this.debounceTimer = setTimeout(() => this.fetchSuggestions(query), DEBOUNCE_MS);
  }

  async fetchSuggestions(query) {
    this.abortController = new AbortController();

    try {
      const res = await fetch(
        `${apiBase}/api/suggestions?q=${encodeURIComponent(query)}&limit=10`,
        { signal: this.abortController.signal }
      );

      if (!res.ok) {
        this.hide();
        return;
      }

      const data = await res.json();
      this.suggestions = data || [];
      this.renderSuggestions(query);
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Autocomplete error:", err);
        this.hide();
      }
    }
  }

  renderSuggestions(query) {
    this.list.innerHTML = "";
    this.highlightedIndex = -1;

    if (this.suggestions.length === 0) {
      const noResults = document.createElement("li");
      noResults.className = "no-results";
      noResults.textContent = "No matching models found";
      noResults.setAttribute("aria-disabled", "true");
      this.list.appendChild(noResults);
      this.show();
      return;
    }

    this.suggestions.forEach((suggestion, index) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", "false");
      li.dataset.index = index;

      const modelHtml = this.highlightMatch(suggestion.model_number, query);

      li.innerHTML = `
        <div class="suggestion-model">${modelHtml}</div>
        <div class="suggestion-context">${suggestion.brand} - ${suggestion.category}</div>
      `;

      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        this.selectSuggestion(index);
      });

      li.addEventListener("mouseenter", () => {
        this.setHighlight(index);
      });

      this.list.appendChild(li);
    });

    this.show();
  }

  highlightMatch(text, query) {
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const index = lowerText.indexOf(lowerQuery);

    if (index === -1) return this.escapeHtml(text);

    const before = text.slice(0, index);
    const match = text.slice(index, index + query.length);
    const after = text.slice(index + query.length);

    return `${this.escapeHtml(before)}<span class="suggestion-match">${this.escapeHtml(match)}</span>${this.escapeHtml(after)}`;
  }

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  handleKeydown(e) {
    if (!this.isVisible()) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        this.moveHighlight(1);
        break;
      case "ArrowUp":
        e.preventDefault();
        this.moveHighlight(-1);
        break;
      case "Enter":
        if (this.highlightedIndex >= 0) {
          e.preventDefault();
          this.selectSuggestion(this.highlightedIndex);
        }
        break;
      case "Escape":
        this.hide();
        break;
      case "Tab":
        this.hide();
        break;
    }
  }

  moveHighlight(delta) {
    const items = this.list.querySelectorAll('li[role="option"]');
    if (items.length === 0) return;

    let newIndex = this.highlightedIndex + delta;
    if (newIndex < 0) newIndex = items.length - 1;
    if (newIndex >= items.length) newIndex = 0;

    this.setHighlight(newIndex);
  }

  setHighlight(index) {
    const items = this.list.querySelectorAll('li[role="option"]');

    items.forEach((item, i) => {
      item.classList.toggle("highlighted", i === index);
      item.setAttribute("aria-selected", i === index ? "true" : "false");
    });

    this.highlightedIndex = index;

    if (items[index]) {
      items[index].scrollIntoView({ block: "nearest" });
    }
  }

  selectSuggestion(index) {
    const suggestion = this.suggestions[index];
    if (!suggestion) return;

    this.input.value = suggestion.model_number;
    this.hide();

    if (this.onSelect) {
      this.onSelect(suggestion);
    }
  }

  handleBlur() {
    setTimeout(() => this.hide(), 150);
  }

  handleFocus() {
    if (this.input.value.trim().length >= MIN_QUERY_LENGTH && this.suggestions.length > 0) {
      this.show();
    }
  }

  showLoading() {
    this.list.innerHTML = "";
    this.list.classList.add("loading", "visible");
    this.input.setAttribute("aria-expanded", "true");
  }

  show() {
    this.list.classList.remove("loading");
    this.list.classList.add("visible");
    this.input.setAttribute("aria-expanded", "true");
  }

  hide() {
    this.list.classList.remove("visible", "loading");
    this.input.setAttribute("aria-expanded", "false");
    this.highlightedIndex = -1;
  }

  isVisible() {
    return this.list.classList.contains("visible");
  }
}

// Initialize autocomplete if elements exist
if (suggestionsList) {
  new Autocomplete(modelInput, suggestionsList, (suggestion) => {
    // Optionally auto-submit when a suggestion is selected
    // form.requestSubmit();
  });
}

// ==================== SEARCH RESULTS ====================

const renderStatus = (message, isError = false) => {
  const status = document.createElement("div");
  status.className = `status${isError ? " error" : ""}`;
  status.textContent = message;
  results.replaceChildren(status);
};

const renderResults = (appliances) => {
  results.replaceChildren();

  appliances.forEach((appliance, index) => {
    const card = document.createElement("article");
    card.className = "card";
    card.style.animationDelay = `${Math.min(index, 8) * 60}ms`;

    const heading = document.createElement("h3");
    heading.textContent = `${appliance.brand} ${appliance.model}`;
    card.appendChild(heading);

    const consumableList = document.createElement("div");
    appliance.consumables.forEach((item) => {
      const entry = document.createElement("div");
      entry.className = "consumable";

      const meta = document.createElement("div");
      meta.className = "meta";
      const skuLabel = item.sku ? `SKU: ${item.sku}` : "SKU: N/A";
      const asinLabel = item.asin ? `ASIN: ${item.asin}` : "";
      const idLabel = asinLabel ? `${skuLabel} · ${asinLabel}` : skuLabel;
      meta.innerHTML = `<span class="tag">${item.type}</span><span>${item.name} (${idLabel})</span>`;
      entry.appendChild(meta);

      if (item.notes) {
        const notes = document.createElement("div");
        notes.className = "notes";
        notes.textContent = item.notes;
        entry.appendChild(notes);
      }

      if (item.purchase_url) {
        const link = document.createElement("a");
        link.className = "buy-link";
        link.href = item.purchase_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "View on Amazon";
        meta.appendChild(link);
      }

      consumableList.appendChild(entry);
    });

    card.appendChild(consumableList);
    results.appendChild(card);
  });
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const model = modelInput.value.trim();
  if (!model) return;

  renderStatus("Searching...");

  try {
    const res = await fetch(`${apiBase}/api/consumables?model=${encodeURIComponent(model)}`);

    if (!res.ok) {
      const error = await res.json().catch(() => null);
      const message = error?.detail || "Search failed. Try again.";
      renderStatus(message, true);
      return;
    }

    const data = await res.json();
    renderResults(data);
  } catch (err) {
    console.error(err);
    renderStatus("Could not reach the server. Is the backend running?", true);
  }
});
