from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
import os

# Load environment variables from .env
load_dotenv()

from modules.phone_scanner import scan_phone
from modules.email_scanner import scan_email

app = FastAPI(
    title="OSINT Dashboard",
    description="Personal Digital Footprint & OSINT Dashboard",
    version="1.0.0",
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist before mounting
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Request Models ─────────────────────────────────────────────────────────────

class PhoneScanRequest(BaseModel):
    phone: str


class EmailScanRequest(BaseModel):
    email: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the dashboard UI."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/scan-phone")
async def api_scan_phone(req: PhoneScanRequest):
    """Scan a phone number for OSINT data."""
    try:
        result = await scan_phone(req.phone)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Internal server error: {str(e)}"},
        )


@app.post("/api/scan-email")
async def api_scan_email(req: EmailScanRequest):
    """Scan an email address for OSINT data."""
    try:
        result = await scan_email(req.email)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Internal server error: {str(e)}"},
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
