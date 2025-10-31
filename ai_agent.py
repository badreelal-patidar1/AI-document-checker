import os
import json
import hashlib
import asyncio
from dotenv import load_dotenv
import spacy
from openai import OpenAI
from utils import CHUNK_SIZE, chunk_text

# Load environment variables
load_dotenv()

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


CACHE_FILE = "llm_cache.json"   # global cache file

def load_cache():
    """Load cache from file on startup."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

async def save_cache():
    """Save cache to file when updated."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(CACHE, f, indent=2)

# Initialize global cache
CACHE = load_cache()

async def _hash_text(text: str) -> str:
    """Generate a short hash for text for caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LLMAgent:
    def __init__(self, model_name: str = None):
        self.model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def nlp_summary(self, text: str) -> dict:
        """
        Perform basic NLP analysis on the provided text.

        This method uses spaCy to extract:
            - Sentence count and each sentence
            - Named entities found in the text, with their labels
            - A sample of the first 30 tokens with their part-of-speech tags

        Args:
            text (str): Input text for analysis

        Returns:
            dict: Contains 'sentence_count', 'sentences', 'entities', and 'pos_sample'
        """
        doc = await asyncio.to_thread(nlp, text)
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        pos_sample = [(token.text, token.pos_) for idx, token in enumerate(doc) if idx < 30]
        return {
            "sentence_count": len(sentences),
            "sentences": sentences,
            "entities": entities,
            "pos_sample": pos_sample,
        }

    async def _call_openai_chat(self, messages, max_tokens=1500, temperature=0.0, response_format=None):
        """Wrapper for OpenAI API with internal cache check."""
        # Build cache key
        key_data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format":response_format
        }
        cache_key = await _hash_text(json.dumps(key_data, sort_keys=True,indent=2))
        if cache_key in CACHE:
            # print(f"[CACHE HIT] Skipping API call for key {cache_key[:10]}...")
            return CACHE[cache_key]
        

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        content = response.choices[0].message.content
        CACHE[cache_key] = content  # save result
        await save_cache()        
        return content

    async def analyze(self, text: str) -> dict:
        """
        Analyze the given text for grammar, clarity, and style issues using NLP and LLM methods.

        This method:
        1. Summarizes basic NLP statistics from the text (sentence count, entities, etc.)
        2. Splits the text into manageable chunks.
        3. For each chunk, sends it to the LLM for compliance checking.
        4. Aggregates the results across all chunks, including detected issues and suggested corrections.

        Args:
            text (str): The input text to analyze.

        Returns:
            dict: A dictionary containing:
                - 'grammar_issues': List of grammar issues found.
                - 'clarity_issues': Suggestions to improve clarity.
                - 'style_issues': Suggestions regarding tone, word choice, etc.
                - 'per_chunk_reports': Per-chunk analysis results.
        """
        nlp_info = await self.nlp_summary(text)
        chunks = await chunk_text(text, chunk_size=CHUNK_SIZE)
        combined_findings = {
            "grammar_issues": [],
            "clarity_issues": [],
            "style_issues": [],
            "per_chunk_reports": [],
        }

        for idx, chunk in enumerate(chunks):
            est_tokens = min(CHUNK_SIZE, int(len(chunk) / 3) + 1500)
            prompt = f"""You are an English writing guideline checker.

            Task:
            Given an NLP context and a text chunk, analyze the text and produce output strictly
            in valid JSON format with the following fields:

            {{
            "grammar_issues": [ 
                "Short description of each grammar issue with the problematic text snippet" 
            ],
            "corrected_text": [ 
                "Revised sentences where errors are corrected; the corrected parts should be **bolded**" 
            ],
            "clarity_issues": [ 
                "Suggestions to improve clarity or reduce ambiguity" 
            ],
            "style_issues": [ 
                "Suggestions regarding tone, formality, or word choice" 
            ]
            }}

            Rules:
            - Always return all four keys, even if a list is empty.
            - Do not include any text outside the JSON object.
            - Keep the JSON valid and properly formatted.

            Example input:
            "The report have too many errors and it need revised."

            Example output:
            {{
            "grammar_issues": [
                "Subject-verb agreement error: 'report have' should be 'report has'",
                "Verb form error: 'need revised' should be 'needs revision'"
            ],
            "corrected_text": [
                "The **report has** too many errors and **needs revision**."
            ],
            "clarity_issues": [
                "Specify what kind of errors (spelling, data, or format) for clarity."
            ],
            "style_issues": [
                "Consider a more formal tone if used in a business report."
            ]
            }}

            Now, analyze the following text:
            NLP context:
            Sentence count: {nlp_info['sentence_count']}
            Sample entities: {nlp_info['entities'][:8]}

            Text chunk:
            \"\"\"{chunk}\"\"\"
            """

            messages = [
                {"role": "system", "content": "You are an English writing guideline checker."},
                {"role": "user", "content": prompt},
            ]

            # cache per chunk
            cache_key = await _hash_text(chunk + "_analysis")
            if cache_key in CACHE:
                out = CACHE[cache_key]
            else:
                try:
                    out = await self._call_openai_chat(messages, max_tokens=est_tokens,
                                                 response_format={"type": "json_object"})
                    CACHE[cache_key] = out
                    await save_cache()
                except Exception as e:
                    out = json.dumps({"error": "openai_call_failed", "message": str(e)},indent=2)

            try:
                parsed = json.loads(out)
            except Exception:
                parsed = {"raw_output": out}

            parsed["_chunk_index"] = idx
            combined_findings["per_chunk_reports"].append(parsed)

        combined_findings["summary"] = "Combined report from LLM over chunks."
        return combined_findings

    async def correct_whole(self, text: str) -> str:
        """
        Correct the entire input `text` for grammar, clarity, conciseness, and professionalism,
        while preserving original meaning, structure, and formatting.

        The text is chunked for prompt size limits. Each chunk is sent to an LLM with
        instructions to:
         - Only return the direct corrected version (no comments or explanations)
         - Retain styles such as bold, italics, underline, and colors

        Caching is used to avoid repeating work. Corrected chunks are then joined and returned.

        Args:
            text (str): The raw document text to be corrected.

        Returns:
            str: The fully corrected document assembled from corrected chunks.
        """
        # See method body below...
        chunks = await chunk_text(text, chunk_size=CHUNK_SIZE)
        corrected_parts = []

        for chunk in chunks:
            est_tokens = min(3500, int(len(chunk) / 3) + 1500)
            prompt = f"""
            You are an expert English editor.
            Rewrite the following text to be grammatically correct, clear, concise, and professional.
            Preserve the original meaning and key facts.
            Rules:
            - Do not include any other text or comments
            - Return only the corrected text.
            - Keep the original text structure and formatting,fonts,styles,color,bold,italic,etc.

            Text:
            \"\"\"{chunk}\"\"\""""

            messages = [
                {"role": "system", "content": "You are an expert English editor."},
                {"role": "user", "content": prompt},
            ]

            cache_key = await _hash_text(chunk + "_correction")
            if cache_key in CACHE:
                corrected = CACHE[cache_key]
            else:
                corrected = await self._call_openai_chat(messages, max_tokens=est_tokens, temperature=0.0)
                CACHE[cache_key] = corrected
                await save_cache()

            corrected_parts.append(corrected.strip())

        return "\n\n".join(corrected_parts)
