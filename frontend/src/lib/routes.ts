// Project pages take the project id as a query parameter rather than a dynamic route segment
// (/projects/[project]): ids only exist at runtime, and the desktop build is a static export
// (NEXT_OUTPUT=export), which can only prerender dynamic segments listed at build time.

export const projectHref = (projectId: string) => `/projects/view?id=${encodeURIComponent(projectId)}`;

export const matrixHref = (projectId: string) => `/projects/matrix?id=${encodeURIComponent(projectId)}`;
