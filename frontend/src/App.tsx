import { Button } from "./components/ui/Button";
import { PaperTile } from "./components/ui/PaperTile";

/** TEMPORARY UNTIL FURTHER COMPLETION OF APP */
function App() {
  return (
    <div className="min-h-screen bg-bg px-8 py-12">
      <div className="max-w-5xl mx-auto flex flex-col gap-10">
        <header className="flex flex-col gap-2">
          <h1 className="font-serif text-4xl text-text-primary">PaperTrail</h1>
          <p className="text-text-secondary">Design system preview — Stage 2</p>
        </header>

        <section className="flex flex-col gap-3">
          <h2 className="font-serif text-xl text-text-primary">Buttons</h2>
          <div className="flex items-center gap-3">
            <Button variant="primary">Save to Library</Button>
            <Button variant="ai">Ask AI</Button>
            <Button variant="secondary">Export</Button>
            <Button variant="ghost">Dismiss</Button>
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="font-serif text-xl text-text-primary">Library tile</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <PaperTile
              title="Attention Is All You Need"
              authors={["Vaswani", "Shazeer", "Parmar", "Uszkoreit"]}
              venue="NeurIPS"
              year={2017}
              tags={["transformers", "nlp"]}
              readingProgress={62}
              lastOpened="2 days ago"
            />
            <PaperTile
              title="Neural Ordinary Differential Equations"
              authors={["Chen", "Rubanova", "Bettencourt", "Duvenaud"]}
              venue="NeurIPS"
              year={2018}
              tags={["ode", "generative"]}
              readingProgress={20}
              lastOpened="1 week ago"
            />
            <PaperTile
              title="Learning Transferable Visual Models From Natural Language Supervision"
              authors={["Radford", "Kim", "Hallacy"]}
              venue="ICML"
              year={2021}
              tags={["multimodal", "clip"]}
              readingProgress={100}
              lastOpened="yesterday"
            />
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
