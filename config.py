# config.py — northstar-bank
# Single source of truth for all configuration.
# Secrets loaded from .env; all tunables defined here as constants.

from dotenv import load_dotenv
import os

load_dotenv()

### Secrets (from .env) 
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
COHERE_API_KEY  = os.getenv("COHERE_API_KEY")
DATABASE_URL    = os.getenv("DATABASE_URL")
AGENTIC_URL     = os.getenv("AGENTIC_URL")
GUARDRAILS_API_KEY = os.getenv("GUARDRAILS_API_KEY")

### OpenAI Models 
OPENAI_CHAT_MODEL       = "gpt-5.4"
OPENAI_VLM_MODEL        = "gpt-5.4"
OPENAI_EMBEDDING_MODEL  = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMS   = 1536

### Cohere 
COHERE_RERANK_MODEL= "rerank-v3.5"

### pgvector 
VECTOR_DIMS = OPENAI_EMBEDDING_DIMS

### Retrieval 
RETRIEVAL_TOP_K     = 20
RERANK_TOP_N        = 4
RELEVANCE_THRESHOLD = 0.3
RRF_K               = 60
MAX_RETRY           = 2

### Ingest
CHUNK_SIZE            = 512
CHUNK_OVERLAP         = 64
INGEST_MAX_FILE_MB    = 50
INGEST_ALLOWED_TYPES  = [".pdf"]

### LLM Temperatures
CHAT_TEMPERATURE        = 0.0
NL_TO_SQL_TEMPERATURE   = 0.0
REPHRASER_TEMPERATURE   = 0.2
