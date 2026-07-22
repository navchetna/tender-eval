import { parseToc } from "@/lib/toc";

export function TocPicker({ toc, onSelect }: { toc: string; onSelect: (heading: string) => void }) {
  const entries = parseToc(toc);
  if (entries.length === 0) return null;

  return (
    <div className="max-h-[160px] w-full overflow-auto rounded-[9px] border-[0.5px] border-line bg-surface2 p-1">
      {entries.map((entry, i) => (
        <button
          type="button"
          key={i}
          onClick={() => onSelect(entry.text)}
          style={{ paddingLeft: `${Math.max(entry.level - 1, 0) * 14 + 8}px` }}
          className="block w-full cursor-pointer rounded-md px-2 py-1 text-left text-[12px] text-ink-soft hover:bg-surface hover:text-ink"
        >
          {entry.text}
        </button>
      ))}
    </div>
  );
}
