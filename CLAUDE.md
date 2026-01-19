# Appliance Consumable Finder

An affiliate-driven website that helps users find compatible consumables (filters, parts) for their appliances by searching model numbers.

## Tech Stack

- **Frontend:** Express.js serving vanilla HTML/CSS/JavaScript
- **Backend:** Python FastAPI with Uvicorn
- **Database:** PostgreSQL via Supabase
- **Deployment:** Docker Compose, hosted on Render

## Project Structure

```
appliance-consumable-finder/
├── frontend/                     # Node/Express UI server
│   ├── server.js                 # Express server (serves static files, injects API_BASE_URL)
│   ├── package.json              # Node dependencies
│   ├── Dockerfile                # Node 20 Alpine container
│   └── public/                   # Static assets
│       ├── index.html            # Search page (main entry)
│       ├── browse.html           # Browse by category page
│       ├── contact.html          # Contact form + contractor profile
│       ├── blog.html             # Blog/tips page
│       ├── technical.html        # Technical info page
│       ├── app.js                # Search + autocomplete functionality
│       ├── browse.js             # Category browsing logic
│       ├── contact.js            # Contact form handling
│       ├── styles.css            # All styling (CSS variables, responsive)
│       └── images/               # Logo and branding assets
│
├── backend/                      # Python FastAPI server
│   ├── app.py                    # Main API (endpoints, DB queries, affiliate links)
│   ├── requirements.txt          # Python dependencies
│   ├── Dockerfile                # Python 3.11 slim container
│   ├── .env                      # Environment config (DATABASE_URL, AMAZON_ASSOCIATE_TAG)
│   ├── .env.example              # Example environment template
│   ├── db/
│   │   └── schema.sql            # PostgreSQL schema (tables, indexes, pg_trgm)
│   ├── image/                    # Static assets (contractor photos)
│   └── tools/                    # Data management scripts
│       ├── load_supabase.py      # Main data loader (appliances, consumables, contractors)
│       ├── amazon_water_filters.py  # Amazon PA-API scraper for water filters
│       ├── scrape_ge_models.py   # GE model scraper
│       └── import_appliances.py  # CSV to JSON converter
│
├── docker-compose.yml            # Local/prod orchestration
├── README.md                     # Project documentation
└── CLAUDE.md                     # This file (AI context)
```

## Database Schema

```sql
-- Core tables
brands (id, name)
categories (id, name)
models (id, brand_id, category_id, model_number, water_filter_missing)
consumables (id, name, type, asin, sku, purchase_url)
model_consumables (model_id, consumable_id, notes)  -- join table
contractors (id, name, company, phone, email, service_area, license, photo, bio, updated_at)

-- Indexes
idx_models_model_number_lower ON models (LOWER(model_number))
idx_models_model_number_trgm ON models USING GIN (LOWER(model_number) gin_trgm_ops)  -- fuzzy search
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/consumables?model=X` | GET | Search consumables by model number |
| `/api/suggestions?q=X&limit=10` | GET | Autocomplete suggestions with fuzzy matching |
| `/api/categories` | GET | All models grouped by category/brand |
| `/api/contractor` | GET | Latest contractor profile |
| `/api/contact` | POST | Submit contact form (logs to console) |
| `/config.js` | GET | Injects `window.API_BASE_URL` |

## Key Features

1. **Model Search:** Case-insensitive substring matching on model numbers
2. **Autocomplete:** Real-time suggestions with fuzzy matching (pg_trgm)
3. **Affiliate Links:** Amazon Associate links auto-generated from ASIN/SKU
4. **Browse by Category:** Hierarchical navigation (category → brand → model)
5. **Contact Form:** Collects leads (currently logs, no CRM integration)

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:port/postgres?sslmode=require

# Optional
AMAZON_ASSOCIATE_TAG=be3857-20    # Default affiliate tag
PGSSLMODE=require                  # SSL mode for DB
PORT=3000                          # Frontend port
API_BASE_URL=http://backend:8000   # For Docker Compose
```

## Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python app.py  # Runs on http://localhost:8000

# Frontend
cd frontend
npm install
npm start  # Runs on http://localhost:3000

# Or with Docker
docker-compose up
```

## Data Loading

```bash
cd backend/tools
python load_supabase.py --input appliances.json --contractor contractor.json
```

## Recent Changes

- Added autocomplete with fuzzy matching (pg_trgm extension)
- Added `/api/suggestions` endpoint
- Frontend autocomplete with debouncing and keyboard navigation
