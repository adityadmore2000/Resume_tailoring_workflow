"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { listDocs } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function DocsLandingPage() {
  const q = useQuery({ queryKey: ["docs"], queryFn: listDocs });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Docs</h1>
        <p className="mt-1 text-sm text-slate-700">Workflow-oriented documentation designed to be read inside the product.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recommended workflow</CardTitle>
          <CardDescription>Resume → Experience Bank → Retrieval → Tailored Resume → Workspace → PDF Export</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link href="/banks/create">
            <Button>Create Bank</Button>
          </Link>
          <Link href="/banks">
            <Button variant="outline">Preview Banks</Button>
          </Link>
          <Link href="/tailor">
            <Button variant="secondary">Tailor</Button>
          </Link>
        </CardContent>
      </Card>

      {q.isLoading ? <div className="text-sm text-slate-600">Loading docs…</div> : null}
      {q.error ? <div className="text-sm text-red-600">{String(q.error)}</div> : null}

      <div className="grid gap-4 md:grid-cols-2">
        {q.data?.docs?.map((d) => (
          <Card key={d.slug}>
            <CardHeader>
              <CardTitle>{d.title}</CardTitle>
              <CardDescription>/docs/{d.slug}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link href={`/docs/${encodeURIComponent(d.slug)}`}>
                <Button variant="secondary">Open</Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

