import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "../lib/api";
import type { Paper } from "../lib/types";

interface FavoriteButtonProps {
  paperId: string;
  isFavorite: boolean;
  //Extra query keys to refresh, so a tile and the reading header stay in step
  invalidate?: unknown[][];
}

//accent-primary, since favoriting is the user's own action rather than the AI's
export function FavoriteButton({ paperId, isFavorite, invalidate = [] }: FavoriteButtonProps) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();

  const toggle = useMutation({
    mutationFn: () => request<Paper>(`/api/papers/${paperId}/favorite`, { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      invalidate.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
    },
  });

  return (
    <button
      onClick={(e) => {
        // Tiles sit inside a <Link>, so don't navigate on a star click.
        e.preventDefault();
        e.stopPropagation();
        toggle.mutate();
      }}
      disabled={toggle.isPending}
      title={isFavorite ? "Remove from favorites" : "Add to favorites"}
      aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
      aria-pressed={isFavorite}
      className={`shrink-0 w-7 h-7 rounded-md flex items-center justify-center transition-colors ${
        isFavorite
          ? "text-accent-primary hover:bg-accent-primary-soft"
          : "text-text-muted hover:text-accent-primary hover:bg-accent-primary-soft"
      }`}
    >
      <svg viewBox="0 0 20 20" className="w-4 h-4" fill={isFavorite ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
        <path d="M10 2.5l2.35 4.76 5.25.76-3.8 3.7.9 5.23L10 14.48l-4.7 2.47.9-5.23-3.8-3.7 5.25-.76z" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
