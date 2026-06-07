# BankIQ — Smart Banking Assistant
TCS External AI Training June-2026 Batch 1

Agentic RAG system for BFSI built with LangGraph, FastAPI, PostgreSQL + pgvector, and Streamlit.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL 15+ with the `pgvector` extension installed

---

## 1. Clone & install dependencies

```bash
git clone https://github.com/sudoautomation/smart_banking_project.git
cd smart_banking_project/Smart-Bank
uv sync
```

---

## 2. Configure environment variables

```bash
cp env.example .env
```

Edit `.env` and fill in your values:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `COHERE_API_KEY` | Cohere API key (for reranking) |
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://user:password@localhost:5432/bankiq` |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional, for tracing) |

---

## 3. Set up the database

Create the database, then run the init script to create all tables and seed demo data:

```bash
# Using psql
psql -U postgres -d bankiq -f init_db.sql

# Or via pgAdmin 4: right-click the database → Query Tool → open init_db.sql → F5
```

---

## 4. Ingest knowledge base documents

Run the ingestion pipeline to parse PDFs, generate embeddings, and store them in the vector store:

```bash
uv run python -m app.ingest.ingest_runner
```

This processes the PDFs in the `data/` folder (`KB_Smart_Banking.pdf`, `HR_Knowledge_Base_2025.pdf`).

---

## 5. Start the API server

```bash
uv run python main.py
```

The FastAPI server starts at **http://localhost:8000**.  
Interactive API docs: **http://localhost:8000/docs**

---

## 6. Start the Streamlit UI

Open a second terminal in the same directory:

```bash
uv run streamlit run ui/app.py
```

The chat UI opens at **http://localhost:8501**.

---

## Project structure

```
Smart-Bank/
├── app/
│   ├── api/          # FastAPI routers and chat service
│   ├── ingest/       # Document parsing and embedding pipeline
│   ├── models/       # Pydantic models
│   ├── orchestrator/ # LangGraph graph, nodes, state, tools
│   ├── retrieval/    # Multimodal RAG and NL-to-SQL retrieval
│   └── utils/        # DB connection, OpenAI client, prompts, schemas
├── data/             # Source PDF knowledge base files
├── ui/               # Streamlit frontend
├── config.py         # App-wide configuration
├── init_db.sql       # Database schema and seed data
├── main.py           # FastAPI entrypoint
└── pyproject.toml    # Dependencies
```
