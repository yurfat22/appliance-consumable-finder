const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8000";

app.use(express.static(path.join(__dirname, "public")));

app.get("/config.js", (_req, res) => {
  res.type("application/javascript").send(`window.API_BASE_URL = "${API_BASE_URL}";`);
});

app.listen(PORT, () => {
  console.log(`UI running on http://localhost:${PORT}`);
  console.log(`Using API base: ${API_BASE_URL}`);
});
