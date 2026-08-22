import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Show } from "@clerk/react";
import { Input } from "../components/ui/Input";
import { SearchResultCard } from "../components/SearchResultCard";
import { PaperTile, type PaperTileStatus } from "../components/ui/PaperTile";
import { AddPaperByDoi } from "../components/AddPaperByDoi";
import { useApiClient } from "../lib/api";
import { CollectionsBar } from "../components/CollectionsBar";
import { LibraryStats } from "../components/library/LibraryStats";
import { RecentlyAdded } from "../components/library/RecentlyAdded";
import { GettingStarted } from "../components/library/GettingStarted";
import type { Collection, Paper, SearchHit, Tag } from "../lib/types";

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
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const activeCollectionId = searchParams.get("collection");
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

  const { data: allPapers } = useQuery({
    queryKey: ["papers", null],
    queryFn: () => request<Paper[]>("/api/papers"),
  });

  const { data: collections } = useQuery({
    queryKey: ["collections"],
    queryFn: () => request<Collection[]>("/api/collections"),
  });

  const collectionFilter =
    collections?.find((c) => c.id === activeCollectionId) ??
    (activeCollectionId
      // Placeholder so the query can filter before the list arrives; the name
      // stays blank so the header falls back rather than flashing a stand-in.
      ? ({ id: activeCollectionId, name: "", created_at: "", paper_count: 0 } as Collection)
      : null);

  function setCollectionFilter(collection: Collection | null) {
    setSearchParams(collection ? { collection: collection.id } : {}, { replace: true });
  }

  const { data: tags } = useQuery({
    queryKey: ["tags"],
    queryFn: () => request<Tag[]>("/api/tags"),
  });

  // One source for the grid: a collection's papers, a tag-filtered list, or all.
  const { data: papers, isLoading } = useQuery({
    queryKey: collectionFilter
      ? ["collection-papers", collectionFilter.id]
      : ["papers", tagFilter],
    queryFn: () =>
      collectionFilter
        ? request<Paper[]>(`/api/collections/${collectionFilter.id}/papers`)
        : request<Paper[]>(`/api/papers${tagFilter ? `?tag=${tagFilter}` : ""}`),
  });

  function refreshPapers() {
    queryClient.invalidateQueries({ queryKey: ["papers"] });
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col gap-10">
      {/* Quiet green band rather than a hero: presence without shouting. */}
      <header className="-mx-6 px-6 py-7 bg-accent-primary-soft/45 border-y border-accent-primary/10">
        <div className="flex flex-col gap-1">
            <div className="h-1 w-12 rounded-full bg-accent-primary/60" />
            <h1 className="font-serif text-3xl text-text-primary mt-1.5">
              {collectionFilter?.name || "Your Library"}
            </h1>
            <p className="text-text-secondary text-sm">
              {papers
                ? `${papers.length} paper${papers.length === 1 ? "" : "s"}${
                    collectionFilter ? " in this collection" : ""
                  }`
                : "\u00A0"}
            </p>
        </div>
      </header>

      <Show when="signed-in">
        <CollectionsBar selected={collectionFilter} onSelect={setCollectionFilter} />
      </Show>

      <Show when="signed-in">
        {tags && tags.length > 0 && !collectionFilter && (
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              onClick={() => setTagFilter(null)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                tagFilter === null
                  ? "bg-accent-info text-white"
                  : "bg-accent-info-soft text-accent-info hover:bg-accent-info/20"
              }`}
            >
              All
            </button>
            {tags.map((tag) => (
              <button
                key={tag.id}
                onClick={() => setTagFilter(tag.id === tagFilter ? null : tag.id)}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                  tagFilter === tag.id
                    ? "bg-accent-info text-white"
                    : "bg-accent-info-soft text-accent-info hover:bg-accent-info/20"
                }`}
              >
                {tag.name}
              </button>
            ))}
          </div>
        )}
      </Show>

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
                  <SearchResultCard key={hit.paper_id} hit={hit} query={debounced} />
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

      {/* Grid leads; the sidebar supports it and drops below it on narrow
          viewports rather than squeezing the tiles. */}
      <div className="flex flex-col lg:flex-row gap-8 items-start">
      <main className="flex-1 min-w-0 flex flex-col gap-6">
      <Show when="signed-in">
        <section className={debounced ? "hidden" : undefined}>
          {isLoading && <p className="text-text-muted">Loading your library…</p>}

          {papers && papers.length === 0 && (
            <p className="text-text-muted">
              Nothing here yet — add a paper by DOI above to get started.
            </p>
          )}

          {papers && papers.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
              {papers.map((paper) => (
                <Link key={paper.id} to={`/papers/${paper.id}`}>
                  <PaperTile
                    paper={paper}
                    tags={paper.tags.map((t) => t.name)}
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
      </main>

      <Show when="signed-in">
        <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-5">
          {allPapers && <LibraryStats papers={allPapers} />}
          {allPapers && <GettingStarted paperCount={allPapers.length} />}
          {allPapers && <RecentlyAdded papers={allPapers} />}
        </aside>
      </Show>
      </div>
    </div>
  );
}
