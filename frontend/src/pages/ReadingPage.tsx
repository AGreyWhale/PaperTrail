import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../components/ui/Button";
import { AttachPdfButton } from "../components/AttachPdfButton";
import { AIPanel } from "../components/AIPanel";
import { FavoriteButton } from "../components/FavoriteButton";
import { TagInput } from "../components/TagInput";
import { AddToCollection } from "../components/AddToCollection";
import { PaperActions } from "../components/PaperActions";
import { PdfViewer } from "../components/PdfViewer";
import { useApiClient } from "../lib/api";
import type { Citation, Note, Paper } from "../lib/types";

//Either stage still running means the paper isn't ready yet
const TRANSIENT_EMBEDDING = new Set(["queued", "embedding"]);
const TRANSIENT_PROCESSING = new Set(["processing"]);

const PANEL_KEY = "papertrail:panel-width";
const COLLAPSED_KEY = "papertrail:panel-collapsed";
const PANEL_MIN = 320;
const PANEL_MAX = 900;

function clampPanel(width: number): number {
  return Math.min(PANEL_MAX, Math.max(PANEL_MIN, width));
}

export function ReadingPage() {
  const { paperId } = useParams<{ paperId: string }>();
  const [searchParams] = useSearchParams();
  const { request, requestBlobUrl } = useApiClient();
  const queryClient = useQueryClient();
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number }>();
  const [targetPage, setTargetPage] = useState<{ page: number; nonce: number }>();
  const [panelWidth, setPanelWidth] = useState(() => {
    const stored = Number(localStorage.getItem(PANEL_KEY));
    return stored ? clampPanel(stored) : 380;
  });
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(COLLAPSED_KEY) === "1",
  );
  const [highlight, setHighlight] = useState<string>();
  const [pendingQuote, setPendingQuote] = useState<{ text: string; page: number; nonce: number }>();
  const [showTags, setShowTags] = useState(false);
  const dragging = useRef(false);
  const openedRef = useRef(false);
  const pageTimer = useRef<number | undefined>(undefined);

  function toggleCollapsed(next: boolean) {
    setCollapsed(next);
    localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
  }

  const { data: paper } = useQuery({
    queryKey: ["paper", paperId],
    queryFn: () => request<Paper>(`/api/papers/${paperId}`),
    enabled: !!paperId,
    // Poll only while the pipeline is mid-flight, so the AI panel turns
    // usable on its own without a manual reload.
    refetchInterval: (query) => {
      const paper = query.state.data as Paper | undefined;
      if (!paper) return false;
      const busy =
        TRANSIENT_EMBEDDING.has(paper.embedding_status) ||
        TRANSIENT_PROCESSING.has(paper.processing_status);
      return busy ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!paper?.has_file || !paperId) {
      setPdfUrl(null);
      return;
    }
    let cancelled = false;
    setPdfError(null);
    requestBlobUrl(`/api/papers/${paperId}/file`)
      .then((url) => {
        if (!cancelled) setPdfUrl(url);
      })
      // Without this the promise rejects unhandled and the pane sits on
      // "Loading PDF…" forever, which is what a missing file looked like.
      .catch(() => {
        if (!cancelled) setPdfError("This paper's PDF is missing from storage.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper?.has_file, paperId]);

  // Record the visit once per mount, and jump to whatever page the link
  // asked for (a citation hit, or where you left off).
  useEffect(() => {
    if (!paperId || openedRef.current) return;
    openedRef.current = true;
    const page = Number(searchParams.get("page")) || undefined;
    request(`/api/papers/${paperId}/opened${page ? `?page=${page}` : ""}`, { method: "POST" });
    if (page) setTargetPage({ page, nonce: 1 });

    const ask = searchParams.get("ask");
    if (ask) setPendingQuestion({ text: ask, nonce: 1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);

  // Persist position as you read, debounced — one write per pause, not per pixel.
  function handlePageChange(page: number) {
    window.clearTimeout(pageTimer.current);
    pageTimer.current = window.setTimeout(() => {
      request(`/api/papers/${paperId}/opened?page=${page}`, { method: "POST" });
    }, 1200);
  }

  function refreshPaper() {
    queryClient.invalidateQueries({ queryKey: ["paper", paperId] });
  }

  function handleHighlightAsk(question: string) {
    setPendingQuestion((prev) => ({ text: question, nonce: (prev?.nonce ?? 0) + 1 }));
  }

  const { data: notes } = useQuery({
    queryKey: ["notes", paperId],
    queryFn: () => request<Note[]>(`/api/papers/${paperId}/notes`),
    enabled: !!paperId,
  });

  // Every saved highlight paints on the page it came from.
  const highlights = (notes ?? [])
    .filter((n) => n.quoted_text && n.page_number)
    .map((n) => ({ text: n.quoted_text!, page: n.page_number!, color: n.color }));

  const createHighlight = useMutation({
    mutationFn: ({ quote, page, color }: { quote: string; page: number; color: string }) =>
      request<Note>(`/api/papers/${paperId}/notes`, {
        method: "POST",
        body: JSON.stringify({ content: "", quoted_text: quote, page_number: page, color }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notes", paperId] }),
  });

  function handleSaveQuote(quote: string, page: number) {
    setPendingQuote((prev) => ({ text: quote, page, nonce: (prev?.nonce ?? 0) + 1 }));
  }

  function handleCitationClick(citation: Citation) {
    setHighlight(citation.text);
    setTargetPage((prev) => ({ page: citation.page_number, nonce: (prev?.nonce ?? 0) + 1 }));
  }

  // Panel resize. Pointer capture keeps the drag alive even when the cursor
  // outruns the handle or crosses into the PDF's iframe-like canvas area.
  function startResize(e: React.PointerEvent<HTMLDivElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragging.current = true;
  }

  function onResize(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    setPanelWidth(clampPanel(window.innerWidth - e.clientX));
  }

  function endResize(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    dragging.current = false;
    localStorage.setItem(PANEL_KEY, String(panelWidth));
  }

  //One call now parses, chunks and embeds — the reader shouldn't have to
  //know those are separate stages
  async function handlePrepare() {
    setPipelineBusy(true);
    try {
      await request(`/api/papers/${paperId}/prepare`, { method: "POST" });
      refreshPaper();
    } finally {
      setPipelineBusy(false);
    }
  }

  if (!paper) return null;

  // h-full works because <main> now has a definite height (flex-1 of h-screen),
  // so this fills it exactly and the two panes scroll independently inside.
  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border px-6 py-3 flex items-center justify-between bg-surface">
        <div className="flex flex-col gap-0.5 min-w-0">
          <Link to="/" className="text-xs text-text-muted hover:text-text-secondary w-fit">
            ← Library
          </Link>
          <h1 className="font-serif text-base text-text-primary truncate">{paper.title}</h1>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <FavoriteButton
            paperId={paper.id}
            isFavorite={paper.is_favorite}
            invalidate={[["paper", paper.id]]}
          />
          <AddToCollection paper={paper} invalidate={[["paper", paper.id]]} />
          <button
            onClick={() => setShowTags((open) => !open)}
            title="Tags"
            className={`text-xs px-2 py-1 rounded-md transition-colors ${
              showTags
                ? "bg-accent-info-soft text-accent-info"
                : "text-text-muted hover:text-text-primary hover:bg-bg-secondary"
            }`}
          >
            Tags{paper.tags.length > 0 && ` (${paper.tags.length})`}
          </button>
          <PaperActions paper={paper} />
        </div>

        {paper.has_file && <PipelineStatus paper={paper} busy={pipelineBusy} onRun={handlePrepare} />}
      </div>

      {showTags && (
        <div className="border-b border-border px-6 py-3 bg-surface">
          <div className="max-w-md">
            <TagInput paper={paper} />
          </div>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 bg-bg-secondary">
          {paper.has_file && pdfError ? (
            <div className="w-full h-full flex flex-col items-center justify-center gap-3 px-6 text-center">
              <p className="text-text-secondary text-sm">{pdfError}</p>
              <p className="text-text-muted text-xs max-w-sm">
                Re-upload it to restore the file. Processing and Q&A will need re-running afterwards.
              </p>
              <AttachPdfButton paperId={paper.id} hasFile={false} onAttached={refreshPaper} />
            </div>
          ) : paper.has_file ? (
            pdfUrl ? (
              <PdfViewer
                fileUrl={pdfUrl}
                title={paper.title}
                onAsk={handleHighlightAsk}
                onSaveQuote={handleSaveQuote}
                highlights={highlights}
                onHighlight={(quote, page, color) =>
                  createHighlight.mutate({ quote, page, color })
                }
                onPageChange={handlePageChange}
                targetPage={targetPage}
                highlightText={highlight}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <p className="text-text-muted text-sm">Loading PDF…</p>
              </div>
            )
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-3">
              <p className="text-text-secondary text-sm">No PDF attached to this paper yet.</p>
              <AttachPdfButton paperId={paper.id} hasFile={false} onAttached={refreshPaper} />
            </div>
          )}
        </div>

        {collapsed ? (
          <button
            onClick={() => toggleCollapsed(false)}
            title="Show assistant"
            className="shrink-0 w-9 border-l border-border bg-surface hover:bg-surface-hover text-text-muted hover:text-text-primary transition-colors flex items-start justify-center pt-4"
          >
            ‹
          </button>
        ) : (
          <>
            <div
              onPointerDown={startResize}
              onPointerMove={onResize}
              onPointerUp={endResize}
              onDoubleClick={() => setPanelWidth(380)}
              title="Drag to resize — double-click to reset"
              className="w-1.5 shrink-0 cursor-col-resize bg-border hover:bg-accent-primary/50 active:bg-accent-primary transition-colors"
            />

            <AIPanel
              paperId={paper.id}
              width={panelWidth}
              embeddingStatus={paper.embedding_status}
              pendingQuestion={pendingQuestion}
              pendingQuote={pendingQuote}
              onCollapse={() => toggleCollapsed(true)}
              onCitationClick={handleCitationClick}
            />
          </>
        )}
      </div>
    </div>
  );
}


//One control for the whole parse-and-embed pipeline: shows progress while it
//runs, the reason if it failed, and nothing at all once the paper is ready
function PipelineStatus({
  paper,
  busy,
  onRun,
}: {
  paper: Paper;
  busy: boolean;
  onRun: () => void;
}) {
  if (paper.embedding_status === "embedded") return null;

  const running =
    busy ||
    paper.processing_status === "processing" ||
    paper.embedding_status === "queued" ||
    paper.embedding_status === "embedding";

  if (running) {
    const label =
      paper.processing_status === "processing" ? "Reading the PDF…" : "Preparing for Q&A…";
    return <span className="text-xs text-text-muted shrink-0">{label}</span>;
  }

  const failed = paper.processing_status === "failed" || paper.embedding_status === "failed";

  return (
    <div className="flex items-center gap-2 min-w-0">
      {failed && paper.embedding_error && (
        <span
          title={paper.embedding_error}
          className="text-xs text-accent-ai bg-accent-ai-soft rounded-control px-2 py-1 truncate max-w-xs"
        >
          {paper.embedding_error}
        </span>
      )}
      <Button variant="ai" size="sm" onClick={onRun} disabled={busy}>
        {failed ? "Retry" : "Prepare for Q&A"}
      </Button>
    </div>
  );
}
