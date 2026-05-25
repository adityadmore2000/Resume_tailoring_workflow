"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Editor from "@monaco-editor/react";

import { API_BASE_URL, compileResume, getResumeLatex, getResumeMarkdown, getResumeText, getResumeTraceability, putResumeLatex } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ResumePreviewPage() {
  const params = useParams<{ resumeId: string }>();
  const resumeId = decodeURIComponent(params.resumeId);

  const latexQuery = useQuery({ queryKey: ["resume-latex", resumeId], queryFn: () => getResumeLatex(resumeId) });
  const mdQuery = useQuery({ queryKey: ["resume-md", resumeId], queryFn: () => getResumeMarkdown(resumeId) });
  const txtQuery = useQuery({ queryKey: ["resume-txt", resumeId], queryFn: () => getResumeText(resumeId) });
  const traceQuery = useQuery({ queryKey: ["resume-trace", resumeId], queryFn: () => getResumeTraceability(resumeId) });

  const [tab, setTab] = React.useState<"pdf" | "latex" | "md" | "txt" | "trace" | "logs">("pdf");
  const [latex, setLatex] = React.useState<string>("");
  const [compileLog, setCompileLog] = React.useState<string>("");
  const [compiledAt, setCompiledAt] = React.useState<string>("");

  React.useEffect(() => {
    if (latexQuery.data?.latex && !latex) setLatex(latexQuery.data.latex);
  }, [latexQuery.data?.latex, latex]);

  const saveMutation = useMutation({
    mutationFn: () => putResumeLatex(resumeId, latex)
  });

  const compileMutation = useMutation({
    mutationFn: async () => {
      const res = await compileResume(resumeId, latex);
      setCompileLog(res.log ?? "");
      setCompiledAt(res.compiled_at ?? "");
      return res;
    }
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Resume Workspace</h1>
          <p className="mt-1 text-sm text-slate-700">Step 4 of 4 — Review & Export. PDF is read-only; LaTeX is editable.</p>
        </div>
        <div className="flex gap-2">
          <a href={`${API_BASE_URL}/api/resumes/${encodeURIComponent(resumeId)}/export/pdf`} target="_blank" rel="noreferrer">
            <Button variant="secondary">Export PDF</Button>
          </a>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>How this works</CardTitle>
          <CardDescription>Traceability maps generated bullets back to evidence in your Experience Bank.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-slate-700">
          Recommended next step: audit traceability, then export your recruiter-ready PDF.
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["pdf", "PDF Preview"],
            ["latex", "LaTeX Source"],
            ["md", "Tailored Markdown"],
            ["txt", "Tailored Text"],
            ["trace", "Traceability"],
            ["logs", "Compile Logs"]
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            className={`rounded-md border px-3 py-1.5 text-sm ${tab === k ? "bg-slate-100" : "bg-white"}`}
            onClick={() => setTab(k)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "pdf" ? (
        <Card>
          <CardHeader>
            <CardTitle>PDF Preview (read-only)</CardTitle>
            <CardDescription>Recompile after editing LaTeX to update the preview.</CardDescription>
          </CardHeader>
          <CardContent>
            <iframe
              title="pdf"
              src={`${API_BASE_URL}/api/resumes/${encodeURIComponent(resumeId)}/pdf`}
              className="h-[860px] w-full rounded-md border"
            />
          </CardContent>
        </Card>
      ) : null}

      {tab === "latex" ? (
        <Card>
          <CardHeader>
            <CardTitle>LaTeX Source (editable)</CardTitle>
            <CardDescription>Save, then recompile to refresh the PDF preview.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Saving…" : "Save"}
              </Button>
              <Button onClick={() => compileMutation.mutate()} disabled={compileMutation.isPending} variant="secondary">
                {compileMutation.isPending ? "Compiling…" : "Recompile"}
              </Button>
              {compiledAt ? <div className="text-xs text-slate-600">Last compile: {compiledAt}</div> : null}
            </div>
            <div className="h-[820px] overflow-hidden rounded-md border">
              <Editor
                height="820px"
                defaultLanguage="latex"
                value={latex}
                onChange={(v) => setLatex(v ?? "")}
                options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: "on" }}
              />
            </div>
            {latexQuery.error ? <div className="text-sm text-red-600">{String(latexQuery.error)}</div> : null}
          </CardContent>
        </Card>
      ) : null}

      {tab === "md" ? (
        <Card>
          <CardHeader>
            <CardTitle>Tailored Markdown</CardTitle>
            <CardDescription>Read-only artifact generated from verified evidence.</CardDescription>
          </CardHeader>
          <CardContent className="prose prose-slate max-w-none">
            {mdQuery.data?.markdown ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{mdQuery.data.markdown}</ReactMarkdown> : <div>Loading…</div>}
          </CardContent>
        </Card>
      ) : null}

      {tab === "txt" ? (
        <Card>
          <CardHeader>
            <CardTitle>Tailored Text</CardTitle>
            <CardDescription>Read-only artifact generated from verified evidence.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm">{txtQuery.data?.text ?? "Loading…"}</pre>
          </CardContent>
        </Card>
      ) : null}

      {tab === "trace" ? (
        <Card>
          <CardHeader>
            <CardTitle>Traceability</CardTitle>
            <CardDescription>If it doesn’t map to evidence, treat it as unverified.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="overflow-auto rounded-md bg-slate-50 p-3 text-sm">
              {JSON.stringify(traceQuery.data?.traceability ?? null, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      {tab === "logs" ? (
        <Card>
          <CardHeader>
            <CardTitle>Compile Logs</CardTitle>
            <CardDescription>Shown after you click Recompile.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm">{compileLog || "(no compile log yet)"}</pre>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

