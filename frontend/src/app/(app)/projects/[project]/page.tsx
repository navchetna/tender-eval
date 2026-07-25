import { Workspace } from "@/components/Workspace";

export default async function ProjectPage({ params }: { params: Promise<{ project: string }> }) {
  const { project } = await params;
  return <Workspace projectId={project} />;
}
