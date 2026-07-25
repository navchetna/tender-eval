import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronRight } from "lucide-react";
import { getFileImageBlobUrl, getFileImageNames } from "@/lib/api";
import { Empty } from "@/components/ui/Empty";
import { Pill } from "@/components/ui/Pill";
import { toneClasses } from "@/lib/tone";
import type { DocumentTree, DocumentTreeNode, Tone, TreeContentItem, TreeContentType } from "@/lib/types";

// Renders the parser's output_tree.json as a navigable document structure — headings you can
// expand/collapse, with a filter to isolate just the text, tables, or extracted images, instead
// of a flat dump of the raw JSON.

type Filter = "all" | "text" | "table" | "image";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "text", label: "Text" },
  { key: "table", label: "Tables" },
  { key: "image", label: "Images" },
];

const TYPE_TONE: Record<TreeContentType, Tone> = { text: "info", table: "ok", image: "warn" };

// Cycled by tree depth so every heading at the same level shares a color, making the
// hierarchy scannable at a glance. "bad" (red) is left out — that's reserved for error states
// elsewhere in the app.
const DEPTH_TONES: Tone[] = ["info", "ok", "warn", "none"];

// Tailwind's scanner needs literal class names, not `border-${tone}-dot` template strings.
const TONE_BORDER: Record<Tone, string> = {
  info: "border-info-dot",
  ok: "border-ok-dot",
  warn: "border-warn-dot",
  bad: "border-bad-dot",
  none: "border-none-dot",
};

const TEXT_PREVIEW_LENGTH = 4000;

function firstChildEntry(child: Record<string, DocumentTreeNode>): [string, DocumentTreeNode] | null {
  const entry = Object.entries(child)[0];
  return entry ?? null;
}

function nodeMatches(node: DocumentTreeNode, filter: Filter): boolean {
  if (filter === "all") return true;
  if (node.content.some((item) => item.type === filter)) return true;
  return node.children.some((child) => {
    const entry = firstChildEntry(child);
    return entry ? nodeMatches(entry[1], filter) : false;
  });
}

function flattenTables(node: DocumentTreeNode, path: string, depth: number): { path: string; item: TreeContentItem; depth: number }[] {
  const results: { path: string; item: TreeContentItem; depth: number }[] = [];
  for (const item of node.content) {
    if (item.type === "table") results.push({ path, item, depth });
  }
  for (const child of node.children) {
    const entry = firstChildEntry(child);
    if (entry) results.push(...flattenTables(entry[1], `${path} / ${entry[0]}`, depth + 1));
  }
  return results;
}

const markdownComponents = {
  p: ({ children }: { children?: React.ReactNode }) => <p className="mb-2 last:mb-0">{children}</p>,
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-[12px]">{children}</table>
    </div>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th className="border-[0.5px] border-line-strong bg-surface px-[8px] py-[5px] text-left font-semibold text-ink">{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td className="border-[0.5px] border-line px-[8px] py-[5px] align-top text-ink-soft">{children}</td>
  ),
};

function ContentBlock({ item, tone }: { item: TreeContentItem; tone: Tone }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = item.type !== "table" && item.content.length > TEXT_PREVIEW_LENGTH;
  const text = isLong && !expanded ? `${item.content.slice(0, TEXT_PREVIEW_LENGTH)}…` : item.content;
  const c = toneClasses[tone];

  return (
    <div className={`rounded-[9px] border-[0.5px] ${TONE_BORDER[tone]} ${c.bg} p-[10px]`}>
      <div className="mb-[8px] flex items-center gap-[8px]">
        <Pill tone={TYPE_TONE[item.type]} mono>
          {item.type}
        </Pill>
        {isLong && (
          <button
            type="button"
            className="cursor-pointer text-[11px] font-medium text-accent"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Show less" : `Show all (${item.content.length.toLocaleString()} chars)`}
          </button>
        )}
      </div>
      {item.type === "table" ? (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {item.content}
        </ReactMarkdown>
      ) : (
        <pre className="m-0 font-mono text-[12px] leading-[1.6] whitespace-pre-wrap text-ink-soft">{text}</pre>
      )}
    </div>
  );
}

function TreeNode({ node, title, depth, filter }: { node: DocumentTreeNode; title: string; depth: number; filter: Filter }) {
  if (!nodeMatches(node, filter)) return null;

  const items = node.content.filter((item) => filter === "all" || item.type === filter);
  const children = node.children.map(firstChildEntry).filter((entry): entry is [string, DocumentTreeNode] => entry !== null);
  const tone = DEPTH_TONES[depth % DEPTH_TONES.length];
  const c = toneClasses[tone];

  return (
    <details open={depth === 0} className="group mb-[6px]">
      <summary
        className={`flex cursor-pointer list-none items-center gap-[8px] rounded-[7px] border-[0.5px] ${TONE_BORDER[tone]} ${c.bg} px-[10px] py-[7px] text-[12.5px] font-medium text-ink`}
      >
        <span className={`h-[7px] w-[7px] shrink-0 rounded-full ${c.dot}`} />
        <ChevronRight size={13} className="shrink-0 text-ink-faint transition-transform group-open:rotate-90" />
        <span className="truncate">{title}</span>
      </summary>
      <div className="mt-[6px] ml-[10px] flex flex-col gap-[8px] border-l-[0.5px] border-line pl-[12px]">
        {items.map((item, idx) => (
          <ContentBlock key={idx} item={item} tone={tone} />
        ))}
        {children.map(([key, value]) => (
          <TreeNode key={key} node={value} title={key} depth={depth + 1} filter={filter} />
        ))}
      </div>
    </details>
  );
}

function TreeImage({ projectId, fileId, name }: { projectId: string; fileId: string; name: string }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    getFileImageBlobUrl(projectId, fileId, name)
      .then((blobUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        objectUrl = blobUrl;
        setUrl(blobUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, fileId, name]);

  return (
    <div className="rounded-[9px] border-[0.5px] border-line bg-surface2 p-[10px]">
      <div className="mb-[8px] flex items-center gap-[8px]">
        <Pill tone="warn" mono>
          image
        </Pill>
        <span className="truncate font-mono text-[11px] text-ink-faint">{name}</span>
      </div>
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={name} className="max-h-[420px] w-auto rounded-[7px] shadow-sm" />
      ) : (
        <div className="flex h-[120px] items-center justify-center text-[12px] text-ink-faint">Loading…</div>
      )}
    </div>
  );
}

export function ParsedTreeView({ tree, projectId, fileId }: { tree: unknown; projectId: string; fileId: string }) {
  const data = tree as DocumentTree | null;
  const [filter, setFilter] = useState<Filter>("all");
  const [imageNames, setImageNames] = useState<string[] | null>(null);

  useEffect(() => {
    if (filter !== "image") return;
    let cancelled = false;
    getFileImageNames(projectId, fileId).then((names) => {
      if (!cancelled) setImageNames(names);
    });
    return () => {
      cancelled = true;
    };
  }, [filter, projectId, fileId]);

  return (
    <div>
      <div className="mb-3 flex items-center gap-[6px]">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            className={`cursor-pointer rounded-[7px] border-[0.5px] px-[11px] py-[5px] text-[12px] font-medium transition-colors ${
              filter === key
                ? "border-accent bg-accent-bg text-accent-ink"
                : "border-line-strong bg-surface text-ink-soft hover:bg-surface2"
            }`}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {!data?.root ? (
        <Empty>No parsed tree available yet.</Empty>
      ) : filter === "image" ? (
        imageNames === null ? (
          <div className="text-[12.5px] text-ink-faint">Loading images…</div>
        ) : imageNames.length === 0 ? (
          <Empty>No images extracted from this document.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-[10px] sm:grid-cols-2">
            {imageNames.map((name) => (
              <TreeImage key={name} projectId={projectId} fileId={fileId} name={name} />
            ))}
          </div>
        )
      ) : filter === "table" ? (
        (() => {
          const tables = flattenTables(data.root, "Document", 0);
          return tables.length === 0 ? (
            <Empty>No tables found in this document.</Empty>
          ) : (
            <div className="flex flex-col gap-[12px]">
              {tables.map(({ path, item, depth }, idx) => (
                <div key={idx}>
                  <div className="mb-[4px] truncate font-mono text-[11px] text-ink-faint">{path}</div>
                  <ContentBlock item={item} tone={DEPTH_TONES[depth % DEPTH_TONES.length]} />
                </div>
              ))}
            </div>
          );
        })()
      ) : (
        <TreeNode node={data.root} title="Document" depth={0} filter={filter} />
      )}
    </div>
  );
}
