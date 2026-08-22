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

const TRANSIENT_STATUSES = new Set(["queued", "embedding"]);

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
      const status = (query.state.data as Paper | undefined)?.embedding_status;
      return status && TRANSIENT_STATUSES.has(status) ? 2000 : false;
    },
  });

  useEffect(() => {
    if (!paper?.has_file || !paperId) {
      setPdfUrl(null);
      return;
    }
    let cancelled = false;
    requestBlobUrl(`/api/papers/${paperId}/file`).then((url) => {
      if (!cancelled) setPdfUrl(url);
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

  async function handleProcess() {
    setPipelineBusy(true);
    try {
      await request(`/api/papers/${paperId}/process`, { method: "POST" });
      refreshPaper();
    } finally {
      setPipelineBusy(false);
    }
  }

  async function handleEmbed() {
    setPipelineBusy(true);
    try {
      await request(`/api/papers/${paperId}/embed`, { method: "POST" });
      refreshPaper();
    } finally {
      setPipelineBusy(false);
    }
  }

  if (!paper) return null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
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

        {paper.has_file && paper.processing_status === "unprocessed" && (
          <Button variant="secondary" size="sm" onClick={handleProcess} disabled={pipelineBusy}>
            {pipelineBusy ? "Processing…" : "Process this paper"}
          </Button>
        )}
        {paper.processing_status === "processed" && paper.embedding_status === "not_embedded" && (
          <Button variant="ai" size="sm" onClick={handleEmbed} disabled={pipelineBusy}>
            {pipelineBusy ? "Starting…" : "Prepare for Q&A"}
          </Button>
        )}
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
          {paper.has_file ? (
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
