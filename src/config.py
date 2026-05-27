"""Loads .env and exposes constants + clients for the experiment.

This is the single source of truth for model IDs, endpoints, and clients.
Per the Hard Constraints in AGENT_INSTRUCTIONS.md section 0: model IDs are
fixed for the whole run.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Resolve project root from this file's location: src/config.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root (NOT current working directory, to be robust)
load_dotenv(PROJECT_ROOT / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY is not set in .env")
if not SILICONFLOW_API_KEY:
    raise RuntimeError("SILICONFLOW_API_KEY is not set in .env")

# Endpoints
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

# Fixed model IDs (do not change mid-run)
MODEL_INGEST = "deepseek-chat"
MODEL_ANSWER = "deepseek-chat"
MODEL_BENCHMARK_GEN = "deepseek-chat"
MODEL_EMBEDDING = "BAAI/bge-m3"

# Cost rates (USD per 1M tokens)
COST_DEEPSEEK_INPUT_PER_M = 0.27
COST_DEEPSEEK_OUTPUT_PER_M = 1.10

# Budget cap (USD) — defined in section 4.3
BUDGET_CAP_USD = 15.0

# Clients (OpenAI-compatible)
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
siliconflow_client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=SILICONFLOW_BASE_URL)

# Filesystem layout (absolute paths)
RAW_DIR = PROJECT_ROOT / "raw"
RAW_CHAPTERS_DIR = RAW_DIR / "chapters"
RAW_FULL_TXT = RAW_DIR / "hongloumeng_full.txt"
RAW_SOURCES_CSV = RAW_DIR / "sources.csv"

WIKI_DIR = PROJECT_ROOT / "wiki"
WIKI_INGEST_LOGS_DIR = WIKI_DIR / ".ingest_logs"
WIKI_INDEX_MD = WIKI_DIR / "index.md"
WIKI_LOG_MD = WIKI_DIR / "log.md"

BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
BENCHMARK_QUESTIONS = BENCHMARK_DIR / "questions.json"
BENCHMARK_GROUND_TRUTH = BENCHMARK_DIR / "ground_truth.json"
BENCHMARK_GEN_LOG = BENCHMARK_DIR / "generation_log.md"

RAG_DIR = PROJECT_ROOT / "rag_baseline"
RAG_CHUNKS_JSONL = RAG_DIR / "chunks.jsonl"
RAG_CHROMA_DIR = RAG_DIR / "chroma_db"

RESULTS_DIR = PROJECT_ROOT / "results"
WIKI_ANSWERS_JSON = RESULTS_DIR / "wiki_answers.json"
RAG_ANSWERS_JSON = RESULTS_DIR / "rag_answers.json"
STATS_JSON = RESULTS_DIR / "stats.json"

CHECKPOINTS_DIR = PROJECT_ROOT / "checkpoints"
USAGE_JSON = PROJECT_ROOT / "usage.json"
MANIFEST_JSON = PROJECT_ROOT / "MANIFEST.json"
PROGRESS_MD = PROJECT_ROOT / "PROGRESS.md"
BLOCKERS_MD = PROJECT_ROOT / "BLOCKERS.md"
