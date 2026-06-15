#home/routes.py
"""
This module contains FastAPI routes for Home page
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home():
    """Home page route."""
    return """
    <html>
 
    </html>
    """