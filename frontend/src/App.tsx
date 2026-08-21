import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { LibraryPage } from "./pages/LibraryPage";

// Lazy so the Library page doesn't download react-pdf/pdfjs, which is
// heavy and only the reading view needs it.
const ReadingPage = lazy(() =>
  import("./pages/ReadingPage").then((m) => ({ default: m.ReadingPage })),
);

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<LibraryPage />} />
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
