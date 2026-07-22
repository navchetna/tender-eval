// Parses the raw TOC text stored on file_repository.parse_toc — lines are "level;heading text"
// (see pydantic_backend/evaluation/groq_client.py and tree_utils.py, which use this exact format
// to detect and later re-locate sections). Correction headings must match the text part verbatim.
export interface TocEntry {
  level: number;
  text: string;
}

export function parseToc(raw: string): TocEntry[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const idx = line.indexOf(";");
      if (idx === -1) return { level: 0, text: line };
      const level = Number(line.slice(0, idx));
      const text = line.slice(idx + 1).trim();
      return Number.isFinite(level) ? { level, text } : { level: 0, text: line };
    });
}
