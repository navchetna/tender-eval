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