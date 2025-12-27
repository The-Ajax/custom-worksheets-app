import contextlib
import os

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import Response

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from starlette import status
from datetime import timedelta
from fastapi.responses import JSONResponse

from generator import create_problem_sheet, convert_html_to_pdf
from database import create_all_tables, get_async_session
import schemas
from models import ProblemSheet
from database import get_async_session
from auth import (
    create_access_token, get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
import crud


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield


app = FastAPI(lifespan=lifespan)

# app = FastAPI(
#     lifespan=lifespan,
#     docs_url=None,
#     redoc_url=None,
#     openapi_url=None,
#     title="My Secure API"
# )

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")



@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    if not request.cookies.get("access_token"):
        return templates.TemplateResponse("login.html", {"request": request})

    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate", response_class=RedirectResponse, status_code=status.HTTP_201_CREATED)
async def generate_pdf(
    request: Request,
    subject: str = Form(...),
    difficulty: str = Form(...),
    num_problems: int = Form(...),
    add_info: str = Form(""),
    user: schemas.UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):

    problem_sheet_data = schemas.ProblemSheetCreate(
        subject=subject,
        difficulty=difficulty,
        num_problems=num_problems,
        additional_info=add_info,
        file_path=None,
        user_id=user.id # Make sure this connects to the db properly
    )

    create_problem_sheet(subject, difficulty, num_problems, add_info)

    new_problem_sheet = ProblemSheet(**problem_sheet_data.model_dump())
    session.add(new_problem_sheet)
    await session.commit()
    await session.refresh(new_problem_sheet)

    pdf_filename = f"problem_sheet_{new_problem_sheet.id}.pdf"

    pdf_path = convert_html_to_pdf("worksheet_templates/res.html", pdf_filename)

    if not pdf_path:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF")
    
    new_problem_sheet.file_path = pdf_path
    await session.commit()
    await session.refresh(new_problem_sheet)
    
    redirect_url = f"/problem_sheets/{new_problem_sheet.id}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/problem_sheets/{sheet_id}", response_class=HTMLResponse)
async def get_problem_sheet(
    sheet_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session)
):
    result = await session.execute(
        select(ProblemSheet).where(ProblemSheet.id == sheet_id)
    )
    sheet = result.scalars().first()

    if not sheet:
        return templates.TemplateResponse(
            "not_found.html",
            {"request": request, "sheet_id": sheet_id},
            status_code=404
        )

    sheet_data = {
        "id": sheet.id,
        "subject": sheet.subject,
        "difficulty": sheet.difficulty,
        "num_problems": sheet.num_problems,
        "file_path": sheet.file_path,
        "created_at": sheet.created_at,
        "username": sheet.user.username, # Get Username Later
    }

    return templates.TemplateResponse(
        "problem_sheet_detail.html",
        {"request": request, "sheet": sheet_data}
    )


@app.get("/problem_sheets/{sheet_id}/download", response_class=FileResponse)
async def download_problem_sheet(sheet_id: int, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(ProblemSheet).where(ProblemSheet.id == sheet_id))
    problem_sheet = result.scalars().first()
    
    if not problem_sheet or not problem_sheet.file_path or not os.path.exists(problem_sheet.file_path):
        return {"error": "File not found"}

    return FileResponse(
        path=problem_sheet.file_path,
        filename=os.path.basename(problem_sheet.file_path),
        media_type='application/pdf'
    )

@app.get("/problem_sheets", response_class=HTMLResponse)
async def list_problem_sheets(
    request: Request, 
    session: AsyncSession = Depends(get_async_session),
    user: schemas.UserInDB = Depends(get_current_active_user)
):

    result = await session.execute(
        select(ProblemSheet).where(ProblemSheet.user_id == user.id)
    )
    problem_sheets = result.scalars().all()
    return templates.TemplateResponse("problem_sheet_list.html", {"request": request, "sheets": problem_sheets})


@app.delete("/problem_sheets", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_problem_sheets(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(ProblemSheet.file_path))
    file_paths = [row[0] for row in result.fetchall() if row[0]]
    
    await session.execute(delete(ProblemSheet))
    await session.commit()

    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error deleting file {path}")

    return {"message": "All problem sheets deleted"}


@app.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, session: AsyncSession = Depends(get_async_session)):
    db_user = await crud.get_user_by_username(session, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    new_user = await crud.create_user(session, user)

    return new_user


@app.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: AsyncSession = Depends(get_async_session)
):
    user = await crud.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    response = JSONResponse(content={"message": "Login successful", "access_token": access_token})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=False, # Making it true prevents JavaScript access (make it false for now)
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=False,
        samesite="lax",
        path="/"  # Make cookie available for all paths
    )
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/logout")
async def logout(response: Response):
    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    return response

@app.get("/signup", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})