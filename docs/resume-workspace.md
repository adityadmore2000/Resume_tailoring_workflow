# Resume Workspace

## What this does
Lets you review and export the generated resume:
- PDF Preview (read-only)
- LaTeX Source (editable)
- Tailored Markdown/Text (read-only artifacts)
- Traceability
- Compile Logs

## Why it exists
You need a professional review surface to edit output deterministically and export recruiter-ready PDFs.

## Step-by-step usage
1. Open **Workspace** after tailoring (or via `resume_id` link).
2. Edit in **LaTeX Source**.
3. Click **Recompile** to update **PDF Preview**.
4. Audit **Traceability**.
5. Export PDF.

## What happens internally
- LaTeX is stored per `resume_id`.
- Compilation produces a PDF and logs; failures preserve the last successful PDF if present.

## Common mistakes
- Exporting before compiling (no PDF exists yet).
- Ignoring compile logs after LaTeX edits.
- Editing bullets without checking traceability.

## Recommended next steps
- Tailor another role using the same bank, or update your master resume and recreate the bank if key evidence is missing.
