import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "./ui/Button";
import { useApiClient } from "../lib/api";
import type { Note } from "../lib/types";

interface NotesTabProps {
  paperId: string;
  textSize: number;
  //Set when "Save quote" is used in the PDF; opens the composer pre-filled
  pendingQuote?: { text: string; page: number; nonce: number };
}

export function NotesTab({ paperId, textSize, pendingQuote }: NotesTabProps) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [quote, setQuote] = useState<{ text: string; page: number } | null>(null);

  const { data: notes } = useQuery({
    queryKey: ["notes", paperId],
    queryFn: () => request<Note[]>(`/api/papers/${paperId}/notes`),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["notes", paperId] });
  }

  const save = useMutation({
    mutationFn: () =>
      request<Note>(`/api/papers/${paperId}/notes`, {
        method: "POST",
        body: JSON.stringify({
          content: draft.trim(),
          quoted_text: quote?.text ?? null,
          page_number: quote?.page ?? null,
        }),
      }),
    onSuccess: () => {
      setDraft("");
      setQuote(null);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => request(`/api/notes/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  useEffect(() => {
    if (!pendingQuote) return;
    setQuote({ text: pendingQuote.text, page: pendingQuote.page });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuote?.nonce]);

  return (
    <>
      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
        {notes && notes.length === 0 && !quote && (
          <p className="text-sm text-text-muted">
            No notes yet. Highlight a passage in the PDF to colour it, choose Save quote to write
            about it, or type a note below.
          </p>
        )}

        {notes?.map((note) => (
          <div key={note.id} className="flex flex-col gap-1.5 pb-4 border-b border-border last:border-b-0">
            {note.quoted_text && (
              <blockquote
                className={`text-xs text-text-secondary border-l-2 pl-2.5 leading-relaxed ${
                  note.color ? `pt-border-${note.color}` : "border-accent-info-soft"
                }`}
              >
                {note.quoted_text}
                {note.page_number && (
                  <span className="text-text-muted"> (p. {note.page_number})</span>
                )}
              </blockquote>
            )}
            {note.content && (
              <p
                style={{ fontSize: textSize, lineHeight: 1.6 }}
                className="text-text-primary whitespace-pre-wrap"
              >
                {note.content}
              </p>
            )}
            <button
              onClick={() => remove.mutate(note.id)}
              className="text-xs text-text-muted hover:text-accent-ai w-fit transition-colors"
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      <div className="px-5 py-4 border-t border-border flex flex-col gap-2">
        {quote && (
          <div className="text-xs text-text-secondary border-l-2 border-accent-info-soft pl-2.5 py-1 flex items-start gap-2">
            <span className="line-clamp-3 leading-relaxed">{quote.text}</span>
            <button
              onClick={() => setQuote(null)}
              aria-label="Drop quote"
              className="text-text-muted hover:text-accent-ai shrink-0"
            >
              ×
            </button>
          </div>
        )}
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={quote ? "Your note on this passage…" : "Write a note…"}
          rows={3}
          className="w-full rounded-control border border-border bg-surface px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-muted outline-none transition-colors duration-150 focus:border-accent-primary/60 resize-none"
        />
        <Button
          variant="primary"
          onClick={() => save.mutate()}
          disabled={!draft.trim() || save.isPending}
        >
          {save.isPending ? "Saving…" : "Save note"}
        </Button>
      </div>
    </>
  );
}
