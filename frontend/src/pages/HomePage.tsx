import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Show } from "@clerk/react";
import { Card } from "../components/ui/Card";
import { LibraryStats } from "../components/library/LibraryStats";
import { RecentlyAdded } from "../components/library/RecentlyAdded";
import { RecentNotes } from "../components/library/RecentNotes";
import { GettingStarted } from "../components/library/GettingStarted";
import { useApiClient } from "../lib/api";
import type { Collection, Paper } from "../lib/types";

export function HomePage() {
  const { request } = useApiClient();

  const { data: papers } = useQuery({
    queryKey: ["papers", null],
    queryFn: () => request<Paper[]>("/api/papers"),
  });

  const { data: reading } = useQuery({
    queryKey: ["continue-reading"],
    queryFn: () => request<Paper[]>("/api/papers/continue-reading"),
  });

  const { data: collections } = useQuery({
    queryKey: ["collections"],
    queryFn: () => request<Collection[]>("/api/collections"),
  });

  const favorites = (papers ?? []).filter((p) => p.is_favorite);

  // Suggestions hang off whatever you were last reading; failing that, the
  // newest paper, so a fresh library still has somewhere to start.
  const focus = reading?.[0] ?? papers?.[0];

  const { data: questions } = useQuery({
    queryKey: ["suggested-questions", focus?.id],
    queryFn: () => request<string[]>(`/api/papers/${focus!.id}/suggested-questions`),
    enabled: !!focus && focus.embedding_status === "embedded",
  });

  return (
    <div className="flex flex-col">
      {/* Same quiet green band as the Library page, so the two read as one app. */}
      <header className="bg-accent-primary-soft/45 border-b border-accent-primary/10">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-1">
          <div className="h-1 w-12 rounded-full bg-accent-primary/60" />
          <h1 className="font-serif text-3xl text-text-primary mt-1.5">Your Library</h1>
          <Show when="signed-in">
            <p className="text-text-secondary text-sm">
              {papers
                ? `${papers.length} paper${papers.length === 1 ? "" : "s"}, ${
                    papers.filter((p) => p.embedding_status === "embedded").length
                  } ready for questions`
                : " "}
            </p>
          </Show>
          <Show when="signed-out">
            <p className="text-text-secondary text-sm">Sign in to see your library.</p>
          </Show>
        </div>
      </header>

      <Show when="signed-in">
        <div className="max-w-6xl mx-auto px-6 py-10 w-full flex flex-col lg:flex-row gap-8 items-start">
          <main className="flex-1 min-w-0 flex flex-col gap-10">
            <Section title="Continue reading" action={{ to: "/library", label: "All papers" }}>
              {reading && reading.length === 0 && (
                <p className="text-sm text-text-muted">
                  Nothing opened yet —{" "}
                  <Link to="/library" className="text-accent-info hover:underline">
                    pick a paper
                  </Link>{" "}
                  to get started.
                </p>
              )}
              {reading && reading.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                  {reading.map((paper) => (
                    <Link key={paper.id} to={`/papers/${paper.id}?page=${paper.last_page ?? 1}`}>
                      <Card interactive className="flex flex-col gap-2 h-full p-4">
                        <div className="h-1 w-8 rounded-full bg-accent-primary/60" />
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
            </Section>

            {favorites.length > 0 && (
              <Section title="Favorites" note={`${favorites.length} starred`}>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                  {favorites.map((paper) => (
                    <Link key={paper.id} to={`/papers/${paper.id}?page=${paper.last_page ?? 1}`}>
                      <Card
                        interactive
                        className="flex flex-col gap-2 h-full p-4 border-accent-primary/25"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="h-1 w-8 rounded-full bg-accent-primary/60" />
                          <StarIcon />
                        </div>
                        <h3 className="font-serif text-base leading-snug text-text-primary line-clamp-3">
                          {paper.title}
                        </h3>
                        <p className="text-xs text-text-muted mt-auto line-clamp-1">
                          {paper.authors.join(", ")}
                        </p>
                      </Card>
                    </Link>
                  ))}
                </div>
              </Section>
            )}

            {collections && collections.length > 0 && (
              <Section title="Collections" action={{ to: "/library", label: "Manage" }}>
                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-4">
                  {collections.map((collection) => (
                    // Deep-links straight into the Library filtered to this one
                    <Link key={collection.id} to={`/library?collection=${collection.id}`}>
                      <Card
                        interactive
                        className="p-4 flex flex-col gap-2 h-full bg-accent-primary-soft/40 border-accent-primary/20"
                      >
                        <ShelfIcon />
                        <h3 className="font-serif text-base leading-snug text-text-primary line-clamp-2">
                          {collection.name}
                        </h3>
                        <p className="text-xs text-accent-primary/80 mt-auto tabular-nums">
                          {collection.paper_count} paper
                          {collection.paper_count === 1 ? "" : "s"}
                        </p>
                      </Card>
                    </Link>
                  ))}
                </div>
              </Section>
            )}

            {focus && questions && questions.length > 0 && (
              <Section title="Questions to start with" note={`From “${focus.title}”`}>
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
              </Section>
            )}
          </main>

          <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-5">
            {papers && <LibraryStats papers={papers} />}
            {papers && <GettingStarted paperCount={papers.length} />}
            {papers && <RecentlyAdded papers={papers} />}
            <RecentNotes />
          </aside>
        </div>
      </Show>
    </div>
  );
}

function Section({
  title,
  note,
  action,
  children,
}: {
  title: string;
  note?: string;
  action?: { to: string; label: string };
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3 border-b border-border pb-2">
        <h2 className="font-serif text-lg text-text-primary">{title}</h2>
        {note && <span className="text-xs text-text-muted truncate">{note}</span>}
        {action && (
          <Link to={action.to} className="text-xs text-accent-info hover:underline shrink-0">
            {action.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

function StarIcon() {
  return (
    <svg viewBox="0 0 20 20" className="w-3.5 h-3.5 text-accent-primary shrink-0" fill="currentColor">
      <path d="M10 2.5l2.35 4.76 5.25.76-3.8 3.7.9 5.23L10 14.48l-4.7 2.47.9-5.23-3.8-3.7 5.25-.76z" />
    </svg>
  );
}

function ShelfIcon() {
  return (
    <svg
      viewBox="0 0 20 20"
      className="w-5 h-5 text-accent-primary/70"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <path d="M4 3.5v13M8 3.5v13M12.5 4l3.5 12.5" />
    </svg>
  );
}
