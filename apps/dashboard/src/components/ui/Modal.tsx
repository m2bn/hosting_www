"use client";

import { ReactNode } from "react";
import { Button } from "@/components/ui/Button";

type ModalProps = {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
};

export function Modal({ open, title, children, onClose }: ModalProps) {
  if (!open) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-lg rounded-lg border border-border bg-white shadow-soft">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          <Button variant="ghost" onClick={onClose} aria-label="Close modal">
            Close
          </Button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
