import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

class Consumable(BaseModel):
    name: str
    type: str
    sku: str
    notes: Optional[str] = None
    purchase_url: Optional[str] = None


class Appliance(BaseModel):
    model: str
    brand: str
    category: str
    consumables: List[Consumable]


class BrandGroup(BaseModel):
    brand: str
    appliances: List[Appliance]


class Contractor(BaseModel):
    name: str
    company: str
    phone: str
    email: EmailStr
    service_area: Optional[str] = None
    license: Optional[str] = None
    photo: Optional[str] = None
    bio: Optional[str] = None


DATA_PATH = Path(__file__).parent / "data" / "appliances.json"
CONTRACTOR_PATH = Path(__file__).parent / "data" / "contractor.json"
IMAGE_DIR = Path(__file__).parent / "image"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public"

app = FastAPI(title="Appliance Consumables API")

# Allow the Node UI (default localhost:3000) to talk to the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets (e.g., contractor photos) from /assets/*
app.mount("/assets", StaticFiles(directory=IMAGE_DIR), name="assets")


def load_data() -> List[Appliance]:
    if not DATA_PATH.exists():
        raise RuntimeError(f"Data file not found: {DATA_PATH}")

    with DATA_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return [Appliance(**item) for item in raw]


def load_contractor() -> Contractor:
    if not CONTRACTOR_PATH.exists():
        raise RuntimeError(f"Contractor file not found: {CONTRACTOR_PATH}")

    with CONTRACTOR_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    return Contractor(**raw)


APPLIANCES: List[Appliance] = load_data()
CONTRACTOR: Contractor = load_contractor()


class CategoryGroup(BaseModel):
    category: str
    brands: List[BrandGroup]


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    zip_code: Optional[str] = None
    appliance_category: Optional[str] = None
    model: Optional[str] = None
    preferred_time: Optional[str] = None
    notes: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/consumables", response_model=List[Appliance])
def search(model: str = Query(..., description="Appliance model number")) -> List[Appliance]:
    model_query = model.strip().lower()
    if not model_query:
        raise HTTPException(status_code=400, detail="Model query cannot be empty.")

    matches = [
        appliance
        for appliance in APPLIANCES
        if model_query in appliance.model.lower()
    ]

    if not matches:
        raise HTTPException(status_code=404, detail="No consumables found for that model.")

    return matches


@app.get("/api/categories", response_model=List[CategoryGroup])
def list_categories() -> List[CategoryGroup]:
    categories: dict[str, dict[str, List[Appliance]]] = {}
    for appliance in APPLIANCES:
        cat = categories.setdefault(appliance.category, {})
        cat.setdefault(appliance.brand, []).append(appliance)

    grouped: List[CategoryGroup] = []
    for category, brand_map in sorted(categories.items()):
        brands = [
            BrandGroup(brand=brand, appliances=items)
            for brand, items in sorted(brand_map.items())
        ]
        grouped.append(CategoryGroup(category=category, brands=brands))

    return grouped


@app.get("/api/contractor", response_model=Contractor)
def get_contractor() -> Contractor:
    # Reload on each request so updates to contractor.json show without a server restart.
    return load_contractor()


@app.post("/api/contact")
def submit_contact(request: ContactRequest) -> dict:
    # In a real app this would enqueue to a CRM/email/SMS. For now we log it.
    print("Contact request received:", request.model_dump())
    return {"status": "received", "message": "A local pro will reach out soon."}


@app.get("/config.js")
def config(request: Request) -> Response:
    base_url = str(request.base_url).rstrip("/")
    return Response(
        f'window.API_BASE_URL = "{base_url}";',
        media_type="application/javascript",
    )


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
