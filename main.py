# main.py
import os
import uuid
import shutil
import asyncio
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from utils import (
    extract_text_from_pdf,
    extract_text_from_docx,
    ensure_dirs,
    validate_file,
    save_pdf_text
)
from ai_agent import LLMAgent

# Load environment variables from .env file
load_dotenv()

UPLOAD_DIR = "uploads"
CORRECTED_DIR = "corrected_files"
ensure_dirs([UPLOAD_DIR, CORRECTED_DIR])

app = FastAPI(title="AI Document Compliance Checker (LLM Agent)")

agent = LLMAgent(model_name=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))


async def save_upload(file: UploadFile) -> str:
    """
    Save an uploaded file asynchronously to the upload directory.

    Args:
        file (UploadFile): The uploaded file received from FastAPI endpoint.

    Returns:
        str: The file system path of the saved file.

    Notes:
        - The function creates a unique filename by prepending a UUID to the original filename.
        - It saves the file in the directory specified by UPLOAD_DIR.
        - File saving is performed using a thread to avoid blocking the event loop.
    """
    filename = f"{uuid.uuid4().hex}_{file.filename}"  # Create unique filename
    path = os.path.join(UPLOAD_DIR, filename)         # Destination path
    with open(path, "wb") as buffer:
        # Use a thread to copy the uploaded file's data efficiently
        await asyncio.to_thread(shutil.copyfileobj, file.file, buffer)
    return path


@app.get("/")
async def root():
    return {"message": "Welcome to the AI Document Compliance Checker (LLM Agent)"}


@app.post("/analyze/")
async def analyze(file: UploadFile = File(...)):
    is_valid, msg = await validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    path = await save_upload(file)
    # Extract text based on file type
    if path.lower().endswith(".pdf"):
        text = await extract_text_from_pdf(path)
    elif path.lower().endswith(".docx"):
        text = await extract_text_from_docx(path)
    else:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX allowed")

    report = await agent.analyze(text)
    return JSONResponse(content=report)


@app.post("/correct/")
async def correct(file: UploadFile = File(...), output_format: str = Query(None, enum=["docx", "pdf"])):
    is_valid, msg = await validate_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    path = await save_upload(file)

    # Extract text based on file type
    if path.lower().endswith(".pdf"):
        if output_format is None:
            output_format = "pdf"
        text = await extract_text_from_pdf(path)
    elif path.lower().endswith(".docx"):
        text = await extract_text_from_docx(path)
    else:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX allowed")

    corrected_text = await agent.correct_whole(text)
    base_name = os.path.basename(path)
    corrected_filename = f"corrected_{base_name}.docx"
    corrected_path = os.path.join(CORRECTED_DIR, corrected_filename)

    from utils import save_docx_text

    if output_format == "pdf":
        try:
            pdf_path = corrected_path.replace(".docx", ".pdf")
            pdf_path = await save_pdf_text(corrected_text, pdf_path)
            return FileResponse(pdf_path, media_type="application/pdf", filename=os.path.basename(pdf_path))
        except Exception:
            # PDF conversion failed, return docx instead
            print("Error converting to PDF", traceback.format_exc())

    await save_docx_text(corrected_path, corrected_text)

    return FileResponse(corrected_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=os.path.basename(corrected_path))


@app.get("/download_corrected/{filename}")
async def download_corrected(filename: str):
    path = os.path.join(CORRECTED_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    # Set correct media type based on file extension
    if filename.lower().endswith(".pdf"):
        media = "application/pdf"
    else:
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path, media_type=media, filename=filename)

@app.get("/files")
async def correct_files():
    files = os.listdir(CORRECTED_DIR)
    return JSONResponse(content={"files": files}, status_code=200)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
