import { useNavigate } from "react-router-dom";
import { Button } from "./ui/Button";

interface SelectionBarProps {
  selected: string[];
  onClear: () => void;
}

//Shared entry point for both multi-paper features — they start from the same
//"pick 2+ papers" gesture, so they share one bar rather than two
export function SelectionBar({ selected, onClear }: SelectionBarProps) {
  const navigate = useNavigate();
  const ready = selected.length >= 2;
  const query = `?papers=${selected.join(",")}`;

  return (
    <div className="sticky top-0 z-10 -mx-6 px-6 py-3 bg-accent-primary-soft border-y border-accent-primary/20 flex flex-wrap items-center gap-3">
      <span className="text-sm text-accent-primary">
        {selected.length} selected
        {!ready && " — pick at least 2"}
      </span>

      <div className="flex items-center gap-2 ml-auto">
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
        <Button size="sm" variant="ghost" onClick={onClear}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
