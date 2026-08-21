import { useState } from "react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { useApiClient } from "../lib/api";

interface PaperPreview{
    title: string;
    authors: string[];
    venue: string | null;
    year: number | null;
}

interface AddPaperByDoiProps{
    onPaperAdded?: () => void;
}

type Status = "idle" | "looking-up" | "previewing" | "saving" | "error";

//Doi -> CrossRef -> Show preview -> confirm -> save to library
export function AddPaperByDoi({ onPaperAdded }: AddPaperByDoiProps){
    const { request } = useApiClient();
    const [doi, setDoi] = useState("");
    const [status, setStatus] = useState<Status>("idle");
    const [error, setError] = useState<string | null>(null);
    const [preview, setPreview] = useState<PaperPreview | null>(null);
    const [authorsInput, setAuthorsInput] = useState("");

    async function handleLookup() {
        if (!doi.trim()) return;
        setStatus("looking-up");
        setError(null);
        try{
            const data = await request<PaperPreview>(
                `/api/papers/lookup?doi=${encodeURIComponent(doi.trim())}`,
            );
            setPreview(data);
            setAuthorsInput(data.authors.join(", "));
            setStatus("previewing");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Couldn't look up that DOI");
            setStatus("error");
        }
    }

    async function handleConfirm() {
    if (!preview) return;
    setStatus("saving");
    setError(null);
    try {
      await request("/api/papers", {
        method: "POST",
        body: JSON.stringify({
          ...preview,
          authors: authorsInput
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
        }),
      });
      reset();
      onPaperAdded?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save this paper");
      setStatus("error");
    }
  }

  function reset() {
    setDoi("");
    setPreview(null);
    setAuthorsInput("");
    setStatus("idle");
    setError(null);
  }

  return (
    <div className="flex flex-col gap-4">
      {!preview && (
        <div className="flex items-center gap-2">
          <Input
            placeholder="Paste a DOI, e.g. 10.1038/nphys1170"
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLookup()}
            disabled={status === "looking-up"}
          />
          <Button variant="secondary" onClick={handleLookup} disabled={status === "looking-up"}>
            {status === "looking-up" ? "Looking up…" : "Look up"}
          </Button>
        </div>
      )}

      {error && (
        <p className="text-sm text-accent-ai bg-accent-ai-soft rounded-control px-3 py-2">
          {error}
        </p>
      )}

      {preview && (
        <div className="flex flex-col gap-3 border border-border rounded-card p-4 bg-surface">
          <p className="text-xs text-text-muted uppercase tracking-wide">
            Review before adding to your library
          </p>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-text-secondary">Title</label>
            <Input
              value={preview.title}
              onChange={(e) => setPreview({ ...preview, title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-text-secondary">Authors (comma-separated)</label>
            <Input value={authorsInput} onChange={(e) => setAuthorsInput(e.target.value)} />
          </div>
          <div className="flex gap-3">
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-xs text-text-secondary">Venue</label>
              <Input
                value={preview.venue ?? ""}
                onChange={(e) => setPreview({ ...preview, venue: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5 w-24">
              <label className="text-xs text-text-secondary">Year</label>
              <Input
                type="number"
                value={preview.year ?? ""}
                onChange={(e) =>
                  setPreview({ ...preview, year: e.target.value ? Number(e.target.value) : null })
                }
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Button variant="primary" onClick={handleConfirm} disabled={status === "saving"}>
              {status === "saving" ? "Saving…" : "Save to Library"}
            </Button>
            <Button variant="ghost" onClick={reset} disabled={status === "saving"}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
