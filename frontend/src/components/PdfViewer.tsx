import { useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// new URL(..., import.meta.url) is the Vite pattern that resolves to a
// hashed bundled worker URL. A bare path works in dev and breaks in build.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

interface SelectionState {
  text: string;
  top: number;
  left: number;
}

interface PdfViewerProps {
  fileUrl: string;
  title: string;
  onAsk: (question: string) => void;
}

//Rendered through pdf.js rather than the browser's native viewer, because
//a native <iframe> PDF won't expose its text layer to page JS
export function PdfViewer({ fileUrl, title, onAsk }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  function handleMouseUp() {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    const container = containerRef.current;
    if (!text || !sel || sel.rangeCount === 0 || !container) {
      setSelection(null);
      return;
    }

    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
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
    <div
      ref={containerRef}
      onMouseUp={handleMouseUp}
      className="relative w-full h-full overflow-y-auto flex flex-col items-center gap-4 py-6"
    >
      <Document
        file={fileUrl}
        onLoadSuccess={({ numPages }) => setNumPages(numPages)}
        loading={<p className="text-text-muted text-sm">Loading PDF…</p>}
        error={<p className="text-accent-ai text-sm">Couldn't load this PDF.</p>}
      >
        {Array.from({ length: numPages }, (_, i) => (
          <Page
            key={i}
            pageNumber={i + 1}
            width={680}
            className="shadow-[0_2px_10px_rgba(43,38,33,0.12)] mb-4"
          />
        ))}
      </Document>

      {selection && (
        <div
          className="absolute z-10 flex items-center gap-0.5 bg-text-primary text-white rounded-control shadow-lg px-1 py-1 -translate-x-1/2"
          style={{ top: selection.top, left: selection.left }}
          // Stops this toolbar's own click from bubbling into handleMouseUp,
          // which would clear the selection before the action fires.
          onMouseDown={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => handleAction("ask")}
            className="text-xs px-2.5 py-1.5 rounded-md hover:bg-white/15 transition-colors"
          >
            Ask AI
          </button>
          <button
            onClick={() => handleAction("explain")}
            className="text-xs px-2.5 py-1.5 rounded-md hover:bg-white/15 transition-colors"
          >
            Explain
          </button>
          <button
            onClick={() => handleAction("summarize")}
            className="text-xs px-2.5 py-1.5 rounded-md hover:bg-white/15 transition-colors"
          >
            Summarize
          </button>
        </div>
      )}

      <p className="sr-only">{title}</p>
    </div>
  );
}
