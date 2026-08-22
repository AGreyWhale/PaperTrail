import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PaperMatrix } from "../components/PaperMatrix";
import { useApiClient } from "../lib/api";
import type { Comparison } from "../lib/types";

const DIMENSIONS = [
  ["datasets", "Datasets"],
  ["architecture", "Architecture"],
  ["evaluation_metrics", "Evaluation metrics"],
  ["strengths", "Strengths"],
  ["weaknesses", "Weaknesses"],
  ["future_work", "Future work"],
] as const;

export function ComparePage() {
  const [searchParams] = useSearchParams();
  const { request } = useApiClient();
  const paperIds = (searchParams.get("papers") ?? "").split(",").filter(Boolean);

  const { data, isLoading, error } = useQuery({
    queryKey: ["compare", paperIds],
    queryFn: () =>
      request<Comparison>("/api/papers/compare", {
        method: "POST",
        body: JSON.stringify({ paper_ids: paperIds }),
      }),
    enabled: paperIds.length >= 2,
    retry: false,
  });

  return (
    <div className="flex flex-col">
      <header className="bg-accent-primary-soft/45 border-b border-accent-primary/10">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-1">
          <Link to="/library" className="text-xs text-text-muted hover:text-text-secondary w-fit">
            ← Library
          </Link>
          <div className="h-1 w-12 rounded-full bg-accent-primary/60 mt-1" />
          <h1 className="font-serif text-3xl text-text-primary mt-1.5">Compare papers</h1>
          <p className="text-text-secondary text-sm">
            {paperIds.length} papers, grounded only in retrieved excerpts
          </p>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8 w-full">
        {isLoading && <p className="text-text-muted">Reading both papers and comparing…</p>}

        {error && (
          <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
            {error instanceof Error ? error.message : "Comparison failed"}
          </p>
        )}

        {data && (
          <PaperMatrix
            rowHeader="Dimension"
            columns={data.papers.map((p) => ({ paper_id: p.paper_id, title: p.title }))}
            rows={DIMENSIONS.map(([key, label]) => ({
              label,
              cells: Object.fromEntries(data.papers.map((p) => [p.paper_id, p[key]])),
            }))}
          />
        )}
      </div>
    </div>
  );
}
