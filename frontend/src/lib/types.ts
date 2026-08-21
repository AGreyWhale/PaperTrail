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
