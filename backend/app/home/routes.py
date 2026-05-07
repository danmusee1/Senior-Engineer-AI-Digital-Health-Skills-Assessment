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
        <head>
            <title>Last Mile Health - Senior Full-Stack Engineer, AI & Digital Health Practice Assessment</title>
        </head>
        <body>
            <h1>Welcome to the Last Mile Health Senior Full-Stack Engineer, AI & Digital Health Practice Assessment!</h1>
            <p>This is your starting point for the RAG application assessment. Please follow the instructions below:</p>
            <ol>
                <li><b>Chat Interface Page:</b> Build a user-friendly chat UI for interacting with your RAG system.</li>
                <li><b>PDF Upload Page:</b> Implement a page to upload PDF documents for ingestion.</li>
                <li><b>Local Run Instructions:</b> Ensure your README includes clear steps to run the app locally.</li>
                <li><b>Production Deployment Plan:</b> Add a brief outline for deploying to production (cloud, CI/CD, etc.).</li>
            </ol>
            <p><b>Bonus:</b> Add automated tests and document architectural decisions.</p>
            
        </body>
    </html>
    """