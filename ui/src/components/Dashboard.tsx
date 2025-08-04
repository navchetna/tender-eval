import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  Eye, 
  BarChart3, 
  CheckCircle, 
  Clock, 
  Target,
  FolderOpen,
  Users,
  Building2,
  FileText,
  AlertCircle
} from 'lucide-react';
import ProjectSidebar from './ProjectSidebar';
import DocumentViewer from './DocumentViewer';
import ComparisonView from './ComparisonView';
import ProcessingView from './ProcessingView';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { API_BASE_URL } from '@/lib/constants';

// --- Configuration ---

// --- Type Definitions to match the backend API ---
interface ProjectFile {
  id: string;
  name: string;
  type: 'tender' | 'bid';
  bidderName?: string;
  uploadDate: string;
}

interface Project {
  id: string;
  name: string;
  tenderFile?: ProjectFile;
  bidFiles: ProjectFile[];
  createdAt: string;
  status: 'draft' | 'processing' | 'completed';
}

const Dashboard = () => {
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState('documents');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stages = [
    { id: 1, title: 'Parsing document and creating fast lookup', status: 'completed' },
    { id: 2, title: 'Finding technical and price compliance from TOC', status: 'pending' },
    { id: 3, title: 'Finding compliance requirements from the fast lookup', status: 'pending' },
    { id: 4, title: 'Populating excel sheets', status: 'pending' },
    { id: 5, title: 'Preparing data fror scoring', status: 'pending' },
  ];

  // Fetch project details when activeProjectId changes
  useEffect(() => {
    if (activeProjectId) {
      const fetchProjectDetails = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const response = await fetch(`${API_BASE_URL}/projects/${activeProjectId}/details`);
          if (!response.ok) throw new Error('Failed to fetch project details');
          const data = await response.json();
          setCurrentProject(data);
        } catch (err: any) {
          setError(err.message);
          console.error(err);
        } finally {
          setIsLoading(false);
        }
      };
      fetchProjectDetails();
    } else {
      setCurrentProject(null);
    }
  }, [activeProjectId]);

  const handleProcess = () => {
    setActiveTab('processing');
  };

  const handleProcessingComplete = () => {
    setActiveTab('results');
  };

  const handleGenerateReport = () => {
    console.log('Generating final report');
  };

  // Function to open PDF in new tab (new feature)
  const openPdfInNewTab = async (pdfId: string) => {
    if (!activeProjectId) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${activeProjectId}/pdfs/${pdfId}/view`);
      if (!response.ok) throw new Error('Failed to fetch PDF');
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      console.error('Error opening PDF:', err);
      alert('Failed to open PDF');
    }
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Project Sidebar */}
      <ProjectSidebar onProjectSelect={setActiveProjectId} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b bg-gradient-to-r from-primary/5 to-accent/5">
          <div className="px-6 py-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-foreground">TenderEval</h1>
                <p className="text-muted-foreground mt-1">
                  {currentProject ? `Project: ${currentProject.name}` : 'AI-Powered Tender & Bid Evaluation Platform'}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <Badge variant="outline" className="text-sm">
                  <Target className="h-3 w-3 mr-1" />
                  Infrastructure Procurement
                </Badge>
                <Button variant="outline">
                  <Users className="h-4 w-4 mr-2" />
                  Admin Panel
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Tabs */}
        {isLoading && <p className="p-4 text-gray-500">Loading project details...</p>}
        {error && <p className="p-4 text-red-500">Error: {error}</p>}
        {currentProject && (
          <div className="px-6 py-6">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-3 mb-8">
                <TabsTrigger value="documents">
                  <Eye className="h-4 w-4 mr-2" />
                  Documents
                </TabsTrigger>
                <TabsTrigger value="processing" disabled={activeTab !== 'processing'}>
                  <Clock className="h-4 w-4 mr-2" />
                  Processing
                </TabsTrigger>
                <TabsTrigger value="results" disabled={activeTab !== 'results'}>
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Results
                </TabsTrigger>
              </TabsList>

              <TabsContent value="documents" className="space-y-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold">Project Documents</h3>
                  {currentProject.tenderFile && currentProject.bidFiles.length > 0 && (
                    <Button onClick={handleProcess} className="shadow-soft">
                      Resume Process
                    </Button>
                  )}
                </div>
                {/* Accordion for processed files */}
                <Accordion type="multiple" className="mb-6">
                  {[...(currentProject.tenderFile ? [currentProject.tenderFile] : []), ...currentProject.bidFiles].map(file => (
                    <AccordionItem key={file.id} value={file.id}>
                      <AccordionTrigger>
                        <span className="font-medium">{file.name}</span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-2">
                          {stages.map(stage => (
                            <div key={stage.id} className="p-2 bg-muted/40 rounded flex items-center">
                              {stage.status === 'completed' ? (
                                <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
                              ) : (
                                <AlertCircle className="h-4 w-4 text-yellow-500 mr-2" />
                              )}
                              <strong>{stage.title}:</strong>
                              <div className="ml-1 text-sm capitalize">{stage.status}</div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
                {/* Simple Documents List */}
                <div className="space-y-4">
                  {currentProject.tenderFile && (
                    <Card className="cursor-pointer hover:bg-gray-50" onClick={() => openPdfInNewTab(currentProject.tenderFile.id)}>
                      <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-green-600" />
                          <div className="flex-1">
                            <div className="font-medium">{currentProject.tenderFile.name}</div>
                            <div className="text-sm text-muted-foreground">
                              Uploaded on {new Date(currentProject.tenderFile.uploadDate).toLocaleDateString()}
                            </div>
                          </div>
                          <Badge variant="secondary">Tender</Badge>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  
                  {currentProject.bidFiles.map((file) => (
                    <Card key={file.id} className="cursor-pointer hover:bg-gray-50" onClick={() => openPdfInNewTab(file.id)}>
                      <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-orange-600" />
                          <div className="flex-1">
                            <div className="font-medium">{file.name}</div>
                            <div className="text-sm text-muted-foreground">
                              {file.bidderName} • Uploaded on {new Date(file.uploadDate).toLocaleDateString()}
                            </div>
                          </div>
                          <Badge variant="outline">Bid</Badge>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="processing" className="space-y-6">
                <ProcessingView 
                  files={[
                    ...(currentProject.tenderFile ? [currentProject.tenderFile] : []),
                    ...currentProject.bidFiles
                  ]}
                  onProcessingComplete={handleProcessingComplete}
                  projectId={activeProjectId}  // Preserved: Passing projectId to ProcessingView
                />
              </TabsContent>

              <TabsContent value="results" className="space-y-6">
                <ComparisonView
                  comparisons={[]} // Replace with real data as needed
                  explanation="" // Replace with real data as needed
                  onGenerateReport={handleGenerateReport}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}

        {!currentProject && !isLoading && (
          <div className="text-center py-12">
            <FolderOpen className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Project Selected</h3>
            <p className="text-muted-foreground">
              Select a project from the sidebar or create a new one to get started.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
