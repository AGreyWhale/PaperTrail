import { useState } from "react";
import { Show, SignInButton, SignOutButton, useAuth } from "@clerk/react";
import { Button } from "./components/ui/ui/Button";
import { PaperTile } from "./components/ui/ui/PaperTile";
import { AddPaperByDoi } from "./components/ui/AddPaperByDoi";
import { AttachPdfButton } from "./components/ui/AttachPdfButton";
import { useApiClient } from "./lib/api";

interface Paper {
  id: string;
  title: string;
  authors: string[];
  venue: string | null;
  year: number | null;
  has_file: boolean;
}

//Temp design to see if auth works:
function App() {
  const { isLoaded } = useAuth();
  const { request } = useApiClient();
  const [papers, setPapers] = useState<Paper[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadPapers() {
    setError(null);
    try {
      const data = await request<Paper[]>("/api/papers");
      setPapers(data);
    } catch(err){
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  if(!isLoaded) return null;

  return (
    <div className="min-h-screen bg-bg px-8 py-12">
      <div className="max-w-5xl mx-auto flex flex-col gap-10">
        <header className="flex items-center justify-between">
          <div className="flex flex-col gap-2">
            <h1 className="font-serif text-4xl text-text-primary">PaperTrail</h1>
            <p className="text-text-secondary">Design system + auth preview — Stage 4</p>
          </div>

          <Show when="signed-out">
            <SignInButton>
              <Button variant="primary">Sign in</Button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <SignOutButton>
              <Button variant="secondary">Sign out</Button>
            </SignOutButton>
          </Show>
        </header>

        <section className="flex flex-col gap-3">
          <h2 className="font-serif text-xl text-text-primary">Authenticated API call</h2>
          <Show when="signed-out">
            <p className="text-sm text-text-secondary">Sign in to fetch your papers from the API.</p>
          </Show>
          <Show when="signed-in">
            <div className="flex items-center gap-3">
              <Button variant="ai" onClick={loadPapers}>
                Fetch my papers
              </Button>
              {papers !== null && (
                <span className="text-sm text-text-muted">{papers.length} paper(s) found</span>
              )}
            </div>
            {error && <p className="text-sm text-accent-ai">{error}</p>}
            {papers !== null && papers.length > 0 && (
              <div className="flex flex-col gap-2 mt-2">
                {papers.map((paper) => (
                  <div
                    key={paper.id}
                    className="flex items-center justify-between border border-border rounded-control px-3.5 py-2.5 bg-surface"
                  >
                    <span className="text-sm text-text-primary truncate pr-4">{paper.title}</span>
                    <AttachPdfButton
                      paperId={paper.id}
                      hasFile={paper.has_file}
                      onAttached={loadPapers}
                    />
                  </div>
                ))}
              </div>
            )}
          </Show>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="font-serif text-xl text-text-primary">Add a paper by DOI</h2>
          <Show when="signed-out">
            <p className="text-sm text-text-secondary">Sign in to add papers to your library.</p>
          </Show>
          <Show when="signed-in">
            <AddPaperByDoi onPaperAdded={loadPapers} />
          </Show>
        </section>

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
