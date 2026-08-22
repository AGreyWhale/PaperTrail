import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "../lib/api";
import type { Collection, Paper } from "../lib/types";

interface AddToCollectionProps {
  paper: Paper;
  invalidate?: unknown[][];
}

//Checklist dropdown: a paper can sit in several collections, so this toggles
//membership rather than picking one
export function AddToCollection({ paper, invalidate = [] }: AddToCollectionProps) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const { data: collections } = useQuery({
    queryKey: ["collections"],
    queryFn: () => request<Collection[]>("/api/collections"),
    enabled: open,
  });

  const member = new Set(paper.collections.map((c) => c.id));

  const toggle = useMutation({
    mutationFn: ({ id, isMember }: { id: string; isMember: boolean }) =>
      request(`/api/collections/${id}/papers/${paper.id}`, {
        method: isMember ? "DELETE" : "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["collection-papers"] });
      invalidate.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
    },
  });

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        onClick={(e) => {
          // Tiles are wrapped in a <Link>; don't navigate on a menu click.
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        title="Add to collection"
        className={`text-xs px-2 py-1 rounded-md transition-colors ${
          paper.collections.length > 0
            ? "bg-accent-primary-soft text-accent-primary"
            : "text-text-muted hover:text-text-primary hover:bg-bg-secondary"
        }`}
      >
        Collections{paper.collections.length > 0 && ` (${paper.collections.length})`}
      </button>

      {open && (
        <div
          onClick={(e) => e.preventDefault()}
          className="absolute right-0 top-full mt-1 z-20 w-56 rounded-control border border-border bg-surface shadow-lg py-1"
        >
          {collections && collections.length === 0 && (
            <p className="text-xs text-text-muted px-3 py-2">
              No collections yet — create one on the Library page.
            </p>
          )}
          {collections?.map((collection) => {
            const isMember = member.has(collection.id);
            return (
              <button
                key={collection.id}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  toggle.mutate({ id: collection.id, isMember });
                }}
                className="w-full text-left text-sm px-3 py-1.5 flex items-center gap-2 hover:bg-surface-hover transition-colors"
              >
                <span className={isMember ? "text-accent-primary" : "text-transparent"}>✓</span>
                <span className="text-text-primary truncate">{collection.name}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
