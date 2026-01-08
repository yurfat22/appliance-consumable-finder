const formEl = document.getElementById("contact-form");
const statusEl = document.getElementById("contact-status");
const apiBase = window.API_BASE_URL || "http://localhost:8000";
const proEls = {
  name: document.getElementById("pro-name"),
  company: document.getElementById("pro-company"),
  bio: document.getElementById("pro-bio"),
  phone: document.getElementById("pro-phone"),
  email: document.getElementById("pro-email"),
  area: document.getElementById("pro-area"),
  license: document.getElementById("pro-license"),
  photo: document.getElementById("pro-photo"),
};

const setStatus = (message, isError = false) => {
  statusEl.textContent = message;
  statusEl.className = `status${isError ? " error" : ""}`;
};

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = {
    name: formEl.name.value.trim(),
    email: formEl.email.value.trim(),
    phone: formEl.phone.value.trim() || undefined,
    zip_code: formEl.zip.value.trim() || undefined,
    appliance_category: formEl.category.value || undefined,
    model: formEl.model.value.trim() || undefined,
    preferred_time: formEl.preferred.value.trim() || undefined,
    notes: formEl.notes.value.trim() || undefined,
  };

  if (!data.name || !data.email || !data.appliance_category) {
    setStatus("Please fill in required fields.", true);
    return;
  }

  setStatus("Sending request...");

  try {
    const res = await fetch(`${apiBase}/api/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => null);
      setStatus(error?.detail || "Could not send request.", true);
      return;
    }

    setStatus("Request sent. A local pro will reach out soon.");
    formEl.reset();
  } catch (err) {
    console.error(err);
    setStatus("Could not reach the server. Is the backend running?", true);
  }
});

const loadPro = async () => {
  try {
    const res = await fetch(`${apiBase}/api/contractor`, { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    proEls.name.textContent = data.name;
    proEls.company.textContent = data.company;
    proEls.bio.textContent = data.bio || "";
    proEls.phone.textContent = data.phone;
    proEls.email.textContent = data.email;
    proEls.area.textContent = data.service_area || "Local";
    proEls.license.textContent = data.license || "Available on request";
    if (data.photo) {
      const src = data.photo.startsWith("http")
        ? data.photo
        : `${apiBase}${data.photo.startsWith("/") ? "" : "/"}${data.photo}`;
      proEls.photo.src = src;
    }
  } catch (err) {
    console.error("Failed to load contractor info", err);
  }
};

loadPro();
