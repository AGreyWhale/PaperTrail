import { Link } from "react-router-dom";
import { Card } from "./ui/Card";
import type { SearchHit } from "../lib/types";

//Links straight to the matching page, so a result opens where the answer is
export function SearchResultCard({ hit }: { hit: SearchHit }) {
  return (
    <Link to={`/papers/${hit.paper_id}?page=${hit.page_number}`}>
      <Card interactive className="flex flex-col gap-2">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-serif text-lg leading-snug text-text-primary">{hit.title}</h3>
          <span className="text-xs text-text-muted shrink-0 tabular-nums">
            p. {hit.page_number}
            {hit.match_count > 1 && ` · ${hit.match_count} matches`}
          </span>
        </div>

        <p className="text-xs text-text-muted">
          {hit.authors.join(", ")}
          {hit.venue && ` · ${hit.venue}`}
          {hit.year && ` · ${hit.year}`}
        </p>

        <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-info-soft pl-3">
          {hit.excerpt}
        </p>
      </Card>
    </Link>
  );
}
