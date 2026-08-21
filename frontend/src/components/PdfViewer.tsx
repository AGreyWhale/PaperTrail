import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// new URL(..., import.meta.url) is the Vite pattern that resolves to a
// hashed bundled worker URL. A bare path works in dev and breaks in build.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const ZOOM_STEPS = [0.5, 0.67, 0.8, 1, 1.15, 1.3, 1.5, 1.75, 2, 2.5, 3];
const SCALE_KEY = "papertrail:pdf-scale";
const PAGE_GAP = 16;
// Stand-in page height (roughly US Letter at 72dpi) used before page 1
// reports its real size. Without it every placeholder is 0px tall, they
// all land in the viewport at once, and nothing is actually lazy.
const ASSUMED_PAGE_HEIGHT = 792;

function normalize(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
}

//Which text items on a page make up the cited passage.
//pdf.js and pdfplumber extract text differently (spacing, hyphenation), so an
//exact match often misses. Falls back to progressively shorter prefixes, and
//matches one contiguous run rather than every fragment that happens to appear
//somewhere in the citation, which lit up unrelated words across the page.
function citedItemRange(items: { str: string }[], citation: string): [number, number] | null {
  const bounds: Array<[number, number]> = [];
  let haystack = "";
  for (const item of items) {
    const start = haystack.length;
    haystack += item.str.replace(/\s+/g, " ");
    bounds.push([start, haystack.length]);
  }

  const hay = haystack.toLowerCase();
  const needle = normalize(citation);

  let at = -1;
  let length = 0;
  for (const size of [needle.length, 120, 60, 30]) {
    if (size > needle.length) continue;
    at = hay.indexOf(needle.slice(0, size));
    if (at !== -1) {
      length = size;
      break;
    }
  }
  if (at === -1) return null;

  const end = at + length;
  const hits = bounds
    .map(([s, e], i) => (s < end && e > at ? i : -1))
    .filter((i) => i !== -1);
  return hits.length ? [hits[0]!, hits[hits.length - 1]!] : null;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function clampScale(value: number): number {
  return Math.min(3, Math.max(0.5, value));
}

function storedScale(): number {
  const raw = Number(localStorage.getItem(SCALE_KEY));
  return raw ? clampScale(raw) : 1;
}

interface SelectionState {
  text: string;
  top: number;
  left: number;
}

interface PageSize {
  width: number;
  height: number;
}

interface PdfViewerProps {
  fileUrl: string;
  title: string;
  onAsk: (question: string) => void;
  //Page the AI panel asked us to jump to, bumped by nonce so clicking the
  //same citation twice still scrolls
  targetPage?: { page: number; nonce: number };
  //Text of the clicked citation, tinted in the text layer so a source lands
  //on a paragraph rather than just "somewhere on page 4"
  highlightText?: string;
}

//Rendered through pdf.js rather than the browser's native viewer, because
//a native <iframe> PDF won't expose its text layer to page JS
export function PdfViewer({ fileUrl, title, onAsk, targetPage, highlightText }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [pageSize, setPageSize] = useState<PageSize | null>(null);
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  // `scale` is what pdf.js actually renders at; `preview` is a CSS transform
  // applied instantly while zooming. Re-rasterising every page on each wheel
  // tick is what makes naive zoom feel like it's chewing gum, so the real
  // re-render is debounced and the transform covers the gap.
  const [scale, setScale] = useState(storedScale);
  const [preview, setPreview] = useState<number | null>(null);
  const [fitting, setFitting] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const commitTimer = useRef<number | undefined>(undefined);
  // Pages stay mounted once rendered — remounting on scroll-back causes a
  // visible white flash and re-rasterisation.
  const [rendered, setRendered] = useState<Set<number>>(() => new Set([1]));
  const [citedRange, setCitedRange] = useState<[number, number] | null>(null);

  const commitScale = useCallback((next: number) => {
    const target = clampScale(next);
    setPreview(target);
    window.clearTimeout(commitTimer.current);
    commitTimer.current = window.setTimeout(() => {
      setScale(target);
      setPreview(null);
      localStorage.setItem(SCALE_KEY, String(target));
    }, 140);
  }, []);

  const effectiveScale = preview ?? scale;
  const highlightPage = targetPage?.page;

  const stepZoom = useCallback(
    (direction: 1 | -1) => {
      const from = preview ?? scale;
      const next =
        direction === 1
          ? ZOOM_STEPS.find((s) => s > from + 0.001)
          : [...ZOOM_STEPS].reverse().find((s) => s < from - 0.001);
      if (next) {
        setFitting(false);
        commitScale(next);
      }
    },
    [commitScale, preview, scale],
  );

  const fitWidth = useCallback(() => {
    const container = containerRef.current;
    if (!container || !pageSize) return;
    commitScale((container.clientWidth - 48) / pageSize.width);
  }, [commitScale, pageSize]);

  // Stay fitted when the sidebar is dragged, until an explicit zoom opts out.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !fitting) return;
    const observer = new ResizeObserver(() => fitWidth());
    observer.observe(container);
    return () => observer.disconnect();
  }, [fitting, fitWidth]);

  // Ctrl/Cmd + wheel. Registered manually because preventDefault needs a
  // non-passive listener, which React's onWheel doesn't give us.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    function onWheel(e: WheelEvent) {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      commitScale((preview ?? scale) * (e.deltaY < 0 ? 1.1 : 0.9));
    }
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => container.removeEventListener("wheel", onWheel);
  }, [commitScale, preview, scale]);

  // Ctrl/Cmd +, -, 0 — ignored while typing in the AI panel.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!e.ctrlKey && !e.metaKey) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "=" || e.key === "+") {
        e.preventDefault();
        stepZoom(1);
      } else if (e.key === "-") {
        e.preventDefault();
        stepZoom(-1);
      } else if (e.key === "0") {
        e.preventDefault();
        commitScale(1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [commitScale, stepZoom]);

  // Render a screen ahead of the viewport rather than all pages at once —
  // a 30-page paper was mounting 30 canvases before showing anything.
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !numPages) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const seen = entries
          .filter((e) => e.isIntersecting)
          .map((e) => Number((e.target as HTMLElement).dataset.page));
        if (!seen.length) return;
        setRendered((prev) => {
          const next = new Set(prev);
          seen.forEach((n) => next.add(n));
          return next.size === prev.size ? prev : next;
        });
      },
      { root: container, rootMargin: "100% 0px" },
    );
    pageRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [numPages]);

  // Page counter: whichever page's top edge is nearest the viewport top.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    function onScroll() {
      const top = container!.getBoundingClientRect().top;
      let best = 1;
      let bestGap = Infinity;
      pageRefs.current.forEach((el, page) => {
        const gap = Math.abs(el.getBoundingClientRect().top - top);
        if (gap < bestGap) {
          bestGap = gap;
          best = page;
        }
      });
      setCurrentPage(best);
    }
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, [numPages]);

  // Citation click in the AI panel.
  useEffect(() => {
    setCitedRange(null);
    if (!targetPage) return;
    const el = pageRefs.current.get(targetPage.page);
    if (!el) return;
    setRendered((prev) => new Set(prev).add(targetPage.page));
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [targetPage?.nonce, targetPage?.page]);

  function handleMouseUp() {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    const container = containerRef.current;
    if (!text || !sel || sel.rangeCount === 0 || !container) {
      setSelection(null);
      return;
    }

    const rect = sel.getRangeAt(0).getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    setSelection({
      text,
      top: rect.top - containerRect.top + container.scrollTop - 44,
      left: rect.left - containerRect.left + rect.width / 2,
    });
  }

  function handleAction(kind: "ask" | "explain" | "summarize") {
    if (!selection) return;
    const quoted = `"${selection.text}"`;
    const question =
      kind === "explain"
        ? `Explain the following passage in simple terms: ${quoted}`
        : kind === "summarize"
          ? `Summarize the following passage: ${quoted}`
          : `Regarding this passage: ${quoted} — what does this mean in context?`;

    onAsk(question);
    setSelection(null);
    window.getSelection()?.removeAllRanges();
  }

  return (
    <div className="relative w-full h-full flex flex-col">
      <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-1">
          <ZoomButton label="Zoom out" onClick={() => stepZoom(-1)} disabled={effectiveScale <= 0.5}>
            −
          </ZoomButton>
          <button
            onClick={() => {
              setFitting(false);
              commitScale(1);
            }}
            title="Reset zoom (Ctrl+0)"
            className="text-xs tabular-nums text-text-secondary hover:text-text-primary w-14 text-center py-1 rounded-md hover:bg-bg-secondary transition-colors"
          >
            {Math.round(effectiveScale * 100)}%
          </button>
          <ZoomButton label="Zoom in" onClick={() => stepZoom(1)} disabled={effectiveScale >= 3}>
            +
          </ZoomButton>
          <button
            onClick={() => {
              setFitting(true);
              fitWidth();
            }}
            className={`ml-1 text-xs px-2 py-1 rounded-md transition-colors ${
              fitting
                ? "bg-accent-primary-soft text-accent-primary"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
            }`}
          >
            Fit width
          </button>
        </div>

        <p className="text-xs text-text-muted tabular-nums">
          {numPages ? `Page ${currentPage} of ${numPages}` : " "}
        </p>
      </div>

      <div
        ref={containerRef}
        onMouseUp={handleMouseUp}
        className="relative flex-1 overflow-auto flex flex-col items-center py-6"
      >
        <div
          style={{
            transform: preview ? `scale(${preview / scale})` : undefined,
            transformOrigin: "top center",
            transition: "transform 120ms ease-out",
          }}
          className="flex flex-col items-center"
        >
          <Document
            file={fileUrl}
            onLoadSuccess={({ numPages }) => setNumPages(numPages)}
            loading={<p className="text-text-muted text-sm">Loading PDF…</p>}
            error={<p className="text-accent-ai text-sm">Couldn't load this PDF.</p>}
          >
            {Array.from({ length: numPages }, (_, i) => {
              const page = i + 1;
              return (
                <div
                  key={page}
                  data-page={page}
                  ref={(el) => {
                    if (el) pageRefs.current.set(page, el);
                    else pageRefs.current.delete(page);
                  }}
                  style={{
                    marginBottom: PAGE_GAP,
                    // Reserve the right height before a page renders, so
                    // scrolling ahead doesn't yank the position around.
                    minHeight: (pageSize?.height ?? ASSUMED_PAGE_HEIGHT) * scale,
                    width: pageSize ? pageSize.width * scale : undefined,
                  }}
                  className="bg-surface shadow-[0_2px_10px_rgba(43,38,33,0.12)]"
                >
                  {rendered.has(page) && (
                    <Page
                      pageNumber={page}
                      scale={scale}
                      onGetTextSuccess={({ items }) => {
                        if (page !== highlightPage || !highlightText) return;
                        setCitedRange(
                          citedItemRange(items as { str: string }[], highlightText),
                        );
                      }}
                      customTextRenderer={
                        page === highlightPage && citedRange
                          ? ({ itemIndex, str }) =>
                              itemIndex >= citedRange[0] && itemIndex <= citedRange[1]
                                ? `<mark class="pt-cite">${escapeHtml(str)}</mark>`
                                : escapeHtml(str)
                          : undefined
                      }
                      onLoadSuccess={(p) => {
                        if (page === 1 && !pageSize) {
                          setPageSize({ width: p.originalWidth, height: p.originalHeight });
                        }
                      }}
                    />
                  )}
                </div>
              );
            })}
          </Document>
        </div>

        {selection && (
          <div
            className="absolute z-10 flex items-center gap-0.5 bg-text-primary text-white rounded-control shadow-lg px-1 py-1 -translate-x-1/2"
            style={{ top: selection.top, left: selection.left }}
            // Stops this toolbar's own click from bubbling into handleMouseUp,
            // which would clear the selection before the action fires.
            onMouseDown={(e) => e.stopPropagation()}
          >
            <ToolbarAction onClick={() => handleAction("ask")}>Ask AI</ToolbarAction>
            <ToolbarAction onClick={() => handleAction("explain")}>Explain</ToolbarAction>
            <ToolbarAction onClick={() => handleAction("summarize")}>Summarize</ToolbarAction>
          </div>
        )}
      </div>

      <p className="sr-only">{title}</p>
    </div>
  );
}

function ZoomButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className="w-7 h-7 flex items-center justify-center rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-secondary disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
    >
      {children}
    </button>
  );
}

function ToolbarAction({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="text-xs px-2.5 py-1.5 rounded-md hover:bg-white/15 transition-colors"
    >
      {children}
    </button>
  );
}
