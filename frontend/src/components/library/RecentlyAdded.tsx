import { Link } from "react-router-dom";
import { Card } from "../ui/Card";
import type { Paper } from "../../lib/types";

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function RecentlyAdded({ papers }: { papers: Paper[] }) {
  //Already newest-first from the API, so just take the head
  const recent = papers.slice(0, 4);
  if (recent.length === 0) return null;

  return (
    <Card className="p-5 flex flex-col gap-3">
      <h2 className="font-serif text-base text-text-primary">Recently added</h2>

      <ul className="flex flex-col">
        {recent.map((paper) => (
          <li key={paper.id}>
            <Link
              to={`/papers/${paper.id}`}
              className="group flex items-baseline gap-3 py-2 border-b border-border last:border-b-0"
            >
              <span className="flex-1 text-sm text-text-primary leading-snug line-clamp-2 group-hover:text-accent-primary transition-colors">
                {paper.title}
              </span>
              <span className="text-xs text-text-muted shrink-0 tabular-nums">
                {shortDate(paper.created_at)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
