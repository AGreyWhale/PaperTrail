import { useNavigate } from "react-router-dom";
import { Button } from "./ui/Button";
import { useApiClient } from "../lib/api";

interface SelectionBarProps {
  selected: string[];
  onClear: () => void;
}

//Shared entry point for both multi-paper features — they start from the same
//"pick 2+ papers" gesture, so they share one bar rather than two
export function SelectionBar({ selected, onClear }: SelectionBarProps) {
  const navigate = useNavigate();
  const { requestText } = useApiClient();

  //Reuses this same selection rather than a second picker
  async function downloadBibtex() {
    const bib = await requestText("/api/papers/bibtex-export", {
      method: "POST",
      body: JSON.stringify({ paper_ids: selected }),
    });
    const url = URL.createObjectURL(new Blob([bib], { type: "application/x-bibtex" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "papertrail.bib";
    link.click();
    URL.revokeObjectURL(url);
  }

  const ready = selected.length >= 2;
  const query = `?papers=${selected.join(",")}`;

  return (
    <div className="sticky top-0 z-10 -mx-6 px-6 py-3 bg-accent-primary-soft border-y border-accent-primary/20 flex flex-wrap items-center gap-3">
      <span className="text-sm text-accent-primary">
        {selected.length} selected
        {!ready && " — pick at least 2 to compare"}
      </span>

      <div className="flex items-center gap-2 ml-auto">
        {/* Search works on a single paper too, so it isn't gated on 2+ */}
        <Button
          size="sm"
          variant="secondary"
          disabled={selected.length === 0}
          onClick={() => navigate(`/selection-search${query}`)}
        >
          Search
        </Button>
        <Button
          size="sm"
          variant="ai"
          disabled={!ready}
          onClick={() => navigate(`/selection-ask${query}`)}
        >
          Ask
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={!ready}
          onClick={() => navigate(`/compare${query}`)}
        >
          Compare
        </Button>
        <Button
          size="sm"
          variant="ai"
          disabled={!ready}
          onClick={() => navigate(`/review${query}`)}
        >
          Literature review
        </Button>
        <Button
          size="sm"
          variant="secondary"
          disabled={selected.length === 0}
          onClick={downloadBibtex}
        >
          Export .bib
        </Button>
        <Button size="sm" variant="ghost" onClick={onClear}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
