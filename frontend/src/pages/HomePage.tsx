import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Show } from "@clerk/react";
import { Card } from "../components/ui/Card";
import { useApiClient } from "../lib/api";
import type { Paper } from "../lib/types";

function readyCount(papers: Paper[]): number {
  return papers.filter((p) => p.embedding_status === "embedded").length;
}

export function HomePage() {
  const { request } = useApiClient();

  const { data: papers } = useQuery({
    queryKey: ["papers"],
    queryFn: () => request<Paper[]>("/api/papers"),
  });

  const { data: reading } = useQuery({
    queryKey: ["continue-reading"],
    queryFn: () => request<Paper[]>("/api/papers/continue-reading"),
  });

  // Suggestions hang off whatever you were last reading; failing that, the
  // newest paper, so a fresh library still has somewhere to start.
  const focus = reading?.[0] ?? papers?.[0];

  const { data: questions } = useQuery({
    queryKey: ["suggested-questions", focus?.id],
    queryFn: () => request<string[]>(`/api/papers/${focus!.id}/suggested-questions`),
    enabled: !!focus && focus.embedding_status === "embedded",
  });

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col gap-10">
      <Show when="signed-out">
        <div className="flex flex-col gap-2">
          <h1 className="font-serif text-3xl text-text-primary">PaperTrail</h1>
          <p className="text-text-secondary">Sign in to see your library.</p>
        </div>
      </Show>

      <Show when="signed-in">
        <header className="flex flex-col gap-1">
          <h1 className="font-serif text-3xl text-text-primary">Your Library</h1>
          <p className="text-text-secondary">
            {papers
              ? `${papers.length} paper${papers.length === 1 ? "" : "s"}, ${readyCount(papers)} ready for questions`
              : " "}
          </p>
        </header>

        <section className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h2 className="font-serif text-lg text-text-primary">Continue reading</h2>
            <Link to="/library" className="text-xs text-accent-info hover:underline">
              All papers →
            </Link>
          </div>

          {reading && reading.length === 0 && (
            <p className="text-sm text-text-muted">
              Nothing opened yet — <Link to="/library" className="text-accent-info hover:underline">pick a paper</Link> to get started.
            </p>
          )}

          {reading && reading.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {reading.map((paper) => (
                <Link key={paper.id} to={`/papers/${paper.id}?page=${paper.last_page ?? 1}`}>
                  <Card interactive className="flex flex-col gap-2 h-full">
                    <h3 className="font-serif text-base leading-snug text-text-primary line-clamp-3">
                      {paper.title}
                    </h3>
                    <p className="text-xs text-text-muted mt-auto">
                      {paper.last_page ? `Page ${paper.last_page}` : "Not started"}
                    </p>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>

        {focus && questions && questions.length > 0 && (
          <section className="flex flex-col gap-3">
            <h2 className="font-serif text-lg text-text-primary">Questions to start with</h2>
            <p className="text-xs text-text-muted -mt-2">From “{focus.title}”</p>
            <div className="flex flex-col gap-2 items-start">
              {questions.map((question) => (
                <Link
                  key={question}
                  to={`/papers/${focus.id}?ask=${encodeURIComponent(question)}`}
                  className="text-sm text-left px-3.5 py-2.5 rounded-control border border-border bg-surface hover:border-accent-ai/50 hover:bg-surface-hover text-text-primary transition-colors w-full max-w-2xl"
                >
                  {question}
                </Link>
              ))}
            </div>
          </section>
        )}
      </Show>
    </div>
  );
}
