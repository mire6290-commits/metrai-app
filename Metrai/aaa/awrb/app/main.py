import os
from fastapi import FastAPI, Request, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import Base, engine
from app.routes import auth, math, ocr, dashboard, admin, views

# Initialize Database Schema on startup automatically
# This handles initial setups and avoids migration bottlenecks for SQLite/Postgre
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Metrai Calculus - Self-Hosted Mathematics & AI Engine Platform",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

# Enable CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
    os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include Modular API Routers
app.include_router(auth.router)
app.include_router(math.router)
app.include_router(ocr.router)
app.include_router(dashboard.router)
app.include_router(admin.router)

# Include HTML Pages Views Router
app.include_router(views.router)

# Locate templates for custom exception handles
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# --- GLOBAL ERROR HANDLERS ---
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    """Graceful HTML 404 page handler."""
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "status_code": 404, "detail": "The page you are looking for does not exist in Metrai Calculus."},
        status_code=404
    )

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc):
    """Graceful HTML 500 error page handler."""
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "status_code": 500, "detail": "An internal error occurred in our mathematical engine. Please try again."},
        status_code=500
    )

# --- SEO META SERVICE ENDPOINTS ---
@app.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt():
    """Generates standard crawling crawler rules for search index optimization."""
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /dashboard\n"
        f"Sitemap: https://metraicalculus.com/sitemap.xml\n"
    )
    return content

@app.get("/sitemap.xml")
def get_sitemap_xml():
    """Generates standard dynamic XML sitemap links for SEO indices."""
    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        '    <loc>https://metraicalculus.com/</loc>\n'
        '    <lastmod>2026-05-18</lastmod>\n'
        '    <changefreq>daily</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
        '  <url>\n'
        '    <loc>https://metraicalculus.com/calculator</loc>\n'
        '    <lastmod>2026-05-18</lastmod>\n'
        '    <changefreq>weekly</changefreq>\n'
        '    <priority>0.8</priority>\n'
        '  </url>\n'
        '  <url>\n'
        '    <loc>https://metraicalculus.com/ocr</loc>\n'
        '    <lastmod>2026-05-18</lastmod>\n'
        '    <changefreq>weekly</changefreq>\n'
        '    <priority>0.8</priority>\n'
        '  </url>\n'
        '</urlset>'
    )
    return Response(content=xml_content, media_type="application/xml")
