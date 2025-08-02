// // // import React, { useState } from 'react';
// // // import { Button } from '@/components/ui/button';
// // // import { Badge } from '@/components/ui/badge';
// // // import { Input } from '@/components/ui/input';
// // // import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
// // // import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
// // // import { 
// // //   FolderPlus, 
// // //   Folder, 
// // //   FolderOpen,
// // //   FileText, 
// // //   Upload, 
// // //   Plus,
// // //   Trash2,
// // //   ChevronRight,
// // //   ChevronDown,
// // //   X,
// // //   ChevronLeft,
// // //   ChevronLeftCircle
// // // } from 'lucide-react';
// // // import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

// // // interface ProjectFile {
// // //   id: string;
// // //   name: string;
// // //   type: 'tender' | 'bid';
// // //   bidderName?: string;
// // //   uploadDate: string;
// // // }

// // // interface Project {
// // //   id: string;
// // //   name: string;
// // //   tenderFile?: ProjectFile;
// // //   bidFiles: ProjectFile[];
// // //   createdAt: string;
// // //   status: 'draft' | 'processing' | 'completed';
// // // }

// // // interface ProjectSidebarProps {
// // //   projects: Project[];
// // //   activeProject: string | null;
// // //   onProjectSelect: (projectId: string | null) => void;
// // //   onProjectCreate: (name: string) => void;
// // //   onFileUpload: (projectId: string, files: File[], type: 'tender' | 'bid', bidderName?: string) => void;
// // //   onProjectDelete?: (projectId: string) => void;
// // //   onFileDelete?: (projectId: string, fileId: string, type: 'tender' | 'bid') => void;
// // //   isCollapsed: boolean;
// // //   onToggleCollapse: () => void;
// // // }

// // // const ProjectSidebar = ({ 
// // //   projects, 
// // //   activeProject, 
// // //   onProjectSelect, 
// // //   onProjectCreate,
// // //   onFileUpload,
// // //   onProjectDelete,
// // //   onFileDelete,
// // //   isCollapsed,
// // //   onToggleCollapse
// // // }: ProjectSidebarProps) => {
// // //   const [newProjectName, setNewProjectName] = useState('');
// // //   const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
// // //   const [uploadType, setUploadType] = useState<'tender' | 'bid'>('tender');
// // //   const [bidderName, setBidderName] = useState('');
// // //   const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set());

// // //   const handleCreateProject = () => {
// // //     if (newProjectName.trim()) {
// // //       onProjectCreate(newProjectName.trim());
// // //       setNewProjectName('');
// // //       setIsCreateDialogOpen(false);
// // //     }
// // //   };

// // //   const handleFileUpload = (projectId: string, event: React.ChangeEvent<HTMLInputElement>) => {
// // //     const files = Array.from(event.target.files || []);
// // //     if (files.length > 0) {
// // //       onFileUpload(projectId, files, uploadType, uploadType === 'bid' ? bidderName : undefined);
// // //       setBidderName('');
// // //     }
// // //   };

// // //   const toggleProjectExpansion = (projectId: string) => {
// // //     const newExpanded = new Set(expandedProjects);
// // //     if (newExpanded.has(projectId)) {
// // //       newExpanded.delete(projectId);
// // //     } else {
// // //       newExpanded.add(projectId);
// // //     }
// // //     setExpandedProjects(newExpanded);
// // //   };

// // //   const handleProjectDelete = (projectId: string, e: React.MouseEvent) => {
// // //     e.stopPropagation();
// // //     if (confirm('Are you sure you want to delete this project?')) {
// // //       onProjectDelete?.(projectId);
// // //       if (activeProject === projectId) {
// // //         onProjectSelect(null);
// // //       }
// // //     }
// // //   };

// // //   const handleFileDelete = (projectId: string, fileId: string, type: 'tender' | 'bid', e: React.MouseEvent) => {
// // //     e.stopPropagation();
// // //     if (confirm('Are you sure you want to delete this file?')) {
// // //       onFileDelete?.(projectId, fileId, type);
// // //     }
// // //   };

// // //   const getStatusColor = (status: string) => {
// // //     switch (status) {
// // //       case 'completed': return 'text-green-500';
// // //       case 'processing': return 'text-yellow-500';
// // //       case 'draft': return 'text-gray-500';
// // //       default: return 'text-gray-500';
// // //     }
// // //   };

// // //   if (isCollapsed) {
// // //     return (
// // //       <div className="w-12 h-full border-r bg-background flex flex-col">
// // //         <div className="p-2 border-b bg-muted/30">
// // //           <Button 
// // //             size="sm" 
// // //             variant="ghost" 
// // //             className="h-8 w-8 p-0"
// // //             onClick={onToggleCollapse}
// // //           >
// // //             <ChevronRight className="h-4 w-4" />
// // //           </Button>
// // //         </div>
// // //         <div className="flex-1 flex flex-col items-center py-2 gap-2">
// // //           {projects.map((project) => (
// // //             <Button
// // //               key={project.id}
// // //               size="sm"
// // //               variant={activeProject === project.id ? "secondary" : "ghost"}
// // //               className="h-8 w-8 p-0"
// // //               onClick={() => onProjectSelect(project.id)}
// // //               title={project.name}
// // //             >
// // //               <Folder className="h-4 w-4" />
// // //             </Button>
// // //           ))}
// // //         </div>
// // //       </div>
// // //     );
// // //   }

// // //   return (
// // //     <div className="w-80 h-full border-r bg-background flex flex-col">
// // //       {/* Header */}
// // //       <div className="p-3 border-b bg-muted/30">
// // //         <div className="flex items-center justify-between mb-2">
// // //           <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Explorer</h2>
// // //           <div className="flex items-center gap-1">
// // //             <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
// // //               <DialogTrigger asChild>
// // //                 <Button size="sm" variant="ghost" className="h-6 w-6 p-0">
// // //                   <FolderPlus className="h-4 w-4" />
// // //                 </Button>
// // //               </DialogTrigger>
// // //               <DialogContent>
// // //                 <DialogHeader>
// // //                   <DialogTitle>Create New Project</DialogTitle>
// // //                 </DialogHeader>
// // //                 <div className="space-y-4">
// // //                   <Input
// // //                     placeholder="Project name"
// // //                     value={newProjectName}
// // //                     onChange={(e) => setNewProjectName(e.target.value)}
// // //                     onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
// // //                   />
// // //                   <Button onClick={handleCreateProject} className="w-full">
// // //                     Create Project
// // //                   </Button>
// // //                 </div>
// // //               </DialogContent>
// // //             </Dialog>
// // //             <Button 
// // //               size="sm" 
// // //               variant="ghost" 
// // //               className="h-6 w-6 p-0"
// // //               onClick={onToggleCollapse}
// // //             >
// // //               <ChevronLeft className="h-4 w-4" />
// // //             </Button>
// // //           </div>
// // //         </div>
// // //         <Button 
// // //           variant={activeProject === null ? "secondary" : "ghost"} 
// // //           size="sm" 
// // //           onClick={() => onProjectSelect(null)}
// // //           className="w-full justify-start h-7 text-xs font-normal"
// // //         >
// // //           <Folder className="h-3 w-3 mr-2" />
// // //           All Projects
// // //         </Button>
// // //       </div>

// // //       {/* Projects List */}
// // //       <div className="flex-1 overflow-y-auto">
// // //         {projects.map((project) => {
// // //           const isExpanded = expandedProjects.has(project.id);
// // //           const isActive = activeProject === project.id;
// // //           const hasFiles = project.tenderFile || project.bidFiles.length > 0;
          
// // //           return (
// // //             <div key={project.id} className="select-none">
// // //               {/* Project Header */}
// // //               <div 
// // //                 className={`flex items-center pr-2 pl-1 py-1 text-sm cursor-pointer hover:bg-muted/50 group ${
// // //                   isActive ? 'bg-muted' : ''
// // //                 }`}
// // //                 onClick={() => onProjectSelect(project.id)}
// // //               >
// // //                 <Button
// // //                   variant="ghost"
// // //                   size="sm"
// // //                   className="h-5 w-5 p-0 mr-1"
// // //                   onClick={(e) => {
// // //                     e.stopPropagation();
// // //                     toggleProjectExpansion(project.id);
// // //                   }}
// // //                 >
// // //                   {hasFiles ? (
// // //                     isExpanded ? (
// // //                       <ChevronDown className="h-3 w-3" />
// // //                     ) : (
// // //                       <ChevronRight className="h-3 w-3" />
// // //                     )
// // //                   ) : null}
// // //                 </Button>
                
// // //                 <div className="flex items-center flex-1 min-w-0">
// // //                   {isExpanded ? (
// // //                     <FolderOpen className="h-4 w-4 mr-2 text-blue-500 flex-shrink-0" />
// // //                   ) : (
// // //                     <Folder className="h-4 w-4 mr-2 text-blue-500 flex-shrink-0" />
// // //                   )}
// // //                   <span className="truncate font-medium">{project.name}</span>
// // //                 </div>

// // //                 <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
// // //                   <Badge variant="outline" className={`text-xs h-4 px-1 ${getStatusColor(project.status)}`}>
// // //                     {project.status}
// // //                   </Badge>
// // //                   <DropdownMenu>
// // //                     <DropdownMenuTrigger asChild>
// // //                       <Button variant="ghost" size="sm" className="h-5 w-5 p-0">
// // //                         <Plus className="h-3 w-3" />
// // //                       </Button>
// // //                     </DropdownMenuTrigger>
// // //                     <DropdownMenuContent align="end" className="w-48">
// // //                       <DropdownMenuItem asChild>
// // //                         <label className="cursor-pointer flex items-center w-full">
// // //                           <Upload className="h-3 w-3 mr-2" />
// // //                           Upload Tender
// // //                           <input
// // //                             type="file"
// // //                             accept=".pdf"
// // //                             className="hidden"
// // //                             onChange={(e) => {
// // //                               setUploadType('tender');
// // //                               handleFileUpload(project.id, e);
// // //                             }}
// // //                           />
// // //                         </label>
// // //                       </DropdownMenuItem>
// // //                       <DropdownMenuItem asChild>
// // //                         <label className="cursor-pointer flex items-center w-full">
// // //                           <Plus className="h-3 w-3 mr-2" />
// // //                           Add Bidder
// // //                           <input
// // //                             type="file"
// // //                             accept=".pdf"
// // //                             className="hidden"
// // //                             onChange={(e) => {
// // //                               setUploadType('bid');
// // //                               const name = prompt('Enter bidder name:');
// // //                               if (name) {
// // //                                 setBidderName(name);
// // //                                 handleFileUpload(project.id, e);
// // //                               }
// // //                             }}
// // //                           />
// // //                         </label>
// // //                       </DropdownMenuItem>
// // //                       {onProjectDelete && (
// // //                         <DropdownMenuItem 
// // //                           className="text-destructive"
// // //                           onClick={(e) => handleProjectDelete(project.id, e)}
// // //                         >
// // //                           <Trash2 className="h-3 w-3 mr-2" />
// // //                           Delete Project
// // //                         </DropdownMenuItem>
// // //                       )}
// // //                     </DropdownMenuContent>
// // //                   </DropdownMenu>
// // //                 </div>
// // //               </div>

// // //               {/* Project Files */}
// // //               {hasFiles && isExpanded && (
// // //                 <div className="ml-6 border-l border-muted pl-2">
// // //                   {/* Tender File */}
// // //                   {project.tenderFile && (
// // //                     <div className="flex items-center py-1 pr-2 text-sm hover:bg-muted/30 group rounded">
// // //                       <FileText className="h-3 w-3 mr-2 text-green-600 flex-shrink-0" />
// // //                       <span className="truncate text-xs">{project.tenderFile.name}</span>
// // //                       <Badge variant="outline" className="ml-2 text-xs h-4 px-1">
// // //                         Tender
// // //                       </Badge>
// // //                       {onFileDelete && (
// // //                         <Button
// // //                           variant="ghost"
// // //                           size="sm"
// // //                           className="h-4 w-4 p-0 ml-auto opacity-0 group-hover:opacity-100"
// // //                           onClick={(e) => handleFileDelete(project.id, project.tenderFile!.id, 'tender', e)}
// // //                         >
// // //                           <X className="h-3 w-3 text-destructive" />
// // //                         </Button>
// // //                       )}
// // //                     </div>
// // //                   )}

// // //                   {/* Bid Files */}
// // //                   {project.bidFiles.map((file) => (
// // //                     <div key={file.id} className="flex items-center py-1 pr-2 text-sm hover:bg-muted/30 group rounded">
// // //                       <FileText className="h-3 w-3 mr-2 text-orange-600 flex-shrink-0" />
// // //                       <div className="flex-1 min-w-0">
// // //                         <div className="truncate text-xs">{file.name}</div>
// // //                         <div className="truncate text-xs text-muted-foreground">{file.bidderName}</div>
// // //                       </div>
// // //                       <Badge variant="outline" className="ml-2 text-xs h-4 px-1">
// // //                         Bid
// // //                       </Badge>
// // //                       {onFileDelete && (
// // //                         <Button
// // //                           variant="ghost"
// // //                           size="sm"
// // //                           className="h-4 w-4 p-0 ml-1 opacity-0 group-hover:opacity-100"
// // //                           onClick={(e) => handleFileDelete(project.id, file.id, 'bid', e)}
// // //                         >
// // //                           <X className="h-3 w-3 text-destructive" />
// // //                         </Button>
// // //                       )}
// // //                     </div>
// // //                   ))}
// // //                 </div>
// // //               )}
// // //             </div>
// // //           );
// // //         })}
// // //       </div>
// // //     </div>
// // //   );
// // // };

// // // export default ProjectSidebar;
// // import React, { useState, useEffect, useRef } from 'react';
// // import { Button } from "@/components/ui/button";
// // import { Plus, Trash2, File, FolderOpen, FolderClosed, Upload } from "lucide-react";

// // // --- Configuration ---
// // const API_BASE_URL = 'http://localhost:8000';

// // // --- Type Definitions to match the Python API ---
// // interface PDFMetadata {
// //     id: string;
// //     filename: string;
// // }

// // interface ProjectType {
// //     id: string;
// //     name: string;
// //     description?: string | null;
// // }

// // export function ProjectSidebar() {
// //     // --- State Management ---
// //     const [projects, setProjects] = useState<ProjectType[]>([]);
// //     const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
// //     const [projectPdfs, setProjectPdfs] = useState<PDFMetadata[]>([]);
// //     const [selectedPdfId, setSelectedPdfId] = useState<string | null>(null);
    
// //     const [isLoading, setIsLoading] = useState(false);
// //     const [error, setError] = useState<string | null>(null);

// //     const fileInputRef = useRef<HTMLInputElement>(null);

// //     // --- API Call Functions ---

// //     const fetchProjects = async () => {
// //         setIsLoading(true);
// //         setError(null);
// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects`);
// //             if (!response.ok) throw new Error('Failed to fetch projects');
// //             const data = await response.json();
// //             setProjects(data);
// //         } catch (err: any) {
// //             setError(err.message);
// //             console.error(err);
// //         } finally {
// //             setIsLoading(false);
// //         }
// //     };

// //     const handleNewProject = async () => {
// //         const newProjectName = prompt("Enter new project name:", "New Tender Project");
// //         if (!newProjectName) return;

// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects`, {
// //                 method: 'POST',
// //                 headers: { 'Content-Type': 'application/json' },
// //                 body: JSON.stringify({ name: newProjectName, description: "" }),
// //             });
// //             if (!response.ok) throw new Error('Failed to create project');
// //             await fetchProjects(); // Refresh the list
// //         } catch (err: any) {
// //             setError(err.message);
// //             console.error(err);
// //         }
// //     };

// //     const handleDeleteProject = async (projectId: string) => {
// //         if (!window.confirm("Are you sure you want to delete this project and all its data? This cannot be undone.")) return;

// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
// //                 method: 'DELETE',
// //             });
// //             if (!response.ok) throw new Error('Failed to delete project');
            
// //             // Clear selections if the deleted project was selected
// //             if (selectedProjectId === projectId) {
// //                 setSelectedProjectId(null);
// //                 setSelectedPdfId(null);
// //                 setProjectPdfs([]);
// //             }
// //             await fetchProjects(); // Refresh the list
// //         } catch (err: any) {
// //             setError(err.message);
// //             console.error(err);
// //         }
// //     };

// //     const fetchPdfsForProject = async (projectId: string) => {
// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects/${projectId}/pdfs`);
// //             if (!response.ok) throw new Error('Failed to fetch PDFs');
// //             const data = await response.json();
// //             setProjectPdfs(data);
// //         } catch (err: any) {
// //             setError(err.message);
// //             console.error(err);
// //         }
// //     };

// //     const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
// //         const file = event.target.files?.[0];
// //         if (!file || !selectedProjectId) return;

// //         const formData = new FormData();
// //         formData.append('file', file);

// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects/${selectedProjectId}/pdfs`, {
// //                 method: 'POST',
// //                 body: formData,
// //             });
// //             if (!response.ok) throw new Error('Failed to upload PDF');
// //             await fetchPdfsForProject(selectedProjectId); // Refresh PDF list
// //         } catch (err: any) {
// //             setError(err.message);
// //             console.error(err);
// //         } finally {
// //             // Reset file input
// //             if(fileInputRef.current) {
// //                 fileInputRef.current.value = "";
// //             }
// //         }
// //     };
    
// //     const handleDeletePdf = async (pdfId: string) => {
// //         if (!selectedProjectId || !window.confirm("Are you sure you want to delete this document?")) return;
        
// //         try {
// //             const response = await fetch(`${API_BASE_URL}/projects/${selectedProjectId}/pdfs/${pdfId}`, {
// //                 method: 'DELETE',
// //             });
// //              if (!response.ok) throw new Error('Failed to delete PDF');
             
// //             if (selectedPdfId === pdfId) {
// //                 setSelectedPdfId(null);
// //             }
// //              await fetchPdfsForProject(selectedProjectId); // Refresh PDF list
// //         } catch (err: any)
// //         {
// //             setError(err.message);
// //             console.error(err);
// //         }
// //     };

// //     // --- Effects ---

// //     // Initial fetch of projects when component mounts
// //     useEffect(() => {
// //         fetchProjects();
// //     }, []);

// //     // --- Event Handlers ---

// //     const handleProjectSelect = (projectId: string) => {
// //         if (selectedProjectId === projectId) {
// //             // If clicking the same project, collapse it
// //             setSelectedProjectId(null);
// //             setSelectedPdfId(null);
// //             setProjectPdfs([]);
// //         } else {
// //             setSelectedProjectId(projectId);
// //             setSelectedPdfId(null); // Reset PDF selection
// //             fetchPdfsForProject(projectId);
// //         }
// //     };
    
// //     const handlePdfSelect = (pdfId: string) => {
// //          if (selectedPdfId === pdfId) {
// //             // If clicking the same PDF, collapse it
// //             setSelectedPdfId(null);
// //         } else {
// //             setSelectedPdfId(pdfId);
// //         }
// //     };

// //     const triggerUploadForProject = (projectId: string) => {
// //         setSelectedProjectId(projectId); // Ensure the project is selected for upload context
// //         fileInputRef.current?.click();
// //     };

// //     return (
// //         <div className="flex flex-col h-full bg-gray-50 border-r border-gray-200 w-80">
// //             <div className="p-4 border-b border-gray-200">
// //                 <h1 className="text-xl font-bold text-gray-800">Tender Evaluation</h1>
// //             </div>

// //             <div className="p-2">
// //                 <Button onClick={handleNewProject} variant="outline" className="w-full justify-start text-sm">
// //                     <Plus className="mr-2 h-4 w-4" />
// //                     New Project
// //                 </Button>
// //             </div>

// //             {isLoading && <p className="p-4 text-gray-500">Loading projects...</p>}
// //             {error && <p className="p-4 text-red-500">Error: {error}</p>}
            
// //             <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
// //                 {projects.map((project) => (
// //                     <div key={project.id}>
// //                         <div
// //                             onClick={() => handleProjectSelect(project.id)}
// //                             className="flex items-center p-2 text-sm font-medium text-gray-700 rounded-md hover:bg-gray-100 cursor-pointer group"
// //                         >
// //                             {selectedProjectId === project.id ? <FolderOpen className="mr-3 h-5 w-5 flex-shrink-0 text-gray-500" /> : <FolderClosed className="mr-3 h-5 w-5 flex-shrink-0 text-gray-400" />}
// //                             <span className="flex-1">{project.name}</span>
// //                             <Upload 
// //                                 onClick={(e) => { e.stopPropagation(); triggerUploadForProject(project.id); }}
// //                                 className="h-4 w-4 text-gray-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity mr-2" 
// //                             />
// //                             <Trash2 
// //                                 onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
// //                                 className="h-4 w-4 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
// //                             />
// //                         </div>
                        
// //                         {selectedProjectId === project.id && (
// //                              <div className="pl-6 mt-1 space-y-1">
// //                                 <input 
// //                                     type="file" 
// //                                     ref={fileInputRef} 
// //                                     onChange={handleFileUpload} 
// //                                     className="hidden" 
// //                                     accept=".pdf" 
// //                                 />
// //                                 {projectPdfs.map((pdf) => (
// //                                     <div key={pdf.id}>
// //                                         <div
// //                                             onClick={() => handlePdfSelect(pdf.id)}
// //                                             className="flex items-center p-2 text-xs font-medium text-gray-600 rounded-md hover:bg-gray-100 cursor-pointer group"
// //                                         >
// //                                             <File className="mr-3 h-4 w-4 flex-shrink-0 text-gray-400" />
// //                                             <span className="flex-1 truncate">{pdf.filename}</span>
// //                                              <Trash2 
// //                                                 onClick={(e) => { e.stopPropagation(); handleDeletePdf(pdf.id); }}
// //                                                 className="h-3 w-3 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
// //                                             />
// //                                         </div>
// //                                     </div>
// //                                 ))}
// //                              </div>
// //                         )}
// //                     </div>
// //                 ))}
// //             </nav>
// //         </div>
// //     );
// // }
// // export default ProjectSidebar;
// import React, { useState, useEffect, useRef } from 'react';
// import { Button } from "@/components/ui/button";
// import { Plus, Trash2, File, FolderOpen, FolderClosed, Upload, Loader2 } from "lucide-react";

// // --- Configuration ---
// const API_BASE_URL = 'http://localhost:8000';

// // --- Type Definitions to match the Python API ---
// interface PDFMetadata {
//     id: string;
//     filename: string;
// }

// interface ProjectType {
//     id: string;
//     name: string;
//     description?: string | null;
// }

// interface ProjectSidebarProps {
//     onProjectSelect: (projectId: string | null) => void;
// }

// export function ProjectSidebar({ onProjectSelect }: ProjectSidebarProps) {
//     // --- State Management ---
//     const [projects, setProjects] = useState<ProjectType[]>([]);
//     const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
//     const [projectPdfs, setProjectPdfs] = useState<PDFMetadata[]>([]);
//     const [selectedPdfId, setSelectedPdfId] = useState<string | null>(null);
//     const [uploadingFilename, setUploadingFilename] = useState<string | null>(null);
    
//     const [isLoading, setIsLoading] = useState(false);
//     const [error, setError] = useState<string | null>(null);

//     const fileInputRef = useRef<HTMLInputElement>(null);

//     // --- API Call Functions ---

//     const fetchProjects = async () => {
//         setIsLoading(true);
//         setError(null);
//         try {
//             const response = await fetch(`${API_BASE_URL}/projects`);
//             if (!response.ok) throw new Error('Failed to fetch projects');
//             const data = await response.json();
//             setProjects(data);
//         } catch (err: any) {
//             setError(err.message);
//             console.error(err);
//         } finally {
//             setIsLoading(false);
//         }
//     };

//     const handleNewProject = async () => {
//         const newProjectName = prompt("Enter new project name:", "New Tender Project");
//         if (!newProjectName) return;

//         try {
//             const response = await fetch(`${API_BASE_URL}/projects`, {
//                 method: 'POST',
//                 headers: { 'Content-Type': 'application/json' },
//                 body: JSON.stringify({ name: newProjectName, description: "" }),
//             });
//             if (!response.ok) throw new Error('Failed to create project');
//             await fetchProjects(); // Refresh the list
//         } catch (err: any) {
//             setError(err.message);
//             console.error(err);
//         }
//     };

//     const handleDeleteProject = async (projectId: string) => {
//         if (!window.confirm("Are you sure you want to delete this project and all its data? This cannot be undone.")) return;

//         try {
//             const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
//                 method: 'DELETE',
//             });
//             if (!response.ok) throw new Error('Failed to delete project');
            
//             // Clear selections if the deleted project was selected
//             if (selectedProjectId === projectId) {
//                 setSelectedProjectId(null);
//                 setSelectedPdfId(null);
//                 setProjectPdfs([]);
//                 onProjectSelect(null); // Notify parent
//             }
//             await fetchProjects(); // Refresh the list
//         } catch (err: any) {
//             setError(err.message);
//             console.error(err);
//         }
//     };

//     const fetchPdfsForProject = async (projectId: string) => {
//         try {
//             const response = await fetch(`${API_BASE_URL}/projects/${projectId}/pdfs`);
//             if (!response.ok) throw new Error('Failed to fetch PDFs');
//             const data = await response.json();
//             setProjectPdfs(data);
//         } catch (err: any) {
//             setError(err.message);
//             console.error(err);
//         }
//     };

//     const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
//         const file = event.target.files?.[0];
//         if (!file || !selectedProjectId) return;

//         setUploadingFilename(file.name); // Show processing indicator with filename

//         const formData = new FormData();
//         formData.append('file', file);

//         try {
//             const response = await fetch(`${API_BASE_URL}/projects/${selectedProjectId}/pdfs`, {
//                 method: 'POST',
//                 body: formData,
//             });
//             if (!response.ok) throw new Error('Failed to upload PDF');
//             await fetchPdfsForProject(selectedProjectId); // Refresh PDF list
//         } catch (err: any) {
//             setError(err.message);
//             console.error(err);
//         } finally {
//             setUploadingFilename(null); // Hide processing indicator
//             if(fileInputRef.current) {
//                 fileInputRef.current.value = "";
//             }
//         }
//     };
    
//     const handleDeletePdf = async (pdfId: string) => {
//         if (!selectedProjectId || !window.confirm("Are you sure you want to delete this document?")) return;
        
//         try {
//             const response = await fetch(`${API_BASE_URL}/projects/${selectedProjectId}/pdfs/${pdfId}`, {
//                 method: 'DELETE',
//             });
//              if (!response.ok) throw new Error('Failed to delete PDF');
             
//             if (selectedPdfId === pdfId) {
//                 setSelectedPdfId(null);
//             }
//              await fetchPdfsForProject(selectedProjectId); // Refresh PDF list
//         } catch (err: any)
//         {
//             setError(err.message);
//             console.error(err);
//         }
//     };

//     // --- Effects ---

//     // Initial fetch of projects when component mounts
//     useEffect(() => {
//         fetchProjects();
//     }, []);

//     // --- Event Handlers ---

//     const handleProjectSelect = (projectId: string) => {
//         if (selectedProjectId === projectId) {
//             // If clicking the same project, collapse it
//             setSelectedProjectId(null);
//             setSelectedPdfId(null);
//             setProjectPdfs([]);
//             onProjectSelect(null); // Notify parent
//         } else {
//             setSelectedProjectId(projectId);
//             setSelectedPdfId(null); // Reset PDF selection
//             fetchPdfsForProject(projectId);
//             onProjectSelect(projectId); // Notify parent
//         }
//     };
    
//     const handlePdfSelect = (pdfId: string) => {
//          if (selectedPdfId === pdfId) {
//             // If clicking the same PDF, collapse it
//             setSelectedPdfId(null);
//         } else {
//             setSelectedPdfId(pdfId);
//         }
//     };

//     const triggerUploadForProject = (projectId: string) => {
//         setSelectedProjectId(projectId); // Ensure the project is selected for upload context
//         fileInputRef.current?.click();
//     };

//     return (
//         <div className="flex flex-col h-full bg-gray-50 border-r border-gray-200 w-80">
//             <div className="p-4 border-b border-gray-200">
//                 <h1 className="text-xl font-bold text-gray-800">Tender Evaluation</h1>
//             </div>

//             <div className="p-2">
//                 <Button onClick={handleNewProject} variant="outline" className="w-full justify-start text-sm">
//                     <Plus className="mr-2 h-4 w-4" />
//                     New Project
//                 </Button>
//             </div>

//             {isLoading && <p className="p-4 text-gray-500">Loading projects...</p>}
//             {error && <p className="p-4 text-red-500">Error: {error}</p>}
            
//             <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
//                 {projects.map((project) => (
//                     <div key={project.id}>
//                         <div
//                             onClick={() => handleProjectSelect(project.id)}
//                             className="flex items-center p-2 text-sm font-medium text-gray-700 rounded-md hover:bg-gray-100 cursor-pointer group"
//                         >
//                             {selectedProjectId === project.id ? <FolderOpen className="mr-3 h-5 w-5 flex-shrink-0 text-gray-500" /> : <FolderClosed className="mr-3 h-5 w-5 flex-shrink-0 text-gray-400" />}
//                             <span className="flex-1">{project.name}</span>
//                             <Upload 
//                                 onClick={(e) => { e.stopPropagation(); triggerUploadForProject(project.id); }}
//                                 className="h-4 w-4 text-gray-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity mr-2" 
//                             />
//                             <Trash2 
//                                 onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
//                                 className="h-4 w-4 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
//                             />
//                         </div>
                        
//                         {selectedProjectId === project.id && (
//                              <div className="pl-6 mt-1 space-y-1">
//                                 <input 
//                                     type="file" 
//                                     ref={fileInputRef} 
//                                     onChange={handleFileUpload} 
//                                     className="hidden" 
//                                     accept=".pdf" 
//                                 />
//                                 {uploadingFilename && (
//                                     <div className="flex items-center p-2 text-xs font-medium text-gray-600 rounded-md">
//                                         <Loader2 className="mr-3 h-4 w-4 flex-shrink-0 text-gray-400 animate-spin" />
//                                         <span className="flex-1 truncate">Processing {uploadingFilename}...</span>
//                                     </div>
//                                 )}
//                                 {projectPdfs.map((pdf) => (
//                                     <div key={pdf.id}>
//                                         <div
//                                             onClick={() => handlePdfSelect(pdf.id)}
//                                             className="flex items-center p-2 text-xs font-medium text-gray-600 rounded-md hover:bg-gray-100 cursor-pointer group"
//                                         >
//                                             <File className="mr-3 h-4 w-4 flex-shrink-0 text-gray-400" />
//                                             <span className="flex-1 truncate">{pdf.filename}</span>
//                                              <Trash2 
//                                                 onClick={(e) => { e.stopPropagation(); handleDeletePdf(pdf.id); }}
//                                                 className="h-3 w-3 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
//                                             />
//                                         </div>
//                                     </div>
//                                 ))}
//                              </div>
//                         )}
//                     </div>
//                 ))}
//             </nav>
//         </div>
//     );
// }
// export default ProjectSidebar;
import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Plus, Trash2, File, FolderOpen, FolderClosed, Upload, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";

// --- Configuration ---
const API_BASE_URL = 'http://localhost:8000';

// --- Type Definitions to match the Python API ---
interface PDFMetadata {
    id: string;
    filename: string;
}

interface ProjectType {
    id: string;
    name: string;
    description?: string | null;
}

interface ProjectSidebarProps {
    onProjectSelect: (projectId: string | null) => void;
}

export function ProjectSidebar({ onProjectSelect }: ProjectSidebarProps) {
    // --- State Management ---
    const [projects, setProjects] = useState<ProjectType[]>([]);
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [projectPdfs, setProjectPdfs] = useState<PDFMetadata[]>([]);
    const [selectedPdfId, setSelectedPdfId] = useState<string | null>(null);
    const [uploadingFilename, setUploadingFilename] = useState<string | null>(null);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [selectedPdfType, setSelectedPdfType] = useState<'tender' | 'bid'>('bid');
    const [uploadProjectId, setUploadProjectId] = useState<string | null>(null);
    
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

    // --- API Call Functions ---

    const fetchProjects = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/projects`);
            if (!response.ok) throw new Error('Failed to fetch projects');
            const data = await response.json();
            setProjects(data);
        } catch (err: any) {
            setError(err.message);
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleNewProject = async () => {
        const newProjectName = prompt("Enter new project name:", "New Tender Project");
        if (!newProjectName) return;

        try {
            const response = await fetch(`${API_BASE_URL}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newProjectName, description: "" }),
            });
            if (!response.ok) throw new Error('Failed to create project');
            await fetchProjects(); // Refresh the list
        } catch (err: any) {
            setError(err.message);
            console.error(err);
        }
    };

    const handleDeleteProject = async (projectId: string) => {
        if (!window.confirm("Are you sure you want to delete this project and all its data? This cannot be undone.")) return;

        try {
            const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
                method: 'DELETE',
            });
            if (!response.ok) throw new Error('Failed to delete project');
            
            // Clear selections if the deleted project was selected
            if (selectedProjectId === projectId) {
                setSelectedProjectId(null);
                setSelectedPdfId(null);
                setProjectPdfs([]);
                onProjectSelect(null); // Notify parent
            }
            await fetchProjects(); // Refresh the list
        } catch (err: any) {
            setError(err.message);
            console.error(err);
        }
    };

    const fetchPdfsForProject = async (projectId: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/projects/${projectId}/pdfs`);
            if (!response.ok) throw new Error('Failed to fetch PDFs');
            const data = await response.json();
            setProjectPdfs(data);
        } catch (err: any) {
            setError(err.message);
            console.error(err);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file || !uploadProjectId) return;

        setUploadingFilename(file.name); // Show processing indicator with filename
        setIsUploadModalOpen(false); // Close modal

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE_URL}/projects/${uploadProjectId}/pdfs?pdf_type=${selectedPdfType}`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error('Failed to upload PDF');
            await fetchPdfsForProject(uploadProjectId); // Refresh PDF list
        } catch (err: any) {
            setError(err.message);
            console.error(err);
        } finally {
            setUploadingFilename(null); // Hide processing indicator
            setUploadProjectId(null);
            setSelectedPdfType('bid'); // Reset to default
            if(fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };
    
    const handleDeletePdf = async (pdfId: string) => {
        if (!selectedProjectId || !window.confirm("Are you sure you want to delete this document?")) return;
        
        try {
            const response = await fetch(`${API_BASE_URL}/projects/${selectedProjectId}/pdfs/${pdfId}`, {
                method: 'DELETE',
            });
             if (!response.ok) throw new Error('Failed to delete PDF');
             
            if (selectedPdfId === pdfId) {
                setSelectedPdfId(null);
            }
             await fetchPdfsForProject(selectedProjectId); // Refresh PDF list
        } catch (err: any)
        {
            setError(err.message);
            console.error(err);
        }
    };

    // --- Effects ---

    // Initial fetch of projects when component mounts
    useEffect(() => {
        fetchProjects();
    }, []);

    // --- Event Handlers ---

    const handleProjectSelect = (projectId: string) => {
        if (selectedProjectId === projectId) {
            // If clicking the same project, collapse it
            setSelectedProjectId(null);
            setSelectedPdfId(null);
            setProjectPdfs([]);
            onProjectSelect(null); // Notify parent
        } else {
            setSelectedProjectId(projectId);
            setSelectedPdfId(null); // Reset PDF selection
            fetchPdfsForProject(projectId);
            onProjectSelect(projectId); // Notify parent
        }
    };
    
    const handlePdfSelect = (pdfId: string) => {
         if (selectedPdfId === pdfId) {
            // If clicking the same PDF, collapse it
            setSelectedPdfId(null);
        } else {
            setSelectedPdfId(pdfId);
        }
    };

    const triggerUploadForProject = (projectId: string) => {
        setUploadProjectId(projectId);
        setIsUploadModalOpen(true);
    };

    const confirmUpload = () => {
        fileInputRef.current?.click();
    };

    return (
        <div className="flex flex-col h-full bg-gray-50 border-r border-gray-200 w-80">
            <div className="p-4 border-b border-gray-200">
                <h1 className="text-xl font-bold text-gray-800">Tender Evaluation</h1>
            </div>

            <div className="p-2">
                <Button onClick={handleNewProject} variant="outline" className="w-full justify-start text-sm">
                    <Plus className="mr-2 h-4 w-4" />
                    New Project
                </Button>
            </div>

            {isLoading && <p className="p-4 text-gray-500">Loading projects...</p>}
            {error && <p className="p-4 text-red-500">Error: {error}</p>}
            
            <nav className="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
                {projects.map((project) => (
                    <div key={project.id}>
                        <div
                            onClick={() => handleProjectSelect(project.id)}
                            className="flex items-center p-2 text-sm font-medium text-gray-700 rounded-md hover:bg-gray-100 cursor-pointer group"
                        >
                            {selectedProjectId === project.id ? <FolderOpen className="mr-3 h-5 w-5 flex-shrink-0 text-gray-500" /> : <FolderClosed className="mr-3 h-5 w-5 flex-shrink-0 text-gray-400" />}
                            <span className="flex-1">{project.name}</span>
                            <Upload 
                                onClick={(e) => { e.stopPropagation(); triggerUploadForProject(project.id); }}
                                className="h-4 w-4 text-gray-400 hover:text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity mr-2" 
                            />
                            <Trash2 
                                onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
                                className="h-4 w-4 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
                            />
                        </div>
                        
                        {selectedProjectId === project.id && (
                             <div className="pl-6 mt-1 space-y-1">
                                <input 
                                    type="file" 
                                    ref={fileInputRef} 
                                    onChange={handleFileUpload} 
                                    className="hidden" 
                                    accept=".pdf" 
                                />
                                {uploadingFilename && (
                                    <div className="flex items-center p-2 text-xs font-medium text-gray-600 rounded-md">
                                        <Loader2 className="mr-3 h-4 w-4 flex-shrink-0 text-gray-400 animate-spin" />
                                        <span className="flex-1 truncate">Processing {uploadingFilename}...</span>
                                    </div>
                                )}
                                {projectPdfs.map((pdf) => (
                                    <div key={pdf.id}>
                                        <div
                                            onClick={() => handlePdfSelect(pdf.id)}
                                            className="flex items-center p-2 text-xs font-medium text-gray-600 rounded-md hover:bg-gray-100 cursor-pointer group"
                                        >
                                            <File className="mr-3 h-4 w-4 flex-shrink-0 text-gray-400" />
                                            <span className="flex-1 truncate">{pdf.filename}</span>
                                             <Trash2 
                                                onClick={(e) => { e.stopPropagation(); handleDeletePdf(pdf.id); }}
                                                className="h-3 w-3 text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" 
                                            />
                                        </div>
                                    </div>
                                ))}
                             </div>
                        )}
                    </div>
                ))}
            </nav>

            {/* Upload Type Selection Modal */}
            <Dialog open={isUploadModalOpen} onOpenChange={setIsUploadModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Select Document Type</DialogTitle>
                    </DialogHeader>
                    <div className="py-4">
                        <RadioGroup defaultValue="bid" onValueChange={(value: 'tender' | 'bid') => setSelectedPdfType(value)}>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="tender" id="tender" />
                                <Label htmlFor="tender">Tender Document</Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="bid" id="bid" />
                                <Label htmlFor="bid">Bid Document</Label>
                            </div>
                        </RadioGroup>
                    </div>
                    <Button onClick={confirmUpload}>Select File</Button>
                </DialogContent>
            </Dialog>
        </div>
    );
}
export default ProjectSidebar;