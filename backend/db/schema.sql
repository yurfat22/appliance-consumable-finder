-- Enable trigram extension for fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS brands (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS categories (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS models (
  id BIGSERIAL PRIMARY KEY,
  brand_id BIGINT NOT NULL REFERENCES brands(id),
  category_id BIGINT NOT NULL REFERENCES categories(id),
  model_number TEXT NOT NULL,
  water_filter_missing BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (brand_id, category_id, model_number)
);

CREATE INDEX IF NOT EXISTS idx_models_model_number_lower
  ON models (LOWER(model_number));

-- GIN index for fast trigram similarity searches (fuzzy matching)
CREATE INDEX IF NOT EXISTS idx_models_model_number_trgm
  ON models USING GIN (LOWER(model_number) gin_trgm_ops);

CREATE TABLE IF NOT EXISTS consumables (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  asin TEXT UNIQUE,
  sku TEXT UNIQUE,
  purchase_url TEXT
);

CREATE TABLE IF NOT EXISTS model_consumables (
  model_id BIGINT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
  consumable_id BIGINT NOT NULL REFERENCES consumables(id) ON DELETE CASCADE,
  notes TEXT,
  PRIMARY KEY (model_id, consumable_id)
);

CREATE INDEX IF NOT EXISTS idx_model_consumables_model_id
  ON model_consumables (model_id);

CREATE TABLE IF NOT EXISTS contractors (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  company TEXT NOT NULL,
  phone TEXT NOT NULL,
  email TEXT NOT NULL,
  service_area TEXT,
  license TEXT,
  photo TEXT,
  bio TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
