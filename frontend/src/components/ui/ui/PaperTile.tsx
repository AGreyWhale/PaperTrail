import { Card } from "./Card";

interface PaperTileProps{
    title: string;
    authors: string[];
    venue: string;
    year: number;
    tags: string[];
    readingProgress: number;
    lastOpened: string;
}

//A paper in the library grid
export function PaperTile({
    title,
    authors,
    venue,
    year,
    tags,
    readingProgress,
    lastOpened,
}: PaperTileProps){
    return (
    <Card interactive className="p-5 flex flex-col gap-4">
      <div className="h-1 w-10 rounded-full bg-accent-primary/60" />

      <div className="flex flex-col gap-1.5">
        <h3 className="font-serif text-lg leading-snug text-text-primary line-clamp-2">
          {title}
        </h3>
        <p className="text-sm text-text-secondary">
          {authors.slice(0, 3).join(", ")}
          {authors.length > 3 ? " et al." : ""}
        </p>
        <p className="text-xs text-text-muted">
          {venue} · {year}
        </p>
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

      <div className="flex flex-col gap-1.5 mt-auto pt-2">
        <div className="h-1 w-full rounded-full bg-bg-secondary overflow-hidden">
          <div
            className="h-full rounded-full bg-accent-primary"
            style={{ width: `${Math.min(100, Math.max(0, readingProgress))}%` }}
          />
        </div>
        <p className="text-xs text-text-muted">Last opened {lastOpened}</p>
      </div>
    </Card>
  );
}