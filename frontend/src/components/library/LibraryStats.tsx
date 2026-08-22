import { Card } from "../ui/Card";
import type { Paper } from "../../lib/types";

//Every number here comes from the papers we already fetched — no invented
//metrics, same rule as the pipeline badges on PaperTile
export function LibraryStats({ papers }: { papers: Paper[] }) {
  const ready = papers.filter((p) => p.embedding_status === "embedded").length;
  const working = papers.filter(
    (p) => p.has_file && p.embedding_status !== "embedded" && p.embedding_status !== "failed",
  ).length;
  const needsFile = papers.filter((p) => !p.has_file).length;

  return (
    <Card className="bg-accent-primary-soft border-accent-primary/20 p-5 flex flex-col gap-4">
      <div className="flex items-baseline gap-2">
        <span className="font-serif text-4xl text-accent-primary leading-none">
          {papers.length}
        </span>
        <span className="text-sm text-accent-primary/80">
          paper{papers.length === 1 ? "" : "s"}
        </span>
      </div>

      {/* Proportional bar, so "how much of my library is usable" reads at a
          glance without a number-per-row table. */}
      {papers.length > 0 && (
        <div className="flex h-1.5 rounded-full overflow-hidden bg-accent-primary/15">
          <div className="bg-accent-primary" style={{ flex: ready }} />
          <div className="bg-accent-primary/45" style={{ flex: working }} />
          <div className="bg-transparent" style={{ flex: needsFile }} />
        </div>
      )}

      <dl className="flex flex-col gap-1.5 text-sm">
        <StatRow label="Ready for questions" value={ready} dotClass="bg-accent-primary" />
        {working > 0 && (
          <StatRow label="Processing" value={working} dotClass="bg-accent-primary/45" />
        )}
        {needsFile > 0 && (
          <StatRow label="No PDF yet" value={needsFile} dotClass="bg-accent-primary/15" />
        )}
      </dl>
    </Card>
  );
}

function StatRow({
  label,
  value,
  dotClass,
}: {
  label: string;
  value: number;
  dotClass: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="flex items-center gap-2 text-accent-primary/80">
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
        {label}
      </dt>
      <dd className="tabular-nums text-accent-primary font-medium">{value}</dd>
    </div>
  );
}
