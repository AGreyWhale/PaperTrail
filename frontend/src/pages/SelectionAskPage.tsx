import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
//GFM, or markdown tables arrive as literal pipe characters
import remarkGfm from "remark-gfm";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useApiClient } from "../lib/api";
import type { MultiAskAnswer, MultiCitation, Paper } from "../lib/types";

//Several excerpts can come from one paper; the reader wants one row per paper
function byPaper(citations: MultiCitation[]) {
  const grouped = new Map<string, { citation: MultiCitation; pages: number[] }>();
  for (const c of citations) {
    const existing = grouped.get(c.paper_id);
    if (existing) existing.pages.push(c.page_number);
    else grouped.set(c.paper_id, { citation: c, pages: [c.page_number] });
  }
  return [...grouped.values()];
}

export function SelectionAskPage() {
  const [searchParams] = useSearchParams();
  const { request } = useApiClient();
  const paperIds = (searchParams.get("papers") ?? "").split(",").filter(Boolean);
  const [question, setQuestion] = useState("");

  const { data: papers } = useQuery({
    queryKey: ["papers", null],
    queryFn: () => request<Paper[]>("/api/papers"),
  });
  const scoped = (papers ?? []).filter((p) => paperIds.includes(p.id));

  const ask = useMutation({
    mutationFn: (q: string) =>
      request<MultiAskAnswer>("/api/papers/ask-multiple", {
        method: "POST",
        body: JSON.stringify({ paper_ids: paperIds, question: q }),
      }),
  });

  return (
    <div className="flex flex-col">
      <header className="bg-accent-primary-soft/45 border-b border-accent-primary/10">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-1">
          <Link to="/library" className="text-xs text-text-muted hover:text-text-secondary w-fit">
            ← Library
          </Link>
          <div className="h-1 w-12 rounded-full bg-accent-primary/60 mt-1" />
          <h1 className="font-serif text-3xl text-text-primary mt-1.5">Ask across papers</h1>
          <p className="text-text-secondary text-sm">
            {scoped.length > 0
              ? scoped.map((p) => p.title).join(" · ")
              : `${paperIds.length} selected`}
          </p>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-8 w-full flex flex-col gap-6">
        <div className="flex gap-2">
          <Input
            autoFocus
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && question.trim() && ask.mutate(question.trim())}
            placeholder="Ask a question about these papers together…"
          />
          <Button
            variant="ai"
            onClick={() => ask.mutate(question.trim())}
            disabled={!question.trim() || ask.isPending}
          >
            {ask.isPending ? "Thinking…" : "Ask"}
          </Button>
        </div>

        {ask.isError && (
          <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
            {ask.error instanceof Error ? ask.error.message : "Something went wrong"}
          </p>
        )}

        {ask.data && (
          <>
            <article className="prose-answer prose-review text-text-primary">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{ask.data.answer}</ReactMarkdown>
            </article>

            <footer className="border-t border-border pt-4 flex flex-col gap-2">
              <p className="text-xs text-text-muted uppercase tracking-wide">Sources</p>
              <ul className="flex flex-col gap-1">
                {byPaper(ask.data.citations).map(({ citation, pages }) => (
                  <li key={citation.paper_id} className="text-sm">
                    <Link
                      to={`/papers/${citation.paper_id}?page=${pages[0]}`}
                      className="text-accent-info hover:underline"
                    >
                      {citation.citation}
                    </Link>
                    <span className="text-text-secondary">
                      {" "}
                      — {citation.paper_title}{" "}
                      <span className="text-text-muted">
                        (p. {[...new Set(pages)].sort((a, b) => a - b).join(", ")})
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
