# 🧾 Doc Checker — AI Grammar & Document Correction API

## 📘 Overview
**Doc Checker** is an AI-powered FastAPI service that analyzes and corrects grammar, clarity, and writing style issues in uploaded documents (PDF, DOCX, TXT, etc.).  
It uses **OpenAI**, **spaCy**, and **PyMuPDF** for NLP and text extraction.  
It uses a file-based cache system to avoid unnecessary token usage.

---

## ⚙️ Setup Guide

### 1️⃣ Install UV (Fast Python Environment Manager)
First, install **uv** globally:

```bash
pip install uv
```
---

### 2️⃣ Create & Activate Virtual Environment
```bash
uv venv
uv activate
```

---

### 3️⃣ Install Dependencies
```bash
uv pip install -e .
```
---
```
### download spacy model
python -m spacy download en_core_web_sm
```

### 4️⃣ Create Environment File
Create a `.env` file and copy .env.copy from root folder

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL="gpt-4.1-mini"
```

Get your OpenAI API key from [https://platform.openai.com/](https://platform.openai.com/)

---

### 5️⃣ Run the FastAPI Server
```bash
python main.py
```

Now open your browser and go to:  
👉 **http://127.0.0.1:8000/docs**

You’ll see the Swagger UI for interactive testing.

---

## 🧪 Running Tests

We use **pytest** for unit & integration tests.

Run all tests:
```bash
pytest -v
```
---
## 📁 Project Structure

```
doc_checker/
│
├── main.py                # FastAPI app entry point
├── utils.py               # Helper functions (PDF/DOCX extraction, validation)
├── ai_agent.py            # AI grammar correction logic
├── tests/
│   └── test_main.py       # All pytest test cases
├── pyproject.toml
├── .env.copy
└── README.md
```

---

## 🚀 Example API Usage

### Endpoint: `/correct/`

**Request (Multipart Form Data):**
```
POST /correct/
file: sample.docx
```

**Response:**
```json
{
  "per_chunk_reports":{"grammar_issues": [],
  "clarity_issues": [],
  "style_issues": [],
  "corrected_text": []
  }
}
```

---

## 🧠 Tech Stack

| Component | Description |
|------------|--------------|
| **FastAPI** | Backend framework |
| **spaCy** | NLP text processing |
| **PyMuPDF (fitz)** | PDF parsing |
| **python-docx** | Word document reading |
| **OpenAI GPT** | AI-based correction |
| **pytest** | Testing framework |
| **uv** | Lightweight Python environment manager |

---

## 🧩 Common Issues

### ❌ Error: `application/octet-stream`
Some file uploads (especially `.docx`) are detected as `"application/octet-stream"`.  
This is safe and handled automatically by the validator.  
If you’re writing tests, mock validation like:
```python
assert content_type in (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream"
)
```

### ⚠️ Warning: `DeprecationWarning` from spaCy
This is safe to ignore. It’s due to internal Click version changes and doesn’t affect functionality.

---

## 🛠 Example Development Commands

Reformat code:
```bash
uv pip install black isort
black .
isort .
```

Run with hot reload:
```bash
uvicorn main:app --reload
```

Run single test:
```bash
pytest tests/test_main.py::test_correct_docx -v
```

---

## 🧑‍💻 Developer Information

**Badreelal Patidar**  
📧 blpatidar03@gmail.com  
🧠 Skills: Python, FastAPI, NLP, Machine Learning, Automation  

---

## 💡 Notes

- Supported file types: `.pdf`, `.docx`
- All uploads are stored in root folder
- Large documents are automatically split for analysis
- API responses are pure JSON (except corrected file downloads)

---

### ☁️ Using Render or Vercel
Just set `OPENAI_API_KEY` in your environment variables  
and your **Start Command** should be:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

✨ **Now you can run, test, and deploy your AI-powered document correction API easily!**
