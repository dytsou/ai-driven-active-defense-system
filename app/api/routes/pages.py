from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request})


@router.get("/mfa", response_class=HTMLResponse)
def mfa_page(request: Request):
    return templates.TemplateResponse(
        request,
        "mfa.html",
        {"request": request, "challenge_id": request.query_params.get("challenge_id", "")},
    )


@router.get("/admin/events", response_class=HTMLResponse)
def admin_events_page(request: Request):
    return templates.TemplateResponse(request, "admin/events.html", {"request": request})
