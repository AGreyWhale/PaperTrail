import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "./ui/Button";
import { useApiClient } from "../lib/api";
import type { Paper } from "../lib/types";

//Destructive and re-run actions for one paper, kept together behind a menu so
//the reading header stays calm
export function PaperActions({ paper }: { paper: Paper }) {
  const { request } = useApiClient();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["paper", paper.id] });
    queryClient.invalidateQueries({ queryKey: ["papers"] });
  }

  const reprocess = useMutation({
    mutationFn: () => request<Paper>(`/api/papers/${paper.id}/process`, { method: "POST" }),
    onSuccess: () => {
      setOpen(false);
      refresh();
    },
  });

  const replace = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<Paper>(`/api/papers/${paper.id}/file`, { method: "POST", body: form });
    },
    onSuccess: () => {
      setOpen(false);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: () => request(`/api/papers/${paper.id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["papers"] });
      navigate("/library");
    },
  });

  return (
    <div className="relative">
      <button
        onClick={(e) => {
          // Tiles wrap this in a <Link>; don't navigate on a menu click.
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        title="More actions"
        aria-label="More actions"
        className="text-text-muted hover:text-text-primary px-2 py-1 rounded-md hover:bg-bg-secondary transition-colors"
      >
        ⋯
      </button>

      {open && (
        <div
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
          className="absolute right-0 top-full mt-1 z-20 w-60 rounded-control border border-border bg-surface shadow-lg py-1">
          <MenuItem
            onClick={() => fileRef.current?.click()}
            disabled={replace.isPending}
          >
            {replace.isPending ? "Uploading…" : paper.has_file ? "Replace PDF…" : "Attach PDF…"}
          </MenuItem>

          <MenuItem
            onClick={() => reprocess.mutate()}
            disabled={!paper.has_file || reprocess.isPending}
          >
            {reprocess.isPending ? "Reprocessing…" : "Reprocess text"}
          </MenuItem>

          <div className="h-px bg-border my-1" />

          {confirming ? (
            <div className="px-3 py-2 flex flex-col gap-2">
              <p className="text-xs text-text-secondary leading-snug">
                Delete this paper, its notes and highlights? This can't be undone.
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="ai"
                  onClick={() => remove.mutate()}
                  disabled={remove.isPending}
                >
                  {remove.isPending ? "Deleting…" : "Delete"}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <MenuItem onClick={() => setConfirming(true)} danger>
              Delete paper…
            </MenuItem>
          )}
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          // Reset so picking the same file twice still fires a change event.
          e.target.value = "";
          if (file) replace.mutate(file);
        }}
      />
    </div>
  );
}

function MenuItem({
  onClick,
  disabled,
  danger,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full text-left text-sm px-3 py-1.5 transition-colors disabled:opacity-40 ${
        danger ? "text-accent-ai hover:bg-accent-ai-soft" : "text-text-primary hover:bg-surface-hover"
      }`}
    >
      {children}
    </button>
  );
}
