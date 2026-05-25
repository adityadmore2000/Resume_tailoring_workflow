import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function FlowBlock({ label }: { label: string }) {
  return <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium">{label}</div>;
}

export default function HomePage() {
  return (
    <div className="space-y-10">
      <section className="grid gap-8 md:grid-cols-2 md:items-center">
        <div className="space-y-4">
          <h1 className="text-3xl font-semibold tracking-tight">Evidence-Grounded AI Resume Tailoring</h1>
          <p className="text-slate-700">
            Convert your master resume into a reusable knowledge base and generate recruiter-focused resumes using verified evidence retrieval.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/banks/create">
              <Button>Create Experience Bank</Button>
            </Link>
            <Link href="/docs">
              <Button variant="secondary">View Workflow</Button>
            </Link>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
            <div className="font-medium text-slate-900">Why this exists</div>
            <div className="mt-1">
              Most AI resume tools blindly rewrite text. This platform retrieves only evidence-backed experience from structured Experience Banks before generating anything.
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-6">
          <div className="text-sm font-medium text-slate-900">Workflow</div>
          <div className="mt-4 grid gap-3">
            <FlowBlock label="Master Resume" />
            <div className="pl-2 text-slate-400">↓</div>
            <FlowBlock label="Experience Bank" />
            <div className="pl-2 text-slate-400">↓</div>
            <FlowBlock label="Semantic Retrieval" />
            <div className="pl-2 text-slate-400">↓</div>
            <FlowBlock label="Verified Tailoring" />
            <div className="pl-2 text-slate-400">↓</div>
            <FlowBlock label="LaTeX Resume Workspace" />
            <div className="pl-2 text-slate-400">↓</div>
            <FlowBlock label="PDF Export" />
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">What you get</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Experience Banks</CardTitle>
              <CardDescription>Upload once. Reuse forever.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-700">
              Your bank becomes the source-of-truth for tailoring. You don’t repeatedly upload resumes per job.
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Evidence-Grounded Tailoring</CardTitle>
              <CardDescription>Retrieval + verification + assembly.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-700">Only verified evidence is assembled into role-relevant bullets.</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Traceability</CardTitle>
              <CardDescription>Audit every bullet.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-700">
              Generated bullets map back to evidence so you can review, edit, and export with confidence.
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="text-lg font-semibold">Next step</div>
        <p className="mt-1 text-sm text-slate-700">Start by creating an Experience Bank from your master resume.</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/banks/create">
            <Button>Create Experience Bank</Button>
          </Link>
          <Link href="/tailor">
            <Button variant="outline">Tailor Resume</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}

