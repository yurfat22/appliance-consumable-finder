const form = document.getElementById("search-form");
const modelInput = document.getElementById("model");
const results = document.getElementById("results");

const apiBase = window.API_BASE_URL || "http://localhost:8000";

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
