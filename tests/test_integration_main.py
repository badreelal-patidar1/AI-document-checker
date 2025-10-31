import pytest
import fitz
import mimetypes
import io
from docx import Document
from fastapi.testclient import TestClient
from main import app, UPLOAD_DIR, CORRECTED_DIR

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path, monkeypatch):
    """Redirect upload/corrected dirs to temporary folder during tests"""
    upload_dir = tmp_path / "uploads"
    corrected_dir = tmp_path / "corrected"
    upload_dir.mkdir()
    corrected_dir.mkdir()
    monkeypatch.setattr("main.UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr("main.CORRECTED_DIR", str(corrected_dir))
    yield


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]


@pytest.mark.asyncio
async def test_analyze_pdf(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    #  Create a real PDF file
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello, PyMuPDF!")  # add some text
    doc.save(pdf_path)
    doc.close()

    #  Mock async functions
    async def fake_validate_file(file): return True, "Valid file type"
    async def fake_save_upload(file): return str(pdf_path)
    async def fake_extract_text_from_pdf(path): return "PDF text content"

    # monkeypatch.setattr("utils.validate_file", fake_validate_file)
    monkeypatch.setattr("main.validate_file", fake_validate_file)
    monkeypatch.setattr("main.save_upload", fake_save_upload)
    monkeypatch.setattr("utils.extract_text_from_pdf", fake_extract_text_from_pdf)

    #  Dummy AI agent
    class DummyAgent:
        async def analyze(self, text):
            return {"grammar_issues": [], "clarity_issues": []}

    monkeypatch.setattr("main.agent", DummyAgent())

    #  Send request to FastAPI
    with open(pdf_path, "rb") as f:
        response = client.post("/analyze/", files={"file": ("sample.pdf", f, "application/pdf")})

    print(response.json())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_correct_docx(monkeypatch, tmp_path):
    docx_path = tmp_path / "sample.docx"
    doc = Document()
    doc.add_paragraph("This is a test DOCX document.")
    doc.save(docx_path)

    async def fake_validate_file(file):
        return True, "Valid file type"

    async def fake_save_upload(file):
        return str(docx_path)

    async def fake_extract_text_from_docx(path):
        return "DOCX content"

    async def fake_save_docx_text(path, text):
        out_dir = tmp_path / "corrected"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "corrected_sample.docx.docx"
        out_path.write_text("Corrected content.")
        return str(out_path)

    monkeypatch.setattr("main.validate_file", fake_validate_file)
    monkeypatch.setattr("main.save_upload", fake_save_upload)
    monkeypatch.setattr("utils.extract_text_from_docx", fake_extract_text_from_docx)
    monkeypatch.setattr("utils.save_docx_text", fake_save_docx_text)

    class DummyAgent:
        async def correct_whole(self, text):
            return "Corrected content."
    monkeypatch.setattr("main.agent", DummyAgent())

    with open(docx_path, "rb") as f:
        response = client.post(
            "/correct/",
            files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    print("Response:", response.json() if "application/json" in response.headers.get("content-type", "") else "File OK")
    assert response.status_code == 200
    
def test_download_corrected_not_found():
    response = client.get("/download_corrected/nonexistent.docx")
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]
