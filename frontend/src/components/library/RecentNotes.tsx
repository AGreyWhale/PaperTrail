import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card } from "../ui/Card";
import { useApiClient } from "../../lib/api";
import type { RecentNote } from "../../lib/types";

//A note's own words when it has them, otherwise the passage it was taken from
function preview(note: RecentNote): string {
  return note.content.trim() || note.quoted_text?.trim() || "";
}

export function RecentNotes() {
  const { request } = useApiClient();

  const { data: notes } = useQuery({
    queryKey: ["recent-notes"],
    queryFn: () => request<RecentNote[]>("/api/notes/recent?limit=4"),
  });

  if (!notes || notes.length === 0) return null;

  return (
    <Card className="p-5 flex flex-col gap-3">
      <h2 className="font-serif text-base text-text-primary">Recent notes</h2>

      <ul className="flex flex-col">
        {notes.map((note) => (
          <li key={note.id}>
            {/* Reuses the reading view's ?page= deep link, the same mechanism
                citations already use to scroll the PDF. */}
            <Link
              to={`/papers/${note.paper_id}${note.page_number ? `?page=${note.page_number}` : ""}`}
              className="group flex flex-col gap-1 py-2 border-b border-border last:border-b-0"
            >
              <span
                className={`text-sm leading-snug line-clamp-2 group-hover:text-accent-primary transition-colors ${
                  note.content.trim() ? "text-text-primary" : "text-text-secondary italic"
                }`}
              >
                {preview(note)}
              </span>
              <span className="text-xs text-text-muted line-clamp-1">
                {note.paper_title}
                {note.page_number && ` · p. ${note.page_number}`}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
