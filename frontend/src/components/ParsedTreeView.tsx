import { JsonView, defaultStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";

// Renders the parser's raw output_tree.json as an interactive, collapsible JSON tree — the
// actual JSON structure, not a markdown/prose rendering of its text content.
const treeStyles = {
  ...defaultStyles,
  container: `${defaultStyles.container} font-mono text-[11.5px]`,
};

export function ParsedTreeView({ tree }: { tree: unknown }) {
  const data = tree as Record<string, unknown> | unknown[];
  return <JsonView data={data} style={treeStyles} shouldExpandNode={(level) => level < 2} />;
}
