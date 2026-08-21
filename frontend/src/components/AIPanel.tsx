import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { useApiClient } from "../lib/api";
import type { AskAnswer } from "../lib/types";

interface AIPanelProps {
  paperId: string;
  embeddingStatus: string;
  //Set by the PDF toolbar. nonce bumps even for identical text, so
  //highlighting the same passage twice still re-asks
  pendingQuestion?: { text: string; nonce: number };
}

//Assistant sidebar in the reading view. Documentation-styled, not a chat
export function AIPanel({ paperId, embeddingStatus, pendingQuestion }: AIPanelProps) {
  const { request } = useApiClient();
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskAnswer | null>(null);

  const ready = embeddingStatus === "embedded";

  async function askWithText(text: string) {
    if (!text.trim() || !ready) return;
    setAsking(true);
    setError(null);
    try {
      const answer = await request<AskAnswer>(`/api/papers/${paperId}/ask`, {
        method: "POST",
        body: JSON.stringify({ question: text.trim() }),
      });
      setResult(answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setAsking(false);
    }
  }

  // Fires when a toolbar action is picked in the PDF: fill the input and ask.
  useEffect(() => {
    if (!pendingQuestion) return;
    setQuestion(pendingQuestion.text);
    askWithText(pendingQuestion.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion?.nonce]);

  return (
    <aside className="w-[380px] shrink-0 border-l border-border bg-surface flex flex-col h-full">
      <div className="px-5 py-4 border-b border-border">
        <h2 className="font-serif text-base text-text-primary">Ask about this paper</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
        {!ready && (
          <p className="text-sm text-text-muted">
            {embeddingStatus === "not_embedded" && "This paper hasn't been embedded yet."}
            {embeddingStatus === "queued" && "Embedding is queued — check back shortly."}
            {embeddingStatus === "embedding" && "Embedding in progress…"}
            {embeddingStatus === "failed" && "Embedding failed for this paper."}
          </p>
        )}

        {asking && <p className="text-sm text-text-muted">Thinking…</p>}

        {error && (
          <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
            {error}
          </p>
        )}

        {result && !asking && (
          <div className="flex flex-col gap-3">
            <div className="prose-answer text-sm text-text-primary leading-relaxed">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>

            {result.citations.length > 0 && (
              <div className="flex flex-col gap-1.5 pt-2 border-t border-border">
                <p className="text-xs text-text-muted uppercase tracking-wide">Sources</p>
                <div className="flex flex-wrap gap-1.5">
                  {result.citations.map((citation) => (
                    <span
                      key={citation.chunk_id}
                      title={citation.text}
                      className="text-xs px-2 py-0.5 rounded-full bg-accent-info-soft text-accent-info cursor-default"
                    >
                      p. {citation.page_number}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="px-5 py-4 border-t border-border flex flex-col gap-2">
        <Input
          placeholder={ready ? "Ask a question…" : "Not ready yet"}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && askWithText(question)}
          disabled={!ready || asking}
        />
        <Button
          variant="ai"
          onClick={() => askWithText(question)}
          disabled={!ready || asking || !question.trim()}
        >
          {asking ? "Thinking…" : "Ask"}
        </Button>
      </div>
    </aside>
  );
}
