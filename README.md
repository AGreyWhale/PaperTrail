# PaperTrail

An AI research paper assistant: keep a personal library of papers, attach the PDFs, and ask questions that get answered with citations back to the exact page.


---

## What works today

- **Clerk authentication** on every route, with papers scoped to their owner — you only ever see your own library.
- **Add a paper by DOI.** Looks the DOI up against the CrossRef REST API, maps the result into a title/authors/venue/year preview, and saves it on confirmation.
- **Attach a PDF** to a paper. Uploads are checked for the `%PDF-` magic bytes and a size limit (50 MB by default) before landing in local file storage behind a swappable `FileStorage` interface.
- **Process a PDF into chunks.** `pdfplumber` extracts per-page text, a sentence-aware chunker packs it into ~500-token chunks with a 2-sentence overlap, and each chunk keeps the page it started on so citations can point back to it later.
- **Embed a paper's chunks in the background.** `POST /papers/{id}/embed` validates and returns immediately with `embedding_status="queued"`; a Celery worker runs a local `sentence-transformers` BGE model and writes the vectors into Chroma, scoped by owner and paper. Status moves `queued → embedding → embedded`, or `failed`.
- **Semantic search inside a paper.** `GET /papers/{id}/similar?query=…` embeds the query and returns the closest chunks with their page numbers and a similarity score.
- **Ask a question about a paper.** `POST /papers/{id}/ask` retrieves the most relevant chunks, grounds an LLM answer in them, and returns the chunks it actually used as citations — real sources, not text parsed back out of the answer.
- **66 passing backend tests** covering auth, papers, uploads, processing, chunking, the PDF parser, the CrossRef client/mapper, the embedding job, search, and RAG.

## What's in progress

| Area | State |
| --- | --- |
| Library-wide search | Search and Q&A are scoped to one paper at a time; cross-library retrieval is next |
| Retry / observability | A failed embedding job sets `embedding_status="failed"`, but there's no retry policy or job-status endpoint yet |
| `torch` install size | `sentence-transformers` pulls in torch, so a full `make install` is a large download. The test suite fakes it out and never needs it |
| Frontend | `App.tsx` is a component/auth preview page; no routing, no real library UI, and nothing wired to the embed/search/ask endpoints yet (`react-router-dom` and `@tanstack/react-query` are installed but unused) |

---

## Tech stack

**Backend** — Python 3.10, FastAPI, SQLAlchemy 2.0, Alembic, Postgres 16, pdfplumber, Celery, Chroma, sentence-transformers, Clerk, pytest
**Frontend** — React 19, TypeScript, Vite, Tailwind CSS v4, Clerk, oxlint, pnpm
**Infra (dev)** — Docker Compose (Postgres + Redis + Chroma), local disk for file storage

Embeddings run locally via `sentence-transformers`, so there's no per-token cost or rate limit on them. Answer generation goes to any OpenAI-compatible endpoint (Groq's free tier by default) — switching providers is three values in `.env`, not a code change.

## Layout

```
backend/
  app/
    api/              FastAPI routers (health, papers)
    core/             config, database session, Clerk auth dependency
    models/           SQLAlchemy models (Paper, Chunk)
    schemas/          Pydantic request/response models
    repositories/     all DB access lives here, one per model
    services/         business logic (papers, uploads, processing, DOI lookup, embedding, search, RAG)
    parsing/          PDF text extraction
    chunking/         sentence-aware chunker
    storage/          FileStorage interface + local-disk implementation
    integrations/     CrossRef client/mapper, local embeddings client, LLM client
    vectorstore/      Chroma wrapper
    workers/          Celery app + the embedding job
  alembic/            migrations
  tests/
frontend/
  src/
    components/ui/    Button, Card, Input, PaperTile + feature components
    lib/              authenticated fetch wrapper, class-name helper
    index.css         Tailwind theme tokens (warm paper palette)
docker-compose.yml    postgres + redis + chroma
Makefile              every dev command
```

The layering is deliberate: routers depend on services, services depend on repositories and interfaces, and repositories are the only thing that touches the database. Swapping Postgres or local disk for something else should be a change to the wiring, not to the business logic.

The same idea covers background work. `app/workers/tasks.py` only builds real dependencies (a DB session, the embeddings model, a Chroma connection) and hands them to `run_embedding_job`, which holds the actual logic. So the job is tested directly with fakes, and no test needs Celery or Redis running.

---

## Getting started

**Prerequisites:** Docker, Python 3.10, pnpm, and a [Clerk](https://clerk.com) application (free tier is fine).

```bash
# 1. Backend virtualenv
python3.10 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt

# 2. Frontend deps
cd frontend && pnpm install && cd ..

# 3. Environment (see below), then:
make dev
```

`make dev` starts Postgres, Redis and Chroma, runs migrations, and brings up the API on <http://localhost:8000> (docs at `/docs`) and the web app on <http://localhost:5173>. Ctrl-C stops both.

Embedding runs in a Celery worker, so it needs its own terminal:

```bash
make worker
```

Without it, `POST /papers/{id}/embed` still returns `queued` — the job just sits on the queue until a worker picks it up.

### Environment

There are no `.env.example` files checked in yet — create these by hand.

`backend/.env`

| Variable | Notes |
| --- | --- |
| `DATABASE_URL` | Defaults to the docker-compose Postgres |
| `CORS_ORIGINS` | Comma-separated; defaults to both spellings of the Vite dev server |
| `CLERK_SECRET_KEY` | Clerk dashboard → API Keys → Secret key |
| `CLERK_AUTHORIZED_PARTIES` | Comma-separated frontend origins |
| `CROSSREF_CONTACT_EMAIL` | Sent to CrossRef as `mailto` for their polite pool |
| `LLM_API_KEY` | Any OpenAI-compatible provider; defaults assume [Groq](https://console.groq.com/keys). `/ask` returns 503 without it |
| `LLM_BASE_URL` | Defaults to Groq's OpenAI-compatible endpoint |
| `LLM_MODEL` | Defaults to `llama-3.3-70b-versatile` |
| `EMBEDDING_MODEL` | Defaults to `BAAI/bge-small-en-v1.5`; downloaded and cached on first use |
| `CHROMA_HOST` / `CHROMA_PORT` | Defaults to the docker-compose Chroma on port 8100 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Default to the docker-compose Redis |
| `MAX_UPLOAD_SIZE_MB` | Defaults to 50 |
| `LOCAL_STORAGE_ROOT` | Defaults to `./storage` |

`frontend/.env`

| Variable | Notes |
| --- | --- |
| `VITE_CLERK_PUBLISHABLE_KEY` | Clerk publishable key; the app throws on startup without it |
| `VITE_API_BASE_URL` | e.g. `http://localhost:8000` |

### Make targets

| Command | What it does |
| --- | --- |
| `make dev` | Containers + migrations, then API and web together |
| `make api` / `make web` | One side only |
| `make worker` | Celery worker for embedding jobs (run in its own terminal) |
| `make up` / `make down` | Start / stop the containers (data is kept) |
| `make migrate` | Bring the schema up to head |
| `make test` | Backend test suite |
| `make build` | Typecheck + production build of the frontend |
| `make install` | Sync both dependency sets after a pull |
| `make clean` | Drop containers **and** their volumes — wipes all Postgres and Chroma data |

Every recipe calls the venv binaries by absolute path, so you never need to activate the virtualenv first.

---

## API

All `/api` routes require a Clerk bearer token.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Liveness check (unauthenticated) |
| `GET` | `/api/papers/lookup?doi=…` | Resolve a DOI (bare or `doi.org` URL) via CrossRef |
| `POST` | `/api/papers` | Add a paper to your library |
| `GET` | `/api/papers` | List your papers, newest first |
| `GET` | `/api/papers/{id}` | Fetch one paper |
| `POST` | `/api/papers/{id}/file` | Attach a PDF (multipart) |
| `POST` | `/api/papers/{id}/process` | Extract text and rebuild the paper's chunks |
| `GET` | `/api/papers/{id}/chunks` | List a paper's chunks in order |
| `POST` | `/api/papers/{id}/embed` | Queue background embedding of the paper's chunks |
| `GET` | `/api/papers/{id}/similar?query=…&top_k=…` | Semantic search within the paper |
| `POST` | `/api/papers/{id}/ask` | Ask a question, answered from the paper with citations |

`embed`, `similar` and `ask` each depend on the previous step: a paper has to be `processed` before it can be embedded, and `embedded` before it can be searched or asked about. Both return 422 otherwise.

## Tests

```bash
make test
```

Tests run against an in-memory SQLite database with Clerk auth overridden to a fixed test user, so they never hit Postgres or Clerk's servers. Real token verification is covered separately in `test_auth.py` against a mocked Clerk client.

The embedding and RAG tests use `tests/fakes.py` throughout — a deterministic embedder (same text always gives the same vector, so round-trip retrieval can be asserted exactly) and a recording LLM client. Chroma runs as an in-process `EphemeralClient`. Nothing in the suite needs a worker, a broker, an API key, or the real model downloaded.

---

## Roadmap

1. Finish the embeddings client and Chroma vector store, and add their dependencies to `requirements.txt`
2. Embed chunks on processing and add retrieval scoped to a paper and its owner
3. Grounded Q&A over a paper, with citations back to page numbers
4. Move processing off the request path into a background worker (Redis is already running for this)
5. Replace the preview page with a real library UI — routing, paper detail, PDF viewer
6. S3-compatible storage for production
