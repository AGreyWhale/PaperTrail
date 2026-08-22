import { Link } from "react-router-dom";
import { Card } from "./ui/Card";
import type { SearchHit } from "../lib/types";

const STOPWORDS = new Set(
  "the a an and or of to in for on with is are was were be been it its this that these those as at by from we our they their he she you i not can may".split(
    " ",
  ),
);

//Bold the words the reader actually searched for, the way Ctrl-F does
function highlight(text: string, query: string) {
  const terms = query
    .toLowerCase()
    .match(/[a-z0-9]+/g)
    ?.filter((w) => w.length > 2 && !STOPWORDS.has(w));
  if (!terms?.length) return text;

  // split() with a capturing group keeps the matches as array entries, so the
  // term check alone decides. Deliberately not reusing pattern.test() here —
  // a /g regex carries lastIndex between calls and flips results alternately.
  const pattern = new RegExp(`(${[...new Set(terms)].map(escapeRegex).join("|")})`, "gi");
  return text.split(pattern).map((part, i) =>
    terms.includes(part.toLowerCase()) ? (
      <mark key={i} className="bg-accent-primary-soft text-accent-primary rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

//Links to the matching page, so a result opens where the answer is
export function SearchResultCard({ hit, query }: { hit: SearchHit; query: string }) {
  return (
    <Link to={`/papers/${hit.paper_id}?page=${hit.page_number}`}>
      <Card interactive className="flex flex-col gap-2 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-serif text-base leading-snug text-text-primary">{hit.title}</h3>
          <span className="text-xs shrink-0 px-2 py-0.5 rounded-full bg-accent-primary-soft text-accent-primary tabular-nums">
            Page {hit.page_number}
          </span>
        </div>

        <p className="text-xs text-text-muted">
          {hit.authors.join(", ")}
          {hit.venue && ` · ${hit.venue}`}
          {hit.year && ` · ${hit.year}`}
          {hit.match_count > 1 && ` · ${hit.match_count} passages match`}
        </p>

        <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-primary/30 pl-3">
          {highlight(hit.excerpt, query)}
        </p>
      </Card>
    </Link>
  );
}
