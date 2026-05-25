"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type Option = { value: string; label: string };

export function Select({
  value,
  onChange,
  placeholder,
  options,
  disabled
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  placeholder: string;
  options: Option[];
  disabled?: boolean;
}) {
  return (
    <div className={cn(disabled ? "opacity-60" : "")}>
      <select
        className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed"
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value ? e.target.value : null)}
      >
        <option value="" disabled>
          {placeholder}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

