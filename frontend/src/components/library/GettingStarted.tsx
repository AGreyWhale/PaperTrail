import { Card } from "../ui/Card";

const STEPS = [
  "Add a paper by pasting its DOI",
  "Attach the PDF from the reading view",
  "Process it, then prepare it for Q&A",
  "Ask questions, highlight, and take notes",
];

//Only shown while the library is still small — it retires itself rather than
//becoming permanent chrome
export function GettingStarted({ paperCount }: { paperCount: number }) {
  if (paperCount > 2) return null;

  return (
    <Card className="p-5 flex flex-col gap-3">
      <h2 className="font-serif text-base text-text-primary">Getting started</h2>
      <ol className="flex flex-col gap-2">
        {STEPS.map((step, i) => (
          <li key={step} className="flex gap-2.5 text-sm text-text-secondary leading-snug">
            <span className="shrink-0 w-5 h-5 rounded-full bg-accent-primary-soft text-accent-primary text-xs flex items-center justify-center font-medium">
              {i + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
    </Card>
  );
}
