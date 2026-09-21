#!/usr/bin/env python3
"""
Split "use client" pages that export `metadata` into:
  page.tsx      (Server Component: exports metadata, renders the view)
  page-view.tsx ("use client" view: everything else, default export kept)

This is the official Next.js pattern for per-page metadata on interactive
pages. Idempotent: files already split (no metadata in a "use client" page)
are skipped.
"""
import re
import pathlib

ROOT = pathlib.Path("/home/z/my-project/src/app")

META_IMPORT_RE = re.compile(
    r'^import type \{[^}]*Metadata[^}]*\} from "next";\n', re.MULTILINE
)
META_EXPORT_RE = re.compile(r"export const metadata(?::\s*Metadata)?\s*=")
DEFAULT_FN_RE = re.compile(r"export default function (\w+)")


def extract_metadata(content: str) -> tuple[str, str]:
    """Return (metadata_object_literal, content_without_export).

    Uses string-aware brace matching from the first `{` after the `=`.
    """
    m = META_EXPORT_RE.search(content)
    if not m:
        raise ValueError("no metadata export")
    brace_start = content.index("{", m.end() - 1)
    depth = 0
    i = brace_start
    in_str = None
    while i < len(content):
        c = content[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if depth != 0:
        raise ValueError("unbalanced braces in metadata")
    meta_obj = content[brace_start : i + 1]
    # consume trailing semicolon + up to one trailing newline pair
    end = i + 1
    if end < len(content) and content[end] == ";":
        end += 1
    while end < len(content) and content[end] in "\n":
        # keep at most one blank line separation
        if content[end:].startswith("\n\n\n"):
            break
        end += 1
        if end < len(content) and content[end] not in "\n":
            break
    rest = content[:m.start()] + content[end:]
    # collapse >2 consecutive newlines left at the seam
    rest = re.sub(r"\n{3,}", "\n\n", rest)
    return meta_obj, rest


def main() -> None:
    changed = []
    for f in sorted(ROOT.rglob("page.tsx")):
        content = f.read_text(encoding="utf-8")
        if '"use client"' not in content or "export const metadata" not in content:
            continue
        meta_obj, view_content = extract_metadata(content)
        # strip the Metadata type import from the client view
        view_content = META_IMPORT_RE.sub("", view_content)
        view_content = re.sub(r"\n{3,}", "\n\n", view_content)
        if not view_content.lstrip().startswith('"use client"'):
            raise ValueError(f"{f}: view lost its 'use client' directive")
        fn = DEFAULT_FN_RE.search(view_content)
        if not fn:
            raise ValueError(f"{f}: no default export function found")
        comp = fn.group(1)

        view_path = f.with_name("page-view.tsx")
        view_path.write_text(view_content, encoding="utf-8")

        page = (
            "import type { Metadata } from \"next\";\n"
            f"import {comp} from \"./page-view\";\n"
            "\n"
            f"export const metadata: Metadata = {meta_obj};\n"
            "\n"
            f"export default function Page() {{\n"
            f"  return <{comp} />;\n"
            "}\n"
        )
        f.write_text(page, encoding="utf-8")
        changed.append(str(f.relative_to(f.parents[3])))
    print(f"split {len(changed)} pages:")
    for c in changed:
        print(f"  {c}")


if __name__ == "__main__":
    main()
