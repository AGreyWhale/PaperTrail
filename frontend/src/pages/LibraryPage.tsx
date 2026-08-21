import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Show } from "@clerk/react";
import { Input } from "../components/ui/Input";
import { SearchResultCard } from "../components/SearchResultCard";
import { PaperTile, type PaperTileStatus } from "../components/ui/PaperTile";
import { AddPaperByDoi } from "../components/AddPaperByDoi";
import { useApiClient } from "../lib/api";
import type { Paper, SearchHit } from "../lib/types";

//Collapses the two backend status fields into one badge for the tile
function deriveStatus(paper: Paper): PaperTileStatus {
  if (!paper.has_file) return "needs_file";
  if (paper.processing_status === "failed" || paper.embedding_status === "failed") return "failed";
  if (paper.processing_status !== "processed") return "processing";
  if (paper.embedding_status === "embedded") return "ready";
  return "embedding";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function LibraryPage() {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  // Each keystroke would otherwise embed the query and hit the vector store.
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  const { data: hits, isFetching: searching } = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => request<SearchHit[]>(`/api/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length > 0,
  });

  const { data: papers, isLoading } = useQuery({
    queryKey: ["papers"],
    queryFn: () => request<Paper[]>("/api/papers"),
  });

  function refreshPapers() {
    queryClient.invalidateQueries({ queryKey: ["papers"] });
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col gap-10">
      <header className="flex flex-col gap-1">
        <h1 className="font-serif text-3xl text-text-primary">Your Library</h1>
        <p className="text-text-secondary">
          {papers ? `${papers.length} paper${papers.length === 1 ? "" : "s"}` : "\u00A0"}
        </p>
      </header>

      <Show when="signed-in">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search across every paper you've embedded…"
          className="max-w-2xl"
        />
      </Show>

      <Show when="signed-in">
        {debounced ? (
          <section className="flex flex-col gap-3">
            {searching && !hits && <p className="text-text-muted">Searching…</p>}
            {hits && hits.length === 0 && (
              <p className="text-text-muted">
                Nothing matched “{debounced}”. Only embedded papers are searchable.
              </p>
            )}
            {hits && hits.length > 0 && (
              <div className="flex flex-col gap-3 max-w-3xl">
                {hits.map((hit) => (
                  <SearchResultCard key={hit.paper_id} hit={hit} />
                ))}
              </div>
            )}
          </section>
        ) : (
          <section className="flex flex-col gap-3 max-w-xl">
            <h2 className="font-serif text-lg text-text-primary">Add a paper</h2>
            <AddPaperByDoi onPaperAdded={refreshPapers} />
          </section>
        )}
      </Show>

      <Show when="signed-out">
        <p className="text-text-secondary">Sign in to see your library.</p>
      </Show>

      <Show when="signed-in">
        <section className={debounced ? "hidden" : undefined}>
          {isLoading && <p className="text-text-muted">Loading your library…</p>}

          {papers && papers.length === 0 && (
            <p className="text-text-muted">
              Nothing here yet — add a paper by DOI above to get started.
            </p>
          )}

          {papers && papers.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {papers.map((paper) => (
                <Link key={paper.id} to={`/papers/${paper.id}`}>
                  <PaperTile
                    title={paper.title}
                    authors={paper.authors}
                    venue={paper.venue}
                    year={paper.year}
                    addedDate={formatDate(paper.created_at)}
                    status={deriveStatus(paper)}
                  />
                </Link>
              ))}
            </div>
          )}
        </section>
      </Show>
    </div>
  );
}
