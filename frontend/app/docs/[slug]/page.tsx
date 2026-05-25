"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";

import { getDoc } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DocDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug);
  const q = useQuery({ queryKey: ["doc", slug], queryFn: () => getDoc(slug) });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{q.data?.title ?? "Doc"}</h1>
          <p className="mt-1 text-sm text-slate-700">Workflow-first guidance.</p>
        </div>
        <Link href="/docs">
          <Button variant="outline">Back to docs</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recommended next step</CardTitle>
          <CardDescription>Keep moving through the workflow.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Link href="/banks/create">
            <Button>Create Bank</Button>
          </Link>
          <Link href="/tailor">
            <Button variant="secondary">Tailor Resume</Button>
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="prose prose-slate max-w-none p-6">
          {q.isLoading ? <div>Loading…</div> : null}
          {q.error ? <div className="text-red-600">{String(q.error)}</div> : null}
          {q.data?.content ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.data.content}</ReactMarkdown> : null}
        </CardContent>
      </Card>
    </div>
  );
}

