# Appliance Consumable Finder

Find appliance consumables (filters, bulbs, etc.) by model number and browse by category/brand. Simple FastAPI backend with a Node/Express front end.

## Project structure
- `backend/` - FastAPI API
  - `app.py` - endpoints for health, consumable search, categories-by-brand, contractor info, contact submission, and static asset serving (`/assets/*` from `backend/image`).
  - `data/appliances.json` - appliance/consumable seed data (with Amazon links).
  - `data/contractor.json` - contractor profile (name/company/phone/email/etc., `photo` should point to `/assets/contractor.jpg`).
  - `image/` - static assets for the backend (e.g., `contractor.jpg`).
  - `requirements.txt` - Python dependencies.
  - `tools/import_appliances.py` - CSV -> JSON ingest tool.
- `frontend/` - Node/Express UI
  - `public/` - static HTML/CSS/JS
  - `server.js` - serves static assets and `/config.js` (injects `API_BASE_URL`).
- `docker-compose.yml` - local/prod container orchestration.

## Setup
### Backend
```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```powershell
cd frontend
npm install
# optional: set API base if not localhost:8000
# $env:API_BASE_URL="http://localhost:8000"
npm start
```
Open `http://localhost:3000`.

## Deployment (Docker Compose)
- Build and run both services:
```powershell
cd <repo-root>
docker compose up --build
```
- Frontend will be on `http://localhost:3000`, backend on `http://localhost:8000`.
- To point at a domain later, set `API_BASE_URL` on the frontend service (e.g., `API_BASE_URL=https://api.yourdomain.com`) and expose/route 3000/8000 via your reverse proxy or hosting platform. Add TLS via your host (e.g., managed certs or Let’s Encrypt) and map `A`/`CNAME` records accordingly.

## Usage
- Search by model: uses `/api/consumables'model=...` (case-insensitive substring match).
- Browse by category: `/api/categories` groups by appliance category and brand (with an "All" group).
- Contact a pro: form posts to `/api/contact`; data is currently logged server-side.
- Contractor info: `/api/contractor` reads `data/contractor.json` on each request; images served from `/assets/*`.

## Data notes
- Add/edit appliances in `backend/data/appliances.json` (fields: `model`, `brand`, `category`, `consumables` with `name`, `type`, `sku`, `notes`, `purchase_url`).
- Update contractor info in `backend/data/contractor.json`; place the photo at `backend/image/contractor.jpg` (or update the path).
- CSV ingest: put a CSV with headers `model,brand,category,consumable_name,consumable_type,sku,notes,purchase_url` at `backend/data/appliances.csv` and run:
  ```powershell
  cd backend
  python tools/import_appliances.py
  ```
  It will regenerate `backend/data/appliances.json`. Use `-i`/`-o` to override input/output paths.


## Supabase (Postgres) setup
The backend can use Supabase/Postgres when `DATABASE_URL` is set. It falls back to JSON when unset.

1) Create a Supabase project and open the SQL editor.
2) Run the schema in `backend/db/schema.sql`.
3) Load data from JSON into Supabase:
```powershell
cd <repo-root>
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require"
py backend/tools/load_supabase.py
```
4) Run the backend using Supabase:
```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/postgres?sslmode=require"
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

To reset and reload tables, use `py backend/tools/load_supabase.py --truncate`.

## Running tests
No automated tests included. To validate manually:
- Hit `/health`, `/api/consumables'model=...`, `/api/categories`, `/api/contractor`.
- Load `http://localhost:3000` to exercise search/browse/contact flows.

## Future ideas
- Fuzzy search and filters (brand/category).
- Import from CSV/DB and pagination.
- Persist contact requests to email/CRM instead of logging.
