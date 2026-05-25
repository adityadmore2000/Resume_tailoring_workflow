"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { listBankItems, readBankFile } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type BankItem = {
  id: string;
  type: string;
  title: string;
  raw_path: string;
  domains: string[];
  tools: string[];
  date_range?: string;
  location?: string;
};

function chips(items: string[]) {
  const xs = Array.from(new Set((items ?? []).map((x) => x.trim()).filter(Boolean))).slice(0, 16);
  return (
    <div className="flex flex-wrap gap-2">
      {xs.map((x) => (
        <span key={x} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
          {x}
        </span>
      ))}
    </div>
  );
}

export default function BankPreviewPage() {
  const params = useParams<{ bankName: string }>();
  const bankName = decodeURIComponent(params.bankName);
  const [selectedKey, setSelectedKey] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<"overview" | "evidence" | "bullets" | "tech">("overview");

  const itemsQuery = useQuery({
    queryKey: ["bank-items", bankName],
    queryFn: () => listBankItems(bankName)
  });

  const items = (itemsQuery.data?.items ?? []) as BankItem[];
  const grouped = React.useMemo(() => {
    const exp = items.filter((x) => x.type === "work_experience");
    const proj = items.filter((x) => x.type === "project");
    const cap = items.filter((x) => x.type === "capability");
    return { exp, proj, cap };
  }, [items]);

  React.useEffect(() => {
    if (!selectedKey && items.length) setSelectedKey(`${items[0].type}:${items[0].id}`);
  }, [items, selectedKey]);

  const selectedItem = React.useMemo(() => {
    if (!selectedKey) return null;
    const [t, id] = selectedKey.split(":");
    return items.find((x) => x.type === t && x.id === id) ?? null;
  }, [items, selectedKey]);

  const contentQuery = useQuery({
    enabled: Boolean(selectedItem?.raw_path),
    queryKey: ["bank-file", bankName, selectedItem?.raw_path],
    queryFn: () => readBankFile(bankName, selectedItem!.raw_path)
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Preview Experience Bank</h1>
          <p className="mt-1 text-sm text-slate-700">Step 2 of 4 — Review extracted content before tailoring.</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/tailor?bank=${encodeURIComponent(bankName)}`}>
            <Button>Tailor Resume</Button>
          </Link>
          <Link href="/banks">
            <Button variant="outline">Back to banks</Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Why this page exists</CardTitle>
          <CardDescription>Human-readable review first. Technical metadata stays optional.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-slate-700">
          Recommended next step: confirm the extracted experience looks accurate, then tailor a resume using this bank.
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        <div className="space-y-3">
          <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm font-medium">{bankName}</div>
          {itemsQuery.isLoading ? <div className="text-sm text-slate-600">Loading…</div> : null}
          {itemsQuery.error ? <div className="text-sm text-red-600">{String(itemsQuery.error)}</div> : null}

          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <div className="text-xs font-semibold text-slate-600">Experience</div>
            <div className="mt-2 space-y-1">
              {grouped.exp.map((it) => {
                const key = `${it.type}:${it.id}`;
                const active = key === selectedKey;
                return (
                  <button
                    key={key}
                    className={`w-full rounded-md px-2 py-1 text-left text-sm hover:bg-slate-50 ${active ? "bg-slate-100 font-medium" : ""}`}
                    onClick={() => setSelectedKey(key)}
                  >
                    {it.title}
                  </button>
                );
              })}
            </div>
            <div className="mt-4 text-xs font-semibold text-slate-600">Projects</div>
            <div className="mt-2 space-y-1">
              {grouped.proj.map((it) => {
                const key = `${it.type}:${it.id}`;
                const active = key === selectedKey;
                return (
                  <button
                    key={key}
                    className={`w-full rounded-md px-2 py-1 text-left text-sm hover:bg-slate-50 ${active ? "bg-slate-100 font-medium" : ""}`}
                    onClick={() => setSelectedKey(key)}
                  >
                    {it.title}
                  </button>
                );
              })}
            </div>
            <div className="mt-4 text-xs font-semibold text-slate-600">Capabilities</div>
            <div className="mt-2 space-y-1">
              {grouped.cap.map((it) => {
                const key = `${it.type}:${it.id}`;
                const active = key === selectedKey;
                return (
                  <button
                    key={key}
                    className={`w-full rounded-md px-2 py-1 text-left text-sm hover:bg-slate-50 ${active ? "bg-slate-100 font-medium" : ""}`}
                    onClick={() => setSelectedKey(key)}
                  >
                    {it.title}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {!selectedItem ? (
            <Card>
              <CardHeader>
                <CardTitle>Select an item</CardTitle>
                <CardDescription>Choose Experience / Projects / Capabilities from the left.</CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>{selectedItem.title}</CardTitle>
                  <CardDescription>{selectedItem.type.replaceAll("_", " ")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedItem.date_range || selectedItem.location ? (
                    <div className="text-sm text-slate-700">
                      {[selectedItem.date_range, selectedItem.location].filter(Boolean).join(" · ")}
                    </div>
                  ) : null}
                  {selectedItem.domains?.length ? (
                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-slate-600">Domains</div>
                      {chips(selectedItem.domains)}
                    </div>
                  ) : null}
                  {selectedItem.tools?.length ? (
                    <div className="space-y-1">
                      <div className="text-xs font-semibold text-slate-600">Tools</div>
                      {chips(selectedItem.tools)}
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <div className="flex flex-wrap gap-2">
                <button
                  className={`rounded-md border px-3 py-1.5 text-sm ${tab === "overview" ? "bg-slate-100" : "bg-white"}`}
                  onClick={() => setTab("overview")}
                >
                  Overview
                </button>
                <button
                  className={`rounded-md border px-3 py-1.5 text-sm ${tab === "evidence" ? "bg-slate-100" : "bg-white"}`}
                  onClick={() => setTab("evidence")}
                >
                  Evidence
                </button>
                <button
                  className={`rounded-md border px-3 py-1.5 text-sm ${tab === "bullets" ? "bg-slate-100" : "bg-white"}`}
                  onClick={() => setTab("bullets")}
                >
                  Resume Bullets
                </button>
                <button
                  className={`rounded-md border px-3 py-1.5 text-sm ${tab === "tech" ? "bg-slate-100" : "bg-white"}`}
                  onClick={() => setTab("tech")}
                >
                  Technical Metadata
                </button>
              </div>

              <Card>
                <CardContent className="prose prose-slate max-w-none p-5">
                  {contentQuery.isLoading ? <div>Loading content…</div> : null}
                  {contentQuery.error ? <div className="text-red-600">{String(contentQuery.error)}</div> : null}
                  {contentQuery.data?.content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{contentQuery.data.content}</ReactMarkdown>
                  ) : (
                    <div className="text-sm text-slate-600">
                      This bank item doesn’t have a readable page yet. (Try regenerating the bank from the master resume.)
                    </div>
                  )}
                </CardContent>
              </Card>
              {tab === "tech" && selectedItem ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Technical metadata</CardTitle>
                    <CardDescription>Shown only for debugging.</CardDescription>
                  </CardHeader>
                  <CardContent className="text-sm">
                    <pre className="overflow-auto rounded-md bg-slate-50 p-3">{JSON.stringify(selectedItem, null, 2)}</pre>
                  </CardContent>
                </Card>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

