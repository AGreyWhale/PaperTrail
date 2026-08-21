import { useRef, useState } from "react";
import { Button } from "./ui/Button";
import { useApiClient } from "../../lib/api";

interface AttachPdfButtonProps {
  paperId: string;
  hasFile: boolean;
  onAttached?: () => void;
}

export function AttachPdfButton({ paperId, hasFile, onAttached }: AttachPdfButtonProps) {
  const { request } = useApiClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await request(`/api/papers/${paperId}/file`, { method: "POST", body: formData });
      onAttached?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      // Reset so choosing the same file again still fires onChange
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={handleFileChosen}
      />
      <Button
        variant={hasFile ? "secondary" : "ai"}
        size="sm"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? "Uploading…" : hasFile ? "Replace PDF" : "Attach PDF"}
      </Button>
      {error && <span className="text-xs text-accent-ai">{error}</span>}
    </div>
  );
}
