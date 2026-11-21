"use client";

import type { InputHTMLAttributes, ReactNode } from "react";

/** Labelled form field with consistent styling and accessible hint/error text. */
export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string | null;
  children?: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-charcoal">
        {label}
      </label>
      <div className="mt-1">{children}</div>
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-11 w-full rounded-lg border border-border bg-white px-3 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30 ${props.className ?? ""}`}
    />
  );
}
