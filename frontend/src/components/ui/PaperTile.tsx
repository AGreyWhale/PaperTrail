import { Card } from "./Card";

export type PaperTileStatus =
  | "needs_file"
  | "processing"
  | "embedding"
  | "ready"
  | "failed";

interface PaperTileProps{
    title: string;
    authors: string[];
    venue: string | null;
    year: number | null;
    addedDate: string;
    status: PaperTileStatus;
    tags?: string[];
}

const STATUS_LABEL: Record<PaperTileStatus, string> = {
  needs_file: "No PDF yet",
  processing: "Processing…",
  embedding: "Embedding…",
  ready: "Ready",
  failed: "Failed",
};

const STATUS_CLASSES: Record<PaperTileStatus, string> = {
  needs_file: "bg-bg-secondary text-text-muted",
  processing: "bg-accent-ai-soft text-accent-ai",
  embedding: "bg-accent-ai-soft text-accent-ai",
  ready: "bg-accent-primary-soft text-accent-primary",
  failed: "bg-accent-ai-soft text-accent-ai",
};

//A paper in the library grid. Badge shows real pipeline state, since we
//don't track actual reading position yet
export function PaperTile({ title, authors, venue, year, addedDate, status, tags = [] }: PaperTileProps){
    return (
    <Card interactive className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <div className="h-1 w-10 rounded-full bg-accent-primary/60" />
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_CLASSES[status]}`}>
          {STATUS_LABEL[status]}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="font-serif text-lg leading-snug text-text-primary line-clamp-2">
          {title}
        </h3>
        <p className="text-sm text-text-secondary line-clamp-1">
          {authors.join(", ")}
        </p>
        {(venue || year) && (
          <p className="text-xs text-text-muted">
            {venue}
            {venue && year ? " · " : ""}
            {year}
          </p>
        )}
      </div>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded-full bg-accent-info-soft text-accent-info"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <p className="text-xs text-text-muted mt-auto pt-2">Added {addedDate}</p>
    </Card>
  );
}
