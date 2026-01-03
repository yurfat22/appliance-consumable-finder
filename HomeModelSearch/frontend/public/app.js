const form = document.getElementById("search-form");
const modelInput = document.getElementById("model");
const results = document.getElementById("results");
const browse = document.getElementById("browse");

const apiBase = window.API_BASE_URL || "http://localhost:8000";

const renderStatus = (message, isError = false) => {
  const status = document.createElement("div");
  status.className = `status${isError ? " error" : ""}`;
  status.textContent = message;
  results.replaceChildren(status);
};

const renderResults = (appliances) => {
  results.replaceChildren();

  appliances.forEach((appliance) => {
    const card = document.createElement("article");
    card.className = "card";

    const heading = document.createElement("h3");
    heading.textContent = `${appliance.brand} ${appliance.model}`;
    card.appendChild(heading);

    const consumableList = document.createElement("div");
    appliance.consumables.forEach((item) => {
      const entry = document.createElement("div");
      entry.className = "consumable";

      const meta = document.createElement("div");
      meta.className = "meta";
      meta.innerHTML = `<span class="tag">${item.type}</span><span>${item.name} (SKU: ${item.sku})</span>`;
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

const renderBrowseStatus = (message, isError = false) => {
  const status = document.createElement("div");
  status.className = `status${isError ? " error" : ""}`;
  status.textContent = message;
  browse.replaceChildren(status);
};

const renderBrowse = (groups) => {
  browse.replaceChildren();

  groups.forEach((group) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const baseBrands =
      Array.isArray(group.brands) && group.brands.length
        ? group.brands
        : Array.isArray(group.appliances)
          ? Object.values(
              group.appliances.reduce((map, appliance) => {
                const brand = appliance.brand || "Unknown";
                if (!map[brand]) {
                  map[brand] = { brand, appliances: [] };
                }
                map[brand].appliances.push(appliance);
                return map;
              }, {})
            )
          : [];

    const allAppliances = baseBrands.flatMap((b) => b.appliances || []);
    const brands = [{ brand: "All", appliances: allAppliances }, ...baseBrands];
    const total = allAppliances.length || brands.reduce((acc, b) => acc + (b.appliances?.length || 0), 0);
    summary.textContent = `${group.category} (${total || 0})`;
    details.appendChild(summary);

    brands.forEach((brandGroup) => {
      const brandDetails = document.createElement("details");
      brandDetails.className = "browse-brand";
      const brandSummary = document.createElement("summary");
      brandSummary.textContent = `${brandGroup.brand} (${brandGroup.appliances?.length || 0})`;
      brandDetails.appendChild(brandSummary);

      (brandGroup.appliances || []).forEach((appliance) => {
        const wrapper = document.createElement("div");
        wrapper.className = "browse-model";

        const title = document.createElement("h4");
        title.textContent = `${appliance.brand} ${appliance.model}`;
        wrapper.appendChild(title);

        const consumableList = document.createElement("div");
        appliance.consumables.forEach((item) => {
          const entry = document.createElement("div");
          entry.className = "consumable";
          const meta = document.createElement("div");
          meta.className = "meta";
          meta.innerHTML = `<span class="tag">${item.type}</span><span>${item.name} (SKU: ${item.sku})</span>`;
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

        wrapper.appendChild(consumableList);
        brandDetails.appendChild(wrapper);
      });

      details.appendChild(brandDetails);
    });

    browse.appendChild(details);
  });
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const model = modelInput.value.trim();
  if (!model) return;

  renderStatus("Searching…");

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

const loadBrowse = async () => {
  renderBrowseStatus("Loading categories…");
  try {
    const res = await fetch(`${apiBase}/api/categories`);
    if (!res.ok) {
      renderBrowseStatus("Could not load categories.", true);
      return;
    }
    const data = await res.json();
    renderBrowse(data);
  } catch (err) {
    console.error(err);
    renderBrowseStatus("Could not reach the server. Is the backend running?", true);
  }
};

loadBrowse();
