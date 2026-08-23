export interface Tag {
  id: string;
  name: string;
}

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  venue: string | null;
  year: number | null;
  created_at: string;
  has_file: boolean;
  file_original_name: string | null;
  file_size_bytes: number | null;
  processing_status: "unprocessed" | "processing" | "processed" | "failed";
  embedding_status: "not_embedded" | "queued" | "embedding" | "embedded" | "failed";
  embedding_error: string | null;
  last_opened_at: string | null;
  last_page: number | null;
  is_favorite: boolean;
  tags: Tag[];
  collections: { id: string; name: string }[];
}

export interface Citation {
  chunk_id: string;
  page_number: number;
  text: string;
}

export interface AskAnswer {
  answer: string;
  citations: Citation[];
}

export type AskStreamEvent =
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "error"; detail: string }
  | { type: "done" };

//One question and its answer in the panel's history
export interface AnswerEntry {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
  streaming: boolean;
  error?: string;
}

//One paper that matched a library-wide search. The excerpt is the
//"why it matched" — no generated explanation
export interface SearchHit {
  paper_id: string;
  title: string;
  authors: string[];
  venue: string | null;
  year: number | null;
  excerpt: string;
  page_number: number;
  score: number;
  match_count: number;
}

export interface Collection {
  id: string;
  name: string;
  created_at: string;
  paper_count: number;
}

export interface Note {
  id: string;
  paper_id: string;
  content: string;
  quoted_text: string | null;
  page_number: number | null;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComparisonRow {
  paper_id: string;
  title: string;
  datasets: string;
  architecture: string;
  evaluation_metrics: string;
  strengths: string;
  weaknesses: string;
  future_work: string;
}

export interface Comparison {
  papers: ComparisonRow[];
}

export interface ReviewSource {
  paper_id: string;
  title: string;
  citation: string;
}

export interface ThemeCell {
  paper_id: string;
  position: string;
}

export interface Theme {
  theme: string;
  cells: ThemeCell[];
}

export interface LiteratureReview {
  themes: Theme[];
  markdown: string;
  sources: ReviewSource[];
}

//A note plus the paper it belongs to, for the home page's panel
export interface RecentNote extends Note {
  paper_title: string;
}
