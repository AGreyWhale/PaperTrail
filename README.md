# PaperTrail

![CI](https://github.com/AGreyWhale/PaperTrail/actions/workflows/ci.yml/badge.svg)

An AI research paper assistant: keep a personal library of papers, attach the PDFs, and ask questions that get answered with citations back to the exact page.


---

## What works today

- **Clerk authentication** on every route, with papers scoped to their owner — you only ever see your own library.
- **Add a paper by DOI.** Looks the DOI up against the CrossRef REST API, maps the result into a title/authors/venue/year preview, and saves it on confirmation.
- **Attach a PDF** to a paper. Uploads are checked for the `%PDF-` magic bytes and a size limit (50 MB by default) before landing in local file storage behind a swappable `FileStorage` interface.
- **Process a PDF into chunks.** `pdfplumber` extracts per-page text, a sentence-aware chunker packs it into ~500-token chunks with a 2-sentence overlap, and each chunk keeps the page it started on so citations can point back to it later.
- **Embed a paper's chunks in the background.** `POST /papers/{id}/embed` validates and returns immediately with `embedding_status="queued"`; a background job runs a local `sentence-transformers` BGE model and writes the vectors onto the chunk rows via pgvector, scoped by owner and paper. Status moves `queued → embedding → embedded`, or `failed`.
- **Semantic search inside a paper.** `GET /papers/{id}/similar?query=…` embeds the query and returns the closest chunks with their page numbers and a similarity score.
- **Ask a question about a paper.** `POST /papers/{id}/ask` retrieves the most relevant chunks, grounds an LLM answer in them, and returns the chunks it actually used as citations — real sources, not text parsed back out of the answer.
- **A real reading view.** The library is a routed paper grid with live pipeline status per tile. Opening a paper gives a two-pane view: the PDF rendered by pdf.js on the left, the assistant panel on the right, with process/embed triggers in the header and polling that flips the panel on by itself when embedding finishes.
- **Highlight-to-ask.** Selecting text in the PDF raises an Ask / Explain / Summarize toolbar that sends the passage straight to the assistant. This is why the PDF renders through pdf.js rather than a native `<iframe>` — a native viewer won't expose its text layer to page JavaScript.
- **Answers stream in.** `/ask/stream` sends citations first, then tokens as the model produces them, so the panel fills in progressively instead of waiting on a complete response. Retrieval and validation run before the first byte, so a 404/422 is still a real status code rather than an error buried inside a 200.
- **Library-wide semantic search.** `GET /api/search?q=…` embeds the query once and searches every embedded paper you own. Results are grouped **by paper, not by chunk** — three matching passages in one paper is one result showing its strongest excerpt and a match count, not three near-duplicate rows.
- **A home page separate from the library grid.** Library summary, Continue reading (real positions, persisted as you scroll), and LLM-generated starter questions cached per paper.
- **Compare mode and literature reviews.** Pick 2+ embedded papers and either get a structured side-by-side table (datasets, architecture, metrics, strengths, weaknesses, future work) or a synthesised markdown review that compares across sources and cites by paper — "(Gao et al., p. 5)" — with a Markdown export. Both share one retrieval helper that validates ownership and caps context per paper.
- **Favorites, tags, collections, and notes.** Tags and collections are proper relational models (per-owner unique tag names, many-to-many joins), so they stay filterable. Notes can stand alone or carry the passage they came from — **Save quote** in the PDF highlight toolbar opens a composer pre-filled with the selection, and notes live in their own tab beside Ask rather than crowding it.
- **A reading UI built for actually reading.** Zoom (buttons, `Ctrl`+scroll, `Ctrl` `+`/`-`/`0`, fit-width that re-fits when the pane resizes), pages rendered lazily a screen ahead, a resizable and collapsible assistant panel, adjustable answer text size, per-question history with copy, `/` to focus the ask box, and citations that scroll the PDF to the page and tint the quoted passage.
- **152 passing backend tests** covering auth, papers, uploads, file serving, processing, chunking, the PDF parser, the CrossRef client/mapper, the embedding job, per-paper and library-wide search, RAG, streaming, reading progress, favorites, tags, collections, and notes.

## What's in progress

| Area | State |
| --- | --- |
| Retry / observability | A failed embedding job sets `embedding_status="failed"`, but there's no retry policy or job-status endpoint yet |
| `torch` install size | `sentence-transformers` pulls in torch, so a full `make install` is a large download. The test suite fakes it out and never needs it |
| Home page sections | Notes and collections now exist, but the home page doesn't surface Recent Notes / Collections yet |
| Library-wide Q&A | Search spans the library, but `/ask` is still one paper at a time |

---

## Tech stack

**Backend** — Python 3.10, FastAPI, SQLAlchemy 2.0, Alembic, Postgres 16 + pgvector, pdfplumber, Celery, sentence-transformers, Clerk, pytest
**Frontend** — React 19, TypeScript, Vite, Tailwind CSS v4, React Router, TanStack Query, react-pdf/pdf.js, Clerk, oxlint, pnpm
**Infra (dev)** — Docker Compose (Postgres/pgvector + Redis), local disk for file storage

Embeddings run locally via `sentence-transformers`, so there's no per-token cost or rate limit on them. Answer generation goes to any OpenAI-compatible endpoint (Groq's free tier by default) — switching providers is three values in `.env`, not a code change.

## Layout

```
backend/
  app/
    api/              FastAPI routers (health, papers)
    core/             config, database session, Clerk auth dependency
    models/           SQLAlchemy models (Paper, Chunk, Tag, Collection, Note)
    schemas/          Pydantic request/response models
    repositories/     all DB access lives here, one per model
    services/         business logic (papers, uploads, processing, DOI lookup, embedding, search, RAG)
    parsing/          PDF text extraction
    chunking/         sentence-aware chunker
    storage/          FileStorage interface + local-disk implementation
    integrations/     CrossRef client/mapper, local embeddings client, LLM client
    workers/          Celery app + the embedding job
  alembic/            migrations
  tests/
frontend/
  src/
    pages/            HomePage, LibraryPage (grid + search), ReadingPage (PDF + assistant)
    components/       AIPanel, PdfViewer, AddPaperByDoi, AttachPdfButton
    components/ui/    Button, Card, Input, PaperTile
    components/layout/  AppShell (nav + routed outlet)
    lib/              authenticated fetch wrapper, class-name helper
    index.css         Tailwind theme tokens (warm paper palette)
docker-compose.yml    postgres (pgvector) + redis
Makefile              every dev command
```

The layering is deliberate: routers depend on services, services depend on repositories and interfaces, and repositories are the only thing that touches the database. Swapping Postgres or local disk for something else should be a change to the wiring, not to the business logic.

The same idea covers background work. `app/workers/tasks.py` has one function, `embed_paper_now`, that builds real dependencies (a fresh DB session, the embeddings model) and hands them to `run_embedding_job`, which holds the actual logic. The Celery task and the `BackgroundTasks` fallback are both one-line wrappers around it, so the two paths can't drift. The job is tested directly with fakes, and no test needs Celery or Redis running.

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

`make dev` starts Postgres and Redis, runs migrations, and brings up the API on <http://localhost:8000> (docs at `/docs`) and the web app on <http://localhost:5173>. Ctrl-C stops both.

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
| `LLM_MODEL` | Defaults to `openai/gpt-oss-120b`; must be one your key can serve (`GET {LLM_BASE_URL}/models` lists them) |
| `EMBEDDING_MODEL` | Defaults to `BAAI/bge-small-en-v1.5`; downloaded and cached on first use |
| `EMBEDDING_BACKEND` | `celery` (worker + Redis) or `background_tasks` (in-process, no worker — for free-tier hosting) |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Default to the docker-compose Redis; only used when `EMBEDDING_BACKEND=celery` |
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
| `make ports` | Check 8000/5173 are free (`make dev` runs this first and stops if not) |
| `make up` / `make down` | Start / stop the containers (data is kept) |
| `make migrate` | Bring the schema up to head |
| `make test` | Backend test suite (no external services needed) |
| `make test-pg` | The pgvector tests, against a real Postgres |
| `make build` | Typecheck + production build of the frontend |
| `make install` | Sync both dependency sets after a pull |
| `make clean` | Drop containers **and** their volumes — wipes all Postgres data |

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
| `GET` | `/api/papers/{id}/file` | Serve the raw PDF bytes (the reading view fetches this with auth) |
| `POST` | `/api/papers/{id}/process` | Extract text and rebuild the paper's chunks |
| `GET` | `/api/papers/{id}/chunks` | List a paper's chunks in order |
| `POST` | `/api/papers/{id}/embed` | Queue background embedding of the paper's chunks |
| `GET` | `/api/papers/{id}/similar?query=…&top_k=…` | Semantic search within the paper |
| `GET` | `/api/search?q=…&limit=…` | Library-wide search, one result per paper |
| `POST` | `/api/papers/compare` | Structured comparison table across 2–6 papers |
| `POST` | `/api/papers/literature-review` | Synthesised markdown review across 2–6 papers |
| `GET` | `/api/papers/continue-reading` | Most recently opened papers, with reading position |
| `POST` | `/api/papers/{id}/opened?page=…` | Record a visit and reading position |
| `DELETE` | `/api/papers/{id}` | Delete a paper, its chunks, notes, file and vectors |
| `PATCH` | `/api/papers/{id}/favorite` | Toggle favorite |
| `GET` | `/api/papers?tag={tag_id}` | List papers, optionally filtered by tag |
| `POST` / `DELETE` | `/api/papers/{id}/tags`, `/api/papers/{id}/tags/{tag_id}` | Attach / detach a tag |
| `GET` | `/api/tags` | The owner's tags, for autocomplete and filtering |
| `POST` / `GET` / `DELETE` | `/api/collections`, `/api/collections/{id}` | Manage collections |
| `POST` / `DELETE` | `/api/collections/{id}/papers/{paper_id}` | Add / remove a paper |
| `GET` | `/api/collections/{id}/papers` | Papers in a collection |
| `POST` / `GET` | `/api/papers/{id}/notes` | Create / list notes on a paper |
| `PATCH` / `DELETE` | `/api/notes/{id}` | Edit / delete a note |
| `GET` | `/api/papers/{id}/suggested-questions` | Starter questions, generated once then cached |
| `POST` | `/api/papers/{id}/ask` | Ask a question, answered from the paper with citations |
| `POST` | `/api/papers/{id}/ask/stream` | Same, streamed as NDJSON (`citations` → `token`… → `done`) |

`embed`, `similar` and `ask` each depend on the previous step: a paper has to be `processed` before it can be embedded, and `embedded` before it can be searched or asked about. Both return 422 otherwise.

## Tests

```bash
make test
```

Tests run against an in-memory SQLite database with Clerk auth overridden to a fixed test user, so they never hit Postgres or Clerk's servers. Real token verification is covered separately in `test_auth.py` against a mocked Clerk client.

The embedding and RAG tests use `tests/fakes.py` throughout — a deterministic embedder (same text always gives the same vector, so round-trip retrieval can be asserted exactly) and a recording LLM client. Nothing in the default suite needs a worker, a broker, an API key, or the real model downloaded.

One deliberate exception: pgvector's `cosine_distance()` is Postgres-only SQL and cannot run on SQLite. Rather than mock the distance computation and pretend the query works, the similarity queries are faked at the `ChunkRepository` boundary (`FakeChunkSearch`, which ranks in Python) for service-level tests, and the real SQL is exercised in `tests/test_pgvector.py` — marked `pg`, skipped unless `TEST_DATABASE_URL` is set. Run it with `make test-pg`.

---

## Roadmap

1. Re-embed existing papers — vectors used to live in Chroma and are not carried over by the migration
2. Embed chunks on processing and add retrieval scoped to a paper and its owner
3. Grounded Q&A over a paper, with citations back to page numbers
4. Move processing off the request path into a background worker (Redis is already running for this)
5. Replace the preview page with a real library UI — routing, paper detail, PDF viewer
6. S3-compatible storage for production
