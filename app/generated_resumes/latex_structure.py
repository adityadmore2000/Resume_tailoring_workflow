from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LatexStructureError:
    message: str
    line: int | None = None


@dataclass(frozen=True)
class LatexFix:
    message: str
    line: int | None = None


@dataclass(frozen=True)
class LatexStructureResult:
    ok: bool
    errors: list[LatexStructureError] = field(default_factory=list)
    fixed_tex: str | None = None
    fixes: list[LatexFix] = field(default_factory=list)


_BEGIN_ITEMIZE_RE = re.compile(r"\\begin\{itemize\}")
_END_ITEMIZE_RE = re.compile(r"\\end\{itemize\}")

_BEGIN_DOC_RE = re.compile(r"\\begin\{document\}")
_END_DOC_RE = re.compile(r"\\end\{document\}")

_MACRO_START = {
    "resumeItemListStart": "resumeItemList",
    "resumeSubHeadingListStart": "resumeSubHeadingList",
}
_MACRO_END = {
    "resumeItemListEnd": "resumeItemList",
    "resumeSubHeadingListEnd": "resumeSubHeadingList",
}

_MACRO_CALL_RE = re.compile(r"\\(?P<name>resumeItemListStart|resumeItemListEnd|resumeSubHeadingListStart|resumeSubHeadingListEnd)\b")


def validate_and_fix_latex_structure(tex: str, *, _depth: int = 0) -> LatexStructureResult:
    """
    Deterministic LaTeX structure validation + safe auto-fix.

    Validates:
    - begin/end document counts
    - itemize begin/end matching
    - resume list macros start/end matching
    - no open list env reaches \\end{document}

    Safe fixes:
    - If a resumeItemListStart is still open at \\end{document}, insert \\resumeItemListEnd before it.
    - If a resumeSubHeadingListStart is still open at \\end{document}, insert \\resumeSubHeadingListEnd before it.
    - Same for raw \\begin{itemize} stacks (insert \\end{itemize}).

    Notes:
    - We do not attempt complex repairs (nested mismatch, wrong ordering, etc.).
    - Fixes are only applied at end-of-document boundaries.
    """
    raw = tex or ""
    lines = raw.splitlines()

    begin_doc = 0
    end_doc = 0
    stack: list[tuple[str, int]] = []  # (kind, line_no)
    errors: list[LatexStructureError] = []

    for idx, line in enumerate(lines, start=1):
        # Document markers
        if _BEGIN_DOC_RE.search(line):
            begin_doc += 1
        if _END_DOC_RE.search(line):
            end_doc += 1

        # Raw itemize
        if _BEGIN_ITEMIZE_RE.search(line):
            stack.append(("itemize", idx))
        if _END_ITEMIZE_RE.search(line):
            # pop the last itemize
            for j in range(len(stack) - 1, -1, -1):
                if stack[j][0] == "itemize":
                    stack.pop(j)
                    break
            else:
                errors.append(LatexStructureError(message="Found \\end{itemize} without matching \\begin{itemize}.", line=idx))

        # Resume macros
        for m in _MACRO_CALL_RE.finditer(line):
            name = m.group("name")
            if name in _MACRO_START:
                stack.append((_MACRO_START[name], idx))
            elif name in _MACRO_END:
                kind = _MACRO_END[name]
                for j in range(len(stack) - 1, -1, -1):
                    if stack[j][0] == kind:
                        stack.pop(j)
                        break
                else:
                    errors.append(LatexStructureError(message=f"Found \\{name} without matching start.", line=idx))

    if begin_doc != 1 or end_doc != 1:
        errors.append(
            LatexStructureError(
                message=f"Document markers invalid: expected exactly 1 \\\\begin{{document}} and 1 \\\\end{{document}} (got {begin_doc} / {end_doc}).",
                line=None,
            )
        )

    # If stack is empty and no errors, we're done.
    if not errors and not stack:
        return LatexStructureResult(ok=True, errors=[], fixed_tex=None, fixes=[])

    # Attempt safe end-of-document fixes: insert closures right before the final \end{document}.
    end_doc_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if "\\end{document}" in lines[i]:
            end_doc_idx = i
            break

    fixes: list[LatexFix] = []
    fixed_tex: str | None = None

    if end_doc_idx is not None and stack:
        insertions: list[str] = []
        # Close in reverse open order.
        for kind, opened_line in reversed(stack):
            if kind == "resumeItemList":
                insertions.append("\\resumeItemListEnd")
                fixes.append(LatexFix(message="Auto-inserted \\resumeItemListEnd before \\end{document}.", line=end_doc_idx + 1))
            elif kind == "resumeSubHeadingList":
                insertions.append("\\resumeSubHeadingListEnd")
                fixes.append(LatexFix(message="Auto-inserted \\resumeSubHeadingListEnd before \\end{document}.", line=end_doc_idx + 1))
            elif kind == "itemize":
                insertions.append("\\end{itemize}")
                fixes.append(LatexFix(message="Auto-inserted \\end{itemize} before \\end{document}.", line=end_doc_idx + 1))
            else:
                # Unknown open kind -> don't guess.
                errors.append(LatexStructureError(message=f"Unclosed environment detected but not auto-fixable: {kind}", line=opened_line))

        if insertions:
            new_lines = list(lines)
            new_lines[end_doc_idx:end_doc_idx] = insertions + [""]
            fixed_tex = "\n".join(new_lines) + ("\n" if raw.endswith("\n") else "")

    # Re-validate after fix if we produced a fixed tex.
    if fixed_tex is not None:
        # Prevent runaway recursion if input is too malformed for our safe fix strategy.
        if _depth >= 1:
            return LatexStructureResult(ok=False, errors=errors, fixed_tex=fixed_tex, fixes=fixes)
        again = validate_and_fix_latex_structure(fixed_tex, _depth=_depth + 1)
        if again.ok:
            return LatexStructureResult(ok=True, errors=[], fixed_tex=fixed_tex, fixes=fixes)
        errors.extend(again.errors)

    return LatexStructureResult(ok=False, errors=errors, fixed_tex=fixed_tex, fixes=fixes)
