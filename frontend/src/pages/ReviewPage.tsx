import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
//GFM, or markdown tables arrive as literal pipe characters
import remarkGfm from "remark-gfm";
import { Button } from "../components/ui/Button";
import { PaperMatrix } from "../components/PaperMatrix";
import { useApiClient } from "../lib/api";
import type { LiteratureReview } from "../lib/types";

function downloadMarkdown(review: LiteratureReview) {
  //Client-side blob download; no backend endpoint needed just to save a file
  const titles = review.sources.map((s) => s.title);
  const themeTable = review.themes.length
    ? [
        "## Common themes",
        "",
        `| Theme | ${titles.join(" | ")} |`,
        `| --- | ${titles.map(() => "---").join(" | ")} |`,
        ...review.themes.map((t) => {
          const byId = Object.fromEntries(t.cells.map((c) => [c.paper_id, c.position]));
          // Escape pipes so a position containing one can't break the table.
          const cells = review.sources.map((s) => (byId[s.paper_id] ?? "—").replace(/\|/g, "\\|"));
          return `| ${t.theme} | ${cells.join(" | ")} |`;
        }),
        "",
      ]
    : [];

  const header = [
    "# Literature review",
    "",
    "## Sources",
    ...review.sources.map((s) => `- ${s.citation} — ${s.title}`),
    "",
    ...themeTable,
    "---",
    "",
  ].join("\n");

  const url = URL.createObjectURL(
    new Blob([header + review.markdown], { type: "text/markdown" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "literature-review.md";
  link.click();
  URL.revokeObjectURL(url);
}

export function ReviewPage() {
  const [searchParams] = useSearchParams();
  const { request } = useApiClient();
  const paperIds = (searchParams.get("papers") ?? "").split(",").filter(Boolean);

  const { data, isLoading, error } = useQuery({
    queryKey: ["review", paperIds],
    queryFn: () =>
      request<LiteratureReview>("/api/papers/literature-review", {
        method: "POST",
        body: JSON.stringify({ paper_ids: paperIds }),
      }),
    enabled: paperIds.length >= 2,
    retry: false,
  });

  return (
    <div className="flex flex-col">
      <header className="bg-accent-primary-soft/45 border-b border-accent-primary/10">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <Link to="/library" className="text-xs text-text-muted hover:text-text-secondary w-fit">
              ← Library
            </Link>
            <div className="h-1 w-12 rounded-full bg-accent-primary/60 mt-1" />
            <h1 className="font-serif text-3xl text-text-primary mt-1.5">Literature review</h1>
            <p className="text-text-secondary text-sm">
              Synthesised across {paperIds.length} papers
            </p>
          </div>
          {data && (
            <Button variant="secondary" size="sm" onClick={() => downloadMarkdown(data)}>
              Export as Markdown
            </Button>
          )}
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 w-full flex flex-col gap-8">
        {isLoading && <p className="text-text-muted">Reading the papers and writing…</p>}

        {error && (
          <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
            {error instanceof Error ? error.message : "Review generation failed"}
          </p>
        )}

        {data && (
          <>
            {data.themes.length > 0 && (
              <section className="flex flex-col gap-3">
                <h2 className="font-serif text-lg text-text-primary">Common themes</h2>
                <PaperMatrix
                  rowHeader="Theme"
                  columns={data.sources.map((s) => ({ paper_id: s.paper_id, title: s.title }))}
                  rows={data.themes.map((t) => ({
                    label: t.theme,
                    cells: Object.fromEntries(t.cells.map((c) => [c.paper_id, c.position])),
                  }))}
                />
              </section>
            )}

            {/* prose-answer is the AI panel's markdown styling; prose-review
                widens it for a full-page read rather than a 380px sidebar. */}
            <article className="prose-answer prose-review text-text-primary max-w-3xl">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.markdown}</ReactMarkdown>
            </article>

            <footer className="border-t border-border pt-4 flex flex-col gap-2">
              <p className="text-xs text-text-muted uppercase tracking-wide">Sources</p>
              <ul className="flex flex-col gap-1">
                {data.sources.map((source) => (
                  <li key={source.paper_id} className="text-sm">
                    <Link
                      to={`/papers/${source.paper_id}`}
                      className="text-accent-info hover:underline"
                    >
                      {source.citation}
                    </Link>
                    <span className="text-text-secondary"> — {source.title}</span>
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
