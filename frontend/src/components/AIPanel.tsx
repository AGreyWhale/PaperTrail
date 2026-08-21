import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { useApiClient } from "../lib/api";
import type { AnswerEntry, Citation } from "../lib/types";

const TEXT_KEY = "papertrail:answer-text-size";
const TEXT_SIZES = [13, 15, 17];

interface AIPanelProps {
  paperId: string;
  width: number;
  embeddingStatus: string;
  onCollapse: () => void;
  onCitationClick?: (citation: Citation) => void;
  //Set by the PDF toolbar. nonce bumps even for identical text, so
  //highlighting the same passage twice still re-asks
  pendingQuestion?: { text: string; nonce: number };
}

//Assistant sidebar in the reading view. Documentation-styled, not a chat
export function AIPanel({
  paperId,
  width,
  embeddingStatus,
  onCollapse,
  onCitationClick,
  pendingQuestion,
}: AIPanelProps) {
  const { requestStream } = useApiClient();
  const [question, setQuestion] = useState("");
  const [entries, setEntries] = useState<AnswerEntry[]>([]);
  const [textSize, setTextSize] = useState(() => Number(localStorage.getItem(TEXT_KEY)) || 15);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const ready = embeddingStatus === "embedded";
  const busy = entries.some((e) => e.streaming);

  function cycleTextSize() {
    const next = TEXT_SIZES[(TEXT_SIZES.indexOf(textSize) + 1) % TEXT_SIZES.length] ?? 15;
    setTextSize(next);
    localStorage.setItem(TEXT_KEY, String(next));
  }

  function patchEntry(id: string, patch: Partial<AnswerEntry>) {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  }

  const askWithText = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !ready) return;

      const id = crypto.randomUUID();
      // Chronological, oldest at top — the scroll-to-bottom effect keeps the
      // live answer in view as it streams.
      setEntries((prev) => [
        ...prev,
        { id, question: trimmed, answer: "", citations: [], streaming: true },
      ]);
      setQuestion("");

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        let answer = "";
        await requestStream(
          `/api/papers/${paperId}/ask/stream`,
          { question: trimmed },
          (event) => {
            if (event.type === "citations") {
              patchEntry(id, { citations: event.citations });
            } else if (event.type === "token") {
              answer += event.text;
              patchEntry(id, { answer });
            } else if (event.type === "error") {
              patchEntry(id, { error: event.detail, streaming: false });
            }
          },
          controller.signal,
        );
      } catch (err) {
        if (!controller.signal.aborted) {
          patchEntry(id, { error: err instanceof Error ? err.message : "Something went wrong" });
        }
      } finally {
        patchEntry(id, { streaming: false });
      }
    },
    [paperId, ready, requestStream],
  );

  // Fires when a toolbar action is picked in the PDF: fill the input and ask.
  useEffect(() => {
    if (!pendingQuestion) return;
    askWithText(pendingQuestion.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion?.nonce]);

  // "/" focuses the ask box, the shortcut people reflexively try.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "/" || e.ctrlKey || e.metaKey) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      e.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Follow the answer as it streams, but only while the reader is already at
  // the bottom — otherwise scrolling up to reread gets yanked back down.
  const lastEntry = entries[entries.length - 1];
  useEffect(() => {
    const box = scrollRef.current;
    if (!box) return;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 120;
    if (atBottom) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [lastEntry?.answer, entries.length]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return (
    <aside
      style={{ width }}
      className="shrink-0 border-l border-border bg-surface flex flex-col h-full"
    >
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-2">
        <h2 className="font-serif text-base text-text-primary truncate">Ask about this paper</h2>
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            onClick={cycleTextSize}
            title="Change answer text size"
            className="text-xs text-text-muted hover:text-text-primary px-2 py-1 rounded-md hover:bg-bg-secondary transition-colors"
          >
            A<span style={{ fontSize: "1.15em" }}>A</span>
          </button>
          <button
            onClick={onCollapse}
            title="Hide panel"
            aria-label="Hide panel"
            className="text-text-muted hover:text-text-primary px-2 py-1 rounded-md hover:bg-bg-secondary transition-colors"
          >
            ›
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-5">
        {!ready && (
          <p className="text-sm text-text-muted">
            {embeddingStatus === "not_embedded" && "This paper hasn't been embedded yet."}
            {embeddingStatus === "queued" && "Embedding is queued — check back shortly."}
            {embeddingStatus === "embedding" && "Embedding in progress…"}
            {embeddingStatus === "failed" && "Embedding failed for this paper."}
          </p>
        )}

        {ready && entries.length === 0 && (
          <p className="text-sm text-text-muted">
            Ask a question below, or highlight a passage in the PDF and choose Ask, Explain, or
            Summarize.
          </p>
        )}

        {entries.map((entry) => (
          <AnswerBlock
            key={entry.id}
            entry={entry}
            textSize={textSize}
            onCitationClick={onCitationClick}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-5 py-4 border-t border-border flex flex-col gap-2">
        <Input
          ref={inputRef}
          placeholder={ready ? "Ask a question…  ( / )" : "Not ready yet"}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && askWithText(question)}
          disabled={!ready || busy}
        />
        <Button
          variant="ai"
          onClick={() => askWithText(question)}
          disabled={!ready || busy || !question.trim()}
        >
          {busy ? "Thinking…" : "Ask"}
        </Button>
      </div>
    </aside>
  );
}

function AnswerBlock({
  entry,
  textSize,
  onCitationClick,
}: {
  entry: AnswerEntry;
  textSize: number;
  onCitationClick?: (citation: Citation) => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    await navigator.clipboard.writeText(entry.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex flex-col gap-2 pb-5 border-b border-border last:border-b-0 last:pb-0">
      <p className="text-xs text-text-muted leading-snug">{entry.question}</p>

      {entry.error ? (
        <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
          {entry.error}
        </p>
      ) : (
        <>
          <div style={{ fontSize: textSize, lineHeight: 1.65 }} className="prose-answer text-text-primary">
            <ReactMarkdown>{entry.answer}</ReactMarkdown>
            {entry.streaming && <span className="inline-block w-1.5 h-4 bg-accent-ai/60 align-text-bottom animate-pulse" />}
          </div>

          {!entry.streaming && entry.answer && (
            <button
              onClick={copyAnswer}
              className="text-xs text-text-muted hover:text-text-primary w-fit transition-colors"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          )}

          {entry.citations.length > 0 && !entry.streaming && (
            <div className="flex flex-col gap-1.5 pt-1">
              <p className="text-xs text-text-muted uppercase tracking-wide">Sources</p>
              <div className="flex flex-wrap gap-1.5">
                {entry.citations.map((citation) => (
                  <button
                    key={citation.chunk_id}
                    title={citation.text}
                    onClick={() => onCitationClick?.(citation)}
                    className="text-xs px-2 py-0.5 rounded-full bg-accent-info-soft text-accent-info hover:bg-accent-info hover:text-white transition-colors"
                  >
                    p. {citation.page_number}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
