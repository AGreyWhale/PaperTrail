import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { HomePage } from "./pages/HomePage";
import { LibraryPage } from "./pages/LibraryPage";
import { ComparePage } from "./pages/ComparePage";
import { ReviewPage } from "./pages/ReviewPage";

// Lazy so the Library page doesn't download react-pdf/pdfjs, which is
// heavy and only the reading view needs it.
const ReadingPage = lazy(() =>
  import("./pages/ReadingPage").then((m) => ({ default: m.ReadingPage })),
);

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route
          path="/papers/:paperId"
          element={
            <Suspense fallback={null}>
              <ReadingPage />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}

export default App;
