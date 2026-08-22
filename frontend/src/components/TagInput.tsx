import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Input } from "./ui/Input";
import { useApiClient } from "../lib/api";
import type { Paper, Tag } from "../lib/types";

//accent-info, matching the citation/metadata role tags play
export function TagInput({ paper }: { paper: Paper }) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");

  const { data: allTags } = useQuery({
    queryKey: ["tags"],
    queryFn: () => request<Tag[]>("/api/tags"),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["paper", paper.id] });
    queryClient.invalidateQueries({ queryKey: ["papers"] });
    queryClient.invalidateQueries({ queryKey: ["tags"] });
  }

  const add = useMutation({
    mutationFn: (name: string) =>
      request<Paper>(`/api/papers/${paper.id}/tags`, {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => {
      setDraft("");
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (tagId: string) =>
      request<Paper>(`/api/papers/${paper.id}/tags/${tagId}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {paper.tags.map((tag) => (
          <span
            key={tag.id}
            className="group text-xs pl-2 pr-1 py-0.5 rounded-full bg-accent-info-soft text-accent-info flex items-center gap-1"
          >
            {tag.name}
            <button
              onClick={() => remove.mutate(tag.id)}
              aria-label={`Remove tag ${tag.name}`}
              className="opacity-40 group-hover:opacity-100 hover:text-accent-ai transition-opacity px-0.5"
            >
              ×
            </button>
          </span>
        ))}
        {paper.tags.length === 0 && <span className="text-xs text-text-muted">No tags yet</span>}
      </div>

      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && draft.trim() && add.mutate(draft.trim())}
        placeholder="Add a tag…"
        list="tag-suggestions"
        className="text-xs py-1.5"
      />
      {/* Existing tags as native autocomplete, no extra dependency */}
      <datalist id="tag-suggestions">
        {allTags?.map((tag) => (
          <option key={tag.id} value={tag.name} />
        ))}
      </datalist>
    </div>
  );
}
