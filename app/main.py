import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, verify_password
from app.config import settings
from app.db import get_db, init_schema
from app.models import User
from app.routers import api
from app import services


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="anna_akulova — библиотека", version="1.0.0")
app.include_router(api.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


from app.timing import disable_timing, reset_timing, snapshot


@app.middleware("http")
async def measure_timing_middleware(request: Request, call_next):
    """Заголовок X-Measure: 1 включает разложение времени для скрипта замеров ДЗ1."""
    if request.headers.get("X-Measure") != "1":
        return await call_next(request)

    reset_timing()
    started = time.perf_counter()
    response = await call_next(request)
    total_ms = (time.perf_counter() - started) * 1000
    db_ms, db_n = snapshot()
    disable_timing()
    response.headers["X-Total-Ms"] = f"{total_ms:.3f}"
    response.headers["X-Db-Ms"] = f"{db_ms:.3f}"
    response.headers["X-Db-Queries"] = str(db_n)
    response.headers["X-App-Ms"] = f"{max(total_ms - db_ms, 0.0):.3f}"
    return response


@app.on_event("startup")
def on_startup() -> None:
    if os.getenv("SKIP_DB_INIT") == "1":
        return
    init_schema()


def _token_from_request(request: Request) -> str | None:
    return request.cookies.get("access_token")


def require_web_user(request: Request, db: Session) -> User | RedirectResponse:
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    token = _token_from_request(request)
    if not token:
        return RedirectResponse("/login", status_code=303)
    try:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        return get_current_user(credentials=credentials, db=db)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    user = require_web_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    page = int(request.query_params.get("page", "1"))
    size = int(request.query_params.get("size", "20"))
    status = request.query_params.get("status") or None
    q = request.query_params.get("q") or None

    items, total = services.list_loans(db, page=page, size=size, status_filter=status, q=q)
    pages = max(1, (total + size - 1) // size)
    return templates.TemplateResponse(
        request,
        "loans.html",
        {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
            "status": status or "",
            "q": q or "",
            "project": "anna_akulova",
        },
    )


@app.get("/loans/{loan_id}", response_class=HTMLResponse)
def loan_card(loan_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_web_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    loan = services.get_loan(db, loan_id)
    return templates.TemplateResponse(
        request,
        "loan_detail.html",
        {"loan": loan, "project": "anna_akulova"},
    )


@app.get("/summary", response_class=HTMLResponse)
def summary_page(request: Request, db: Session = Depends(get_db)):
    user = require_web_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    data = services.build_summary(db)
    return templates.TemplateResponse(
        request,
        "summary.html",
        {"summary": data, "project": "anna_akulova"},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "project": "anna_akulova"},
    )


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный логин или пароль", "project": "anna_akulova"},
            status_code=401,
        )
    token = create_token(user.id)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=False)
