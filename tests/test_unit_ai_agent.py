import os
import json
import asyncio
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from ai_agent import LLMAgent, CACHE, save_cache, load_cache, _hash_text


# ---------- FIXTURES ----------

@pytest.fixture(scope="module")
def sample_text():
    return "The report have too many errors and it need revised. The data is accurate though."


@pytest.fixture
def fake_openai_response():
    """Mocked OpenAI JSON-style response object."""
    class FakeChoice:
        def __init__(self):
            self.message = MagicMock(content=json.dumps({
                "grammar_issues": ["Fake issue"],
                "corrected_text": ["The **report has** too many errors and **needs revision**."],
                "clarity_issues": ["Fake clarity"],
                "style_issues": ["Fake style"]
            }))
    class FakeResponse:
        choices = [FakeChoice()]
    return FakeResponse()


@pytest.fixture(autouse=True)
def clear_cache(tmp_path):
    """Ensure CACHE is isolated between tests."""
    from ai_agent import CACHE_FILE
    CACHE.clear()
    yield
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


# ---------- BASIC HELPERS ----------

@pytest.mark.asyncio
async def test_hash_text_is_consistent():
    h1 = await _hash_text("hello")
    h2 = await _hash_text("hello")
    assert h1 == h2
    assert len(h1) == 64  # sha256


@pytest.mark.asyncio
async def test_cache_load_and_save(tmp_path):
    cache_path = tmp_path / "cache.json"
    fake_cache = {"abc": "123"}

    # Save cache
    from ai_agent import CACHE_FILE, CACHE
    CACHE_FILE = str(cache_path)
    CACHE.update(fake_cache)
    await save_cache()

    # Load again
    loaded = load_cache()
    assert loaded == fake_cache


# ---------- NLP SUMMARY ----------

@pytest.mark.asyncio
async def test_nlp_summary_counts(sample_text):
    agent = LLMAgent()
    result = await agent.nlp_summary(sample_text)
    assert "sentence_count" in result
    assert isinstance(result["sentences"], list)
    assert isinstance(result["entities"], list)
    assert any(isinstance(pair, tuple) for pair in result["pos_sample"])


# ---------- OPENAI CALL (MOCKED) ----------

@pytest.mark.asyncio
@patch("ai_agent.client.chat.completions.create")
async def test_call_openai_chat_uses_cache(mock_create, fake_openai_response):
    mock_create.return_value = fake_openai_response
    agent = LLMAgent()
    messages = [{"role": "user", "content": "hello"}]
    result1 = await agent._call_openai_chat(messages)
    assert isinstance(result1, str)

    # Second call should hit cache (no new call)
    result2 = await agent._call_openai_chat(messages)
    assert result2 == result1
    assert mock_create.call_count == 1  # cached


# ---------- ANALYZE METHOD ----------

@pytest.mark.asyncio
@patch("ai_agent.client.chat.completions.create")
async def test_analyze_text_returns_json(mock_create, fake_openai_response, sample_text):
    mock_create.return_value = fake_openai_response
    agent = LLMAgent()

    result = await agent.analyze(sample_text)

    assert "grammar_issues" in result
    assert "clarity_issues" in result
    assert "style_issues" in result
    assert "per_chunk_reports" in result
    assert isinstance(result["per_chunk_reports"], list)
    assert "summary" in result


# ---------- ANALYZE WITH INVALID JSON (simulate error) ----------

@pytest.mark.asyncio
@patch("ai_agent.client.chat.completions.create")
async def test_analyze_handles_invalid_json(mock_create):
    mock_create.return_value = MagicMock()
    mock_create.return_value.choices = [MagicMock(message=MagicMock(content="INVALID JSON"))]
    agent = LLMAgent()
    result = await agent.analyze("Bad output example.")
    assert "per_chunk_reports" in result
    assert isinstance(result["per_chunk_reports"], list)


# ---------- CORRECT WHOLE METHOD ----------

@pytest.mark.asyncio
@patch("ai_agent.client.chat.completions.create")
async def test_correct_whole_combines_chunks(mock_create, fake_openai_response, sample_text):
    mock_create.return_value = fake_openai_response
    agent = LLMAgent()

    result = await agent.correct_whole(sample_text)
    print(result)
    assert "report" in result
    assert "**" in result or "Fake" not in result
    assert result.startswith("{")
    assert result.endswith("}")
    # Should contain both sentences combined
    assert isinstance(result, str)
    


# ---------- CACHE BEHAVIOR ----------

@pytest.mark.asyncio
async def test_analyze_uses_cache_directly(sample_text):
    agent = LLMAgent()
    cache_key = await _hash_text(sample_text + "_analysis")
    CACHE[cache_key] = json.dumps({"grammar_issues": ["cached"], "clarity_issues": [], "style_issues": [], "corrected_text": []},indent=2)
    result = await agent.analyze(sample_text)
    assert any("cached" in json.dumps(c,indent=2) for c in result["per_chunk_reports"])
