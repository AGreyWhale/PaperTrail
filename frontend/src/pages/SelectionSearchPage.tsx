import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Input } from "../components/ui/Input";
import { SearchResultCard } from "../components/SearchResultCard";
import { useApiClient } from "../lib/api";
import type { Paper, SearchHit } from "../lib/types";

export function SelectionSearchPage() {
  const [searchParams] = useSearchParams();
  const { request } = useApiClient();
  const paperIds = (searchParams.get("papers") ?? "").split(",").filter(Boolean);

  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  // Each keystroke would otherwise embed the query and hit the database.
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Titles for the scope line, so it's obvious what is being searched.
  const { data: papers } = useQuery({
    queryKey: ["papers", null],
    queryFn: () => request<Paper[]>("/api/papers"),
  });
  const scoped = (papers ?? []).filter((p) => paperIds.includes(p.id));

  const { data: hits, isFetching } = useQuery({
    queryKey: ["selection-search", paperIds, debounced],
    queryFn: () =>
      request<SearchHit[]>("/api/search/selection", {
        method: "POST",
        body: JSON.stringify({ paper_ids: paperIds, q: debounced }),
      }),
    enabled: debounced.length > 0 && paperIds.length > 0,
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
          <h1 className="font-serif text-3xl text-text-primary mt-1.5">Search these papers</h1>
          <p className="text-text-secondary text-sm">
            {scoped.length > 0
              ? scoped.map((p) => p.title).join(" · ")
              : `${paperIds.length} selected`}
          </p>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-8 w-full flex flex-col gap-5">
        <Input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search within the selected papers…"
        />

        {isFetching && !hits && <p className="text-text-muted">Searching…</p>}

        {debounced && hits && hits.length === 0 && (
          <p className="text-text-muted">
            Nothing matched “{debounced}” in these papers. Only embedded papers are searchable.
          </p>
        )}

        {hits && hits.length > 0 && (
          <div className="flex flex-col gap-3">
            {hits.map((hit) => (
              <SearchResultCard key={hit.paper_id} hit={hit} query={debounced} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
