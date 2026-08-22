import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { useApiClient } from "../lib/api";
import type { Collection } from "../lib/types";

interface CollectionsBarProps {
  selected: Collection | null;
  onSelect: (collection: Collection | null) => void;
}

//Chip row rather than a sidebar — keeps the grid full-width, which matters
//more here than a persistent nav rail
export function CollectionsBar({ selected, onSelect }: CollectionsBarProps) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const { data: collections } = useQuery({
    queryKey: ["collections"],
    queryFn: () => request<Collection[]>("/api/collections"),
  });

  const create = useMutation({
    mutationFn: (value: string) =>
      request<Collection>("/api/collections", {
        method: "POST",
        body: JSON.stringify({ name: value }),
      }),
    onSuccess: () => {
      setName("");
      setCreating(false);
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => request(`/api/collections/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      onSelect(null);
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => onSelect(null)}
        className={`text-sm px-3 py-1.5 rounded-control border transition-colors ${
          selected === null
            ? "border-accent-primary bg-accent-primary-soft text-accent-primary"
            : "border-border text-text-secondary hover:border-border-strong"
        }`}
      >
        All papers
      </button>

      {collections?.map((collection) => (
        <div key={collection.id} className="group relative">
          <button
            onClick={() => onSelect(selected?.id === collection.id ? null : collection)}
            className={`text-sm pl-3 pr-7 py-1.5 rounded-control border transition-colors ${
              selected?.id === collection.id
                ? "border-accent-primary bg-accent-primary-soft text-accent-primary"
                : "border-border text-text-secondary hover:border-border-strong"
            }`}
          >
            {collection.name}
            <span className="ml-1.5 text-xs text-text-muted">{collection.paper_count}</span>
          </button>
          <button
            onClick={() => remove.mutate(collection.id)}
            aria-label={`Delete collection ${collection.name}`}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-text-muted hover:text-accent-ai transition-opacity px-1"
          >
            ×
          </button>
        </div>
      ))}

      {creating ? (
        <div className="flex items-center gap-1.5">
          <Input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && name.trim()) create.mutate(name.trim());
              if (e.key === "Escape") setCreating(false);
            }}
            placeholder="Collection name…"
            className="text-sm py-1.5 w-44"
          />
          <Button size="sm" variant="ghost" onClick={() => setCreating(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setCreating(true)}>
          + New collection
        </Button>
      )}
    </div>
  );
}
