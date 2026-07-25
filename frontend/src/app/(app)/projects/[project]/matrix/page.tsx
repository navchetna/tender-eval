import { MatrixView } from "@/components/MatrixView";

export default async function MatrixPage({ params }: { params: Promise<{ project: string }> }) {
  const { project } = await params;
  return <MatrixView projectId={project} />;
}
