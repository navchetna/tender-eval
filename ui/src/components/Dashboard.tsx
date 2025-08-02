// // // import React, { useState } from 'react';
// // // import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// // // import { Button } from '@/components/ui/button';
// // // import { Badge } from '@/components/ui/badge';
// // // import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// // // import { Progress } from '@/components/ui/progress';
// // // import { 
// // //   Eye, 
// // //   BarChart3, 
// // //   CheckCircle, 
// // //   Clock, 
// // //   Target,
// // //   FolderOpen,
// // //   Users,
// // //   Building2,
// // //   FileText
// // // } from 'lucide-react';
// // // import ProjectSidebar from './ProjectSidebar';
// // // import DocumentViewer from './DocumentViewer';
// // // import ComparisonView from './ComparisonView';
// // // import ProcessingView from './ProcessingView';
// // // import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';

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

// // // // Mock data for demonstration
// // // const mockProjects: Project[] = [
// // //   {
// // //     id: '1',
// // //     name: 'Highway Infrastructure Project',
// // //     tenderFile: {
// // //       id: 't1',
// // //       name: 'Highway_Tender_2024.pdf',
// // //       type: 'tender',
// // //       uploadDate: '2024-01-15'
// // //     },
// // //     bidFiles: [
// // //       {
// // //         id: 'b1',
// // //         name: 'ABC_Construction_Bid.pdf',
// // //         type: 'bid',
// // //         bidderName: 'ABC Construction Ltd.',
// // //         uploadDate: '2024-01-20'
// // //       },
// // //       {
// // //         id: 'b2',
// // //         name: 'XYZ_Infrastructure_Bid.pdf',
// // //         type: 'bid',
// // //         bidderName: 'XYZ Infrastructure Co.',
// // //         uploadDate: '2024-01-22'
// // //       },
// // //       {
// // //         id: 'b3',
// // //         name: 'BuildTech_Bid.pdf',
// // //         type: 'bid',
// // //         bidderName: 'BuildTech Solutions',
// // //         uploadDate: '2024-01-21'
// // //       }
// // //     ],
// // //     createdAt: '2024-01-15',
// // //     status: 'completed'
// // //   },
// // //   {
// // //     id: '2',
// // //     name: 'Water Treatment Plant',
// // //     tenderFile: {
// // //       id: 't2',
// // //       name: 'Water_Plant_Tender.pdf',
// // //       type: 'tender',
// // //       uploadDate: '2024-02-01'
// // //     },
// // //     bidFiles: [
// // //       {
// // //         id: 'b4',
// // //         name: 'Aqua_Systems_Bid.pdf',
// // //         type: 'bid',
// // //         bidderName: 'Aqua Systems Inc.',
// // //         uploadDate: '2024-02-10'
// // //       },
// // //       {
// // //         id: 'b5',
// // //         name: 'Clean_Water_Bid.pdf',
// // //         type: 'bid',
// // //         bidderName: 'Clean Water Technologies',
// // //         uploadDate: '2024-02-12'
// // //       }
// // //     ],
// // //     createdAt: '2024-02-01',
// // //     status: 'processing'
// // //   }
// // // ];

// // // const mockDocuments = [
// // //   {
// // //     id: '1',
// // //     name: 'Infrastructure Tender - Road Construction',
// // //     type: 'tender' as const,
// // //     status: 'completed' as const,
// // //     sections: [
// // //       {
// // //         id: '1-1',
// // //         title: 'Technical Requirements',
// // //         type: 'technical' as const,
// // //         status: 'compliant' as const,
// // //         tables: [{}]
// // //       },
// // //       {
// // //         id: '1-2',
// // //         title: 'Price Schedule',
// // //         type: 'price' as const,
// // //         status: 'compliant' as const,
// // //         tables: [{}]
// // //       }
// // //     ],
// // //     toc: ['1. Introduction', '2. Technical Requirements', '3. Price Schedule', '4. Terms & Conditions']
// // //   },
// // //   {
// // //     id: '2',
// // //     name: 'Bid Response - ABC Construction',
// // //     type: 'bid' as const,
// // //     status: 'completed' as const,
// // //     sections: [
// // //       {
// // //         id: '2-1',
// // //         title: 'Technical Compliance',
// // //         type: 'technical' as const,
// // //         status: 'compliant' as const,
// // //         tables: [{}]
// // //       },
// // //       {
// // //         id: '2-2',
// // //         title: 'Price Submission',
// // //         type: 'price' as const,
// // //         status: 'compliant' as const,
// // //         tables: [{}]
// // //       }
// // //     ],
// // //     toc: ['1. Company Profile', '2. Technical Compliance', '3. Price Submission', '4. Supporting Documents']
// // //   }
// // // ];

// // // const mockComparisons = [
// // //   {
// // //     bidId: '1',
// // //     bidderName: 'ABC Construction Ltd.',
// // //     technicalScore: 95,
// // //     priceScore: 85,
// // //     overallScore: 92,
// // //     status: 'winner' as const,
// // //     technicalCompliance: { compliant: 18, nonCompliant: 1, total: 19 },
// // //     priceCompliance: { 
// // //       totalPrice: 2450000, 
// // //       breakdown: { 'Materials': 1200000, 'Labor': 800000, 'Equipment': 450000 }
// // //     }
// // //   },
// // //   {
// // //     bidId: '2',
// // //     bidderName: 'XYZ Infrastructure Co.',
// // //     technicalScore: 88,
// // //     priceScore: 92,
// // //     overallScore: 89,
// // //     status: 'qualified' as const,
// // //     technicalCompliance: { compliant: 16, nonCompliant: 3, total: 19 },
// // //     priceCompliance: { 
// // //       totalPrice: 2380000, 
// // //       breakdown: { 'Materials': 1150000, 'Labor': 750000, 'Equipment': 480000 }
// // //     }
// // //   },
// // //   {
// // //     bidId: '3',
// // //     bidderName: 'BuildTech Solutions',
// // //     technicalScore: 75,
// // //     priceScore: 78,
// // //     overallScore: 76,
// // //     status: 'disqualified' as const,
// // //     technicalCompliance: { compliant: 12, nonCompliant: 7, total: 19 },
// // //     priceCompliance: { 
// // //       totalPrice: 2650000, 
// // //       breakdown: { 'Materials': 1300000, 'Labor': 850000, 'Equipment': 500000 }
// // //     }
// // //   }
// // // ];

// // // const mockExplanation = `Based on the comprehensive analysis of all submitted bids, ABC Construction Ltd. emerges as the winning bidder with an overall score of 92%.

// // // Technical Evaluation:
// // // ABC Construction demonstrates superior technical compliance with 18 out of 19 requirements fully met. Their proposed methodology shows deep understanding of the project requirements, with only minor documentation gaps in environmental impact assessments.

// // // Price Evaluation:
// // // While not the lowest bidder, ABC Construction offers excellent value for money at $2,450,000. Their pricing is competitive and well-justified with detailed cost breakdowns that demonstrate transparency and realistic project costing.

// // // Key Differentiators:
// // // 1. Strong technical capability with proven track record
// // // 2. Comprehensive project management approach
// // // 3. Realistic timeline and resource allocation
// // // 4. Excellent safety protocols and environmental compliance

// // // Recommendations:
// // // Award the contract to ABC Construction Ltd. with conditions to address the minor environmental documentation gap within 30 days of contract signing.`;

// // // // Add a mock for processed file stage outputs
// // // const mockProcessedFileOutputs = [
// // //   {
// // //     fileId: 't1',
// // //     fileName: 'Highway_Tender_2024.pdf',
// // //     stages: [
// // //       { id: 1, title: 'Parsing and creating structure', output: 'Parsed structure for Highway_Tender_2024.pdf' },
// // //       { id: 2, title: 'Finding technical and price compliance from TOC', output: 'Compliance found in TOC.' },
// // //       { id: 3, title: 'Finding compliance requirements from tree', output: 'Requirements mapped.' },
// // //       { id: 4, title: 'Converting to dataframes & excel sheets', output: 'Dataframes and Excel generated.' },
// // //       { id: 5, title: 'Transforming into JSON files', output: 'JSON output created.' },
// // //     ]
// // //   },
// // //   {
// // //     fileId: 'b1',
// // //     fileName: 'ABC_Construction_Bid.pdf',
// // //     stages: [
// // //       { id: 1, title: 'Parsing and creating structure', output: 'Parsed structure for ABC_Construction_Bid.pdf' },
// // //       { id: 2, title: 'Finding technical and price compliance from TOC', output: 'Compliance found in TOC.' },
// // //       { id: 3, title: 'Finding compliance requirements from tree', output: 'Requirements mapped.' },
// // //       { id: 4, title: 'Converting to dataframes & excel sheets', output: 'Dataframes and Excel generated.' },
// // //       { id: 5, title: 'Transforming into JSON files', output: 'JSON output created.' },
// // //     ]
// // //   }
// // // ];

// // // const Dashboard = () => {
// // //   const [projects, setProjects] = useState<Project[]>(mockProjects);
// // //   const [activeProject, setActiveProject] = useState<string | null>('1');
// // //   const [activeTab, setActiveTab] = useState('documents');
// // //   const [processStep, setProcessStep] = useState(0);
// // //   const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

// // //   const steps = [
// // //     'Parse Documents',
// // //     'Extract Tables',
// // //     'Analyze Compliance',
// // //     'Generate Comparison',
// // //     'Review Results'
// // //   ];

// // //   const currentProject = activeProject ? projects.find(p => p.id === activeProject) : null;
// // //   const totalProjects = projects.length;
// // //   const totalBidders = projects.reduce((sum, p) => sum + p.bidFiles.length, 0);
// // //   const completedProjects = projects.filter(p => p.status === 'completed').length;

// // //   const handleProjectCreate = (name: string) => {
// // //     const newProject: Project = {
// // //       id: Date.now().toString(),
// // //       name,
// // //       bidFiles: [],
// // //       createdAt: new Date().toISOString(),
// // //       status: 'draft'
// // //     };
// // //     setProjects(prev => [...prev, newProject]);
// // //     setActiveProject(newProject.id);
// // //   };

// // //   const handleFileUpload = (projectId: string, files: File[], type: 'tender' | 'bid', bidderName?: string) => {
// // //     setProjects(prev => prev.map(project => {
// // //       if (project.id !== projectId) return project;
      
// // //       const newFiles: ProjectFile[] = files.map(file => ({
// // //         id: Date.now().toString() + Math.random(),
// // //         name: file.name,
// // //         type,
// // //         bidderName,
// // //         uploadDate: new Date().toISOString()
// // //       }));

// // //       if (type === 'tender') {
// // //         return { ...project, tenderFile: newFiles[0] };
// // //       } else {
// // //         return { ...project, bidFiles: [...project.bidFiles, ...newFiles] };
// // //       }
// // //     }));
// // //   };

// // //   const handleProjectDelete = (projectId: string) => {
// // //     setProjects(prev => prev.filter(p => p.id !== projectId));
// // //   };

// // //   const handleFileDelete = (projectId: string, fileId: string, type: 'tender' | 'bid') => {
// // //     setProjects(prev => prev.map(project => {
// // //       if (project.id !== projectId) return project;
      
// // //       if (type === 'tender') {
// // //         return { ...project, tenderFile: undefined };
// // //       } else {
// // //         return { ...project, bidFiles: project.bidFiles.filter(f => f.id !== fileId) };
// // //       }
// // //     }));
// // //   };

// // //   const handleProcess = () => {
// // //     setActiveTab('processing');
// // //   };

// // //   const handleProcessingComplete = () => {
// // //     setActiveTab('results');
// // //   };

// // //   const handleDownload = (docId: string, format: 'excel' | 'json') => {
// // //     console.log(`Downloading ${format} for document ${docId}`);
// // //   };

// // //   const handleGenerateReport = () => {
// // //     console.log('Generating final report');
// // //   };

// // //   return (
// // //     <div className="min-h-screen bg-background flex">
// // //       {/* Project Sidebar */}
// // //       <ProjectSidebar
// // //         projects={projects}
// // //         activeProject={activeProject}
// // //         onProjectSelect={setActiveProject}
// // //         onProjectCreate={handleProjectCreate}
// // //         onFileUpload={handleFileUpload}
// // //         onProjectDelete={handleProjectDelete}
// // //         onFileDelete={handleFileDelete}
// // //         isCollapsed={sidebarCollapsed}
// // //         onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
// // //       />

// // //       {/* Main Content */}
// // //       <div className="flex-1 flex flex-col">
// // //         {/* Header */}
// // //         <div className="border-b bg-gradient-to-r from-primary/5 to-accent/5">
// // //           <div className="px-6 py-6">
// // //             <div className="flex items-center justify-between">
// // //               <div>
// // //                 <h1 className="text-3xl font-bold text-foreground">TenderEval</h1>
// // //                 <p className="text-muted-foreground mt-1">
// // //                   {currentProject ? `Project: ${currentProject.name}` : 'AI-Powered Tender & Bid Evaluation Platform'}
// // //                 </p>
// // //               </div>
// // //               <div className="flex items-center gap-4">
// // //                 <Badge variant="outline" className="text-sm">
// // //                   <Target className="h-3 w-3 mr-1" />
// // //                   Infrastructure Procurement
// // //                 </Badge>
// // //                 <Button variant="outline">
// // //                   <Users className="h-4 w-4 mr-2" />
// // //                   Admin Panel
// // //                 </Button>
// // //               </div>
// // //             </div>
// // //           </div>
// // //         </div>

// // //         {/* Stats Overview */}
// // //         <div className="px-6 py-6">
// // //           <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
// // //             <Card className="shadow-soft">
// // //               <CardContent className="p-6">
// // //                 <div className="flex items-center gap-3">
// // //                   <div className="p-2 bg-primary/10 rounded-lg">
// // //                     <FolderOpen className="h-5 w-5 text-primary" />
// // //                   </div>
// // //                   <div>
// // //                     <p className="text-2xl font-bold">{totalProjects}</p>
// // //                     <p className="text-sm text-muted-foreground">Total Projects</p>
// // //                   </div>
// // //                 </div>
// // //               </CardContent>
// // //             </Card>
// // //             <Card className="shadow-soft">
// // //               <CardContent className="p-6">
// // //                 <div className="flex items-center gap-3">
// // //                   <div className="p-2 bg-success/10 rounded-lg">
// // //                     <CheckCircle className="h-5 w-5 text-success" />
// // //                   </div>
// // //                   <div>
// // //                     <p className="text-2xl font-bold">{completedProjects}</p>
// // //                     <p className="text-sm text-muted-foreground">Completed Projects</p>
// // //                   </div>
// // //                 </div>
// // //               </CardContent>
// // //             </Card>
// // //             <Card className="shadow-soft">
// // //               <CardContent className="p-6">
// // //                 <div className="flex items-center gap-3">
// // //                   <div className="p-2 bg-warning/10 rounded-lg">
// // //                     <Users className="h-5 w-5 text-warning" />
// // //                   </div>
// // //                   <div>
// // //                     <p className="text-2xl font-bold">{totalBidders}</p>
// // //                     <p className="text-sm text-muted-foreground">Total Bidders</p>
// // //                   </div>
// // //                 </div>
// // //               </CardContent>
// // //             </Card>
// // //             <Card className="shadow-soft">
// // //               <CardContent className="p-6">
// // //                 <div className="flex items-center gap-3">
// // //                   <div className="p-2 bg-info/10 rounded-lg">
// // //                     <Building2 className="h-5 w-5 text-info" />
// // //                   </div>
// // //                   <div>
// // //                     <p className="text-2xl font-bold">{currentProject?.bidFiles.length || 0}</p>
// // //                     <p className="text-sm text-muted-foreground">Current Project Bidders</p>
// // //                   </div>
// // //                 </div>
// // //               </CardContent>
// // //             </Card>
// // //           </div>

// // //           {/* Main Content Tabs */}
// // //           {currentProject && (
// // //             <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
// // //               <TabsList className="grid w-full grid-cols-3 mb-8">
// // //                 <TabsTrigger value="documents">
// // //                   <Eye className="h-4 w-4 mr-2" />
// // //                   Documents
// // //                 </TabsTrigger>
// // //                 <TabsTrigger value="processing" disabled={activeTab !== 'processing'}>
// // //                   <Clock className="h-4 w-4 mr-2" />
// // //                   Processing
// // //                 </TabsTrigger>
// // //                 <TabsTrigger value="results" disabled={activeTab !== 'results'}>
// // //                   <BarChart3 className="h-4 w-4 mr-2" />
// // //                   Results
// // //                 </TabsTrigger>
// // //               </TabsList>

// // //               <TabsContent value="documents" className="space-y-6">
// // //                 <div className="flex items-center justify-between mb-4">
// // //                   <h3 className="text-lg font-semibold">Project Documents</h3>
// // //                   {currentProject.tenderFile && currentProject.bidFiles.length > 0 && (
// // //                     <Button onClick={handleProcess} className="shadow-soft">
// // //                       Start Processing
// // //                     </Button>
// // //                   )}
// // //                 </div>
// // //                 {/* Accordion for processed files */}
// // //                 <Accordion type="multiple" className="mb-6">
// // //                   {mockProcessedFileOutputs.map(file => (
// // //                     <AccordionItem key={file.fileId} value={file.fileId}>
// // //                       <AccordionTrigger>
// // //                         <span className="font-medium">{file.fileName}</span>
// // //                       </AccordionTrigger>
// // //                       <AccordionContent>
// // //                         <div className="space-y-2">
// // //                           {file.stages.map(stage => (
// // //                             <div key={stage.id} className="p-2 bg-muted/40 rounded">
// // //                               <strong>{stage.title}:</strong>
// // //                               <div className="mt-1 text-sm">{stage.output}</div>
// // //                             </div>
// // //                           ))}
// // //                         </div>
// // //                       </AccordionContent>
// // //                     </AccordionItem>
// // //                   ))}
// // //                 </Accordion>
// // //                 {/* Simple Documents List */}
// // //                 <div className="space-y-4">
// // //                   {currentProject.tenderFile && (
// // //                     <Card>
// // //                       <CardContent className="p-4">
// // //                         <div className="flex items-center gap-3">
// // //                           <FileText className="h-5 w-5 text-green-600" />
// // //                           <div className="flex-1">
// // //                             <div className="font-medium">{currentProject.tenderFile.name}</div>
// // //                             <div className="text-sm text-muted-foreground">
// // //                               Uploaded on {new Date(currentProject.tenderFile.uploadDate).toLocaleDateString()}
// // //                             </div>
// // //                           </div>
// // //                           <Badge variant="secondary">Tender</Badge>
// // //                         </div>
// // //                       </CardContent>
// // //                     </Card>
// // //                   )}
                  
// // //                   {currentProject.bidFiles.map((file) => (
// // //                     <Card key={file.id}>
// // //                       <CardContent className="p-4">
// // //                         <div className="flex items-center gap-3">
// // //                           <FileText className="h-5 w-5 text-orange-600" />
// // //                           <div className="flex-1">
// // //                             <div className="font-medium">{file.name}</div>
// // //                             <div className="text-sm text-muted-foreground">
// // //                               {file.bidderName} • Uploaded on {new Date(file.uploadDate).toLocaleDateString()}
// // //                             </div>
// // //                           </div>
// // //                           <Badge variant="outline">Bid</Badge>
// // //                         </div>
// // //                       </CardContent>
// // //                     </Card>
// // //                   ))}
// // //                 </div>
// // //               </TabsContent>

// // //               <TabsContent value="processing" className="space-y-6">
// // //                 <ProcessingView 
// // //                   files={[
// // //                     ...(currentProject.tenderFile ? [currentProject.tenderFile] : []),
// // //                     ...currentProject.bidFiles
// // //                   ]}
// // //                   onProcessingComplete={handleProcessingComplete}
// // //                 />
// // //               </TabsContent>

// // //               <TabsContent value="results" className="space-y-6">
// // //                 <ComparisonView
// // //                   comparisons={mockComparisons}
// // //                   explanation={mockExplanation}
// // //                   onGenerateReport={handleGenerateReport}
// // //                 />
// // //               </TabsContent>
// // //             </Tabs>
// // //           )}

// // //           {!currentProject && (
// // //             <div className="text-center py-12">
// // //               <FolderOpen className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
// // //               <h3 className="text-lg font-semibold mb-2">No Project Selected</h3>
// // //               <p className="text-muted-foreground">
// // //                 Select a project from the sidebar or create a new one to get started.
// // //               </p>
// // //             </div>
// // //           )}
// // //         </div>
// // //       </div>
// // //     </div>
// // //   );
// // // };

// // // export default Dashboard;
// // import React, { useState, useEffect } from 'react';
// // import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// // import { Button } from '@/components/ui/button';
// // import { Badge } from '@/components/ui/badge';
// // import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// // import { Progress } from '@/components/ui/progress';
// // import { 
// //   Eye, 
// //   BarChart3, 
// //   CheckCircle, 
// //   Clock, 
// //   Target,
// //   FolderOpen,
// //   Users,
// //   Building2,
// //   FileText
// // } from 'lucide-react';
// // import ProjectSidebar from './ProjectSidebar';
// // import DocumentViewer from './DocumentViewer';
// // import ComparisonView from './ComparisonView';
// // import ProcessingView from './ProcessingView';
// // import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';


// // // --- Configuration ---
// // const API_BASE_URL = 'http://localhost:8000';

// // // --- Type Definitions to match the backend API ---
// // interface ProjectFile {
// //   id: string;
// //   name: string;
// //   type: 'tender' | 'bid';
// //   bidderName?: string;
// //   uploadDate: string;
// // }

// // interface Project {
// //   id: string;
// //   name: string;
// //   tenderFile?: ProjectFile;
// //   bidFiles: ProjectFile[];
// //   createdAt: string;
// //   status: 'draft' | 'processing' | 'completed';
// // }

// // const Dashboard = () => {
// //   const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
// //   const [currentProject, setCurrentProject] = useState<Project | null>(null);
// //   const [activeTab, setActiveTab] = useState('documents');
// //   const [isLoading, setIsLoading] = useState(false);
// //   const [error, setError] = useState<string | null>(null);

// //   // Fetch project details when activeProjectId changes
// //   useEffect(() => {
// //     if (activeProjectId) {
// //       const fetchProjectDetails = async () => {
// //         setIsLoading(true);
// //         setError(null);
// //         try {
// //           const response = await fetch(`${API_BASE_URL}/projects/${activeProjectId}/details`);
// //           if (!response.ok) throw new Error('Failed to fetch project details');
// //           const data = await response.json();
// //           setCurrentProject(data);
// //         } catch (err: any) {
// //           setError(err.message);
// //           console.error(err);
// //         } finally {
// //           setIsLoading(false);
// //         }
// //       };
// //       fetchProjectDetails();
// //     } else {
// //       setCurrentProject(null);
// //     }
// //   }, [activeProjectId]);

// //   const handleProcess = () => {
// //     setActiveTab('processing');
// //   };

// //   const handleProcessingComplete = () => {
// //     setActiveTab('results');
// //   };

// //   const handleGenerateReport = () => {
// //     console.log('Generating final report');
// //   };

// //   return (
// //     <div className="min-h-screen bg-background flex">
// //       {/* Project Sidebar */}
// //       <ProjectSidebar onProjectSelect={setActiveProjectId} />

// //       {/* Main Content */}
// //       <div className="flex-1 flex flex-col">
// //         {/* Header */}
// //         <div className="border-b bg-gradient-to-r from-primary/5 to-accent/5">
// //           <div className="px-6 py-6">
// //             <div className="flex items-center justify-between">
// //               <div>
// //                 <h1 className="text-3xl font-bold text-foreground">TenderEval</h1>
// //                 <p className="text-muted-foreground mt-1">
// //                   {currentProject ? `Project: ${currentProject.name}` : 'AI-Powered Tender & Bid Evaluation Platform'}
// //                 </p>
// //               </div>
// //               <div className="flex items-center gap-4">
// //                 <Badge variant="outline" className="text-sm">
// //                   <Target className="h-3 w-3 mr-1" />
// //                   Infrastructure Procurement
// //                 </Badge>
// //                 <Button variant="outline">
// //                   <Users className="h-4 w-4 mr-2" />
// //                   Admin Panel
// //                 </Button>
// //               </div>
// //             </div>
// //           </div>
// //         </div>

// //         {/* Main Content Tabs */}
// //         {isLoading && <p className="p-4 text-gray-500">Loading project details...</p>}
// //         {error && <p className="p-4 text-red-500">Error: {error}</p>}
// //         {currentProject && (
// //           <div className="px-6 py-6">
// //             <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
// //               <TabsList className="grid w-full grid-cols-3 mb-8">
// //                 <TabsTrigger value="documents">
// //                   <Eye className="h-4 w-4 mr-2" />
// //                   Documents
// //                 </TabsTrigger>
// //                 <TabsTrigger value="processing" disabled={activeTab !== 'processing'}>
// //                   <Clock className="h-4 w-4 mr-2" />
// //                   Processing
// //                 </TabsTrigger>
// //                 <TabsTrigger value="results" disabled={activeTab !== 'results'}>
// //                   <BarChart3 className="h-4 w-4 mr-2" />
// //                   Results
// //                 </TabsTrigger>
// //               </TabsList>

// //               <TabsContent value="documents" className="space-y-6">
// //                 <div className="flex items-center justify-between mb-4">
// //                   <h3 className="text-lg font-semibold">Project Documents</h3>
// //                   {currentProject.tenderFile && currentProject.bidFiles.length > 0 && (
// //                     <Button onClick={handleProcess} className="shadow-soft">
// //                       Start Processing
// //                     </Button>
// //                   )}
// //                 </div>
// //                 {/* Accordion for processed files */}
// //                 <Accordion type="multiple" className="mb-6">
// //                   {[...(currentProject.tenderFile ? [currentProject.tenderFile] : []), ...currentProject.bidFiles].map(file => (
// //                     <AccordionItem key={file.id} value={file.id}>
// //                       <AccordionTrigger>
// //                         <span className="font-medium">{file.name}</span>
// //                       </AccordionTrigger>
// //                       <AccordionContent>
// //                         <div className="space-y-2">
// //                           <div className="p-2 bg-muted/40 rounded flex items-center">
// //                             <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
// //                             <strong>Parsing and creating structure:</strong>
// //                             <div className="ml-1 text-sm">Completed</div>
// //                           </div>
// //                           {/* Additional stages can be added here as processing progresses */}
// //                         </div>
// //                       </AccordionContent>
// //                     </AccordionItem>
// //                   ))}
// //                 </Accordion>
// //                 {/* Simple Documents List */}
// //                 <div className="space-y-4">
// //                   {currentProject.tenderFile && (
// //                     <Card>
// //                       <CardContent className="p-4">
// //                         <div className="flex items-center gap-3">
// //                           <FileText className="h-5 w-5 text-green-600" />
// //                           <div className="flex-1">
// //                             <div className="font-medium">{currentProject.tenderFile.name}</div>
// //                             <div className="text-sm text-muted-foreground">
// //                               Uploaded on {new Date(currentProject.tenderFile.uploadDate).toLocaleDateString()}
// //                             </div>
// //                           </div>
// //                           <Badge variant="secondary">Tender</Badge>
// //                         </div>
// //                       </CardContent>
// //                     </Card>
// //                   )}
                  
// //                   {currentProject.bidFiles.map((file) => (
// //                     <Card key={file.id}>
// //                       <CardContent className="p-4">
// //                         <div className="flex items-center gap-3">
// //                           <FileText className="h-5 w-5 text-orange-600" />
// //                           <div className="flex-1">
// //                             <div className="font-medium">{file.name}</div>
// //                             <div className="text-sm text-muted-foreground">
// //                               {file.bidderName} • Uploaded on {new Date(file.uploadDate).toLocaleDateString()}
// //                             </div>
// //                           </div>
// //                           <Badge variant="outline">Bid</Badge>
// //                         </div>
// //                       </CardContent>
// //                     </Card>
// //                   ))}
// //                 </div>
// //               </TabsContent>

// //               <TabsContent value="processing" className="space-y-6">
// //                 <ProcessingView 
// //                   files={[
// //                     ...(currentProject.tenderFile ? [currentProject.tenderFile] : []),
// //                     ...currentProject.bidFiles
// //                   ]}
// //                   onProcessingComplete={handleProcessingComplete}
// //                 />
// //               </TabsContent>

// //               <TabsContent value="results" className="space-y-6">
// //                 <ComparisonView
// //                   comparisons={[]} // Replace with real data as needed
// //                   explanation="" // Replace with real data as needed
// //                   onGenerateReport={handleGenerateReport}
// //                 />
// //               </TabsContent>
// //             </Tabs>
// //           </div>
// //         )}

// //         {!currentProject && !isLoading && (
// //           <div className="text-center py-12">
// //             <FolderOpen className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
// //             <h3 className="text-lg font-semibold mb-2">No Project Selected</h3>
// //             <p className="text-muted-foreground">
// //               Select a project from the sidebar or create a new one to get started.
// //             </p>
// //           </div>
// //         )}
// //       </div>
// //     </div>
// //   );
// // };

// // export default Dashboard;
// import React, { useState, useEffect } from 'react';
// import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
// import { Button } from '@/components/ui/button';
// import { Badge } from '@/components/ui/badge';
// import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
// import { Progress } from '@/components/ui/progress';
// import { 
//   Eye, 
//   BarChart3, 
//   CheckCircle, 
//   Clock, 
//   Target,
//   FolderOpen,
//   Users,
//   Building2,
//   FileText,
//   AlertCircle
// } from 'lucide-react';
// import ProjectSidebar from './ProjectSidebar';
// import DocumentViewer from './DocumentViewer';
// import ComparisonView from './ComparisonView';
// import ProcessingView from './ProcessingView';
// import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';


// // --- Configuration ---
// const API_BASE_URL = 'http://localhost:8000';

// // --- Type Definitions to match the backend API ---
// interface ProjectFile {
//   id: string;
//   name: string;
//   type: 'tender' | 'bid';
//   bidderName?: string;
//   uploadDate: string;
// }

// interface Project {
//   id: string;
//   name: string;
//   tenderFile?: ProjectFile;
//   bidFiles: ProjectFile[];
//   createdAt: string;
//   status: 'draft' | 'processing' | 'completed';
// }

// const Dashboard = () => {
//   const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
//   const [currentProject, setCurrentProject] = useState<Project | null>(null);
//   const [activeTab, setActiveTab] = useState('documents');
//   const [isLoading, setIsLoading] = useState(false);
//   const [error, setError] = useState<string | null>(null);

//   // Mock stages data (in real scenario, fetch from backend)
//   const stages = [
//     { id: 1, title: 'Parsing and creating structure', status: 'completed' },
//     { id: 2, title: 'Finding technical and price compliance from TOC', status: 'pending' },
//     { id: 3, title: 'Finding compliance requirements from tree', status: 'pending' },
//     { id: 4, title: 'Converting to dataframes & excel sheets', status: 'pending' },
//     { id: 5, title: 'Transforming into JSON files', status: 'pending' },
//   ];

//   // Fetch project details when activeProjectId changes
//   useEffect(() => {
//     if (activeProjectId) {
//       const fetchProjectDetails = async () => {
//         setIsLoading(true);
//         setError(null);
//         try {
//           const response = await fetch(`${API_BASE_URL}/projects/${activeProjectId}/details`);
//           if (!response.ok) throw new Error('Failed to fetch project details');
//           const data = await response.json();
//           setCurrentProject(data);
//         } catch (err: any) {
//           setError(err.message);
//           console.error(err);
//         } finally {
//           setIsLoading(false);
//         }
//       };
//       fetchProjectDetails();
//     } else {
//       setCurrentProject(null);
//     }
//   }, [activeProjectId]);

//   const handleProcess = () => {
//     setActiveTab('processing');
//   };

//   const handleProcessingComplete = () => {
//     setActiveTab('results');
//   };

//   const handleGenerateReport = () => {
//     console.log('Generating final report');
//   };

//   return (
//     <div className="min-h-screen bg-background flex">
//       {/* Project Sidebar */}
//       <ProjectSidebar onProjectSelect={setActiveProjectId} />

//       {/* Main Content */}
//       <div className="flex-1 flex flex-col">
//         {/* Header */}
//         <div className="border-b bg-gradient-to-r from-primary/5 to-accent/5">
//           <div className="px-6 py-6">
//             <div className="flex items-center justify-between">
//               <div>
//                 <h1 className="text-3xl font-bold text-foreground">TenderEval</h1>
//                 <p className="text-muted-foreground mt-1">
//                   {currentProject ? `Project: ${currentProject.name}` : 'AI-Powered Tender & Bid Evaluation Platform'}
//                 </p>
//               </div>
//               <div className="flex items-center gap-4">
//                 <Badge variant="outline" className="text-sm">
//                   <Target className="h-3 w-3 mr-1" />
//                   Infrastructure Procurement
//                 </Badge>
//                 <Button variant="outline">
//                   <Users className="h-4 w-4 mr-2" />
//                   Admin Panel
//                 </Button>
//               </div>
//             </div>
//           </div>
//         </div>

//         {/* Main Content Tabs */}
//         {isLoading && <p className="p-4 text-gray-500">Loading project details...</p>}
//         {error && <p className="p-4 text-red-500">Error: {error}</p>}
//         {currentProject && (
//           <div className="px-6 py-6">
//             <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
//               <TabsList className="grid w-full grid-cols-3 mb-8">
//                 <TabsTrigger value="documents">
//                   <Eye className="h-4 w-4 mr-2" />
//                   Documents
//                 </TabsTrigger>
//                 <TabsTrigger value="processing" disabled={activeTab !== 'processing'}>
//                   <Clock className="h-4 w-4 mr-2" />
//                   Processing
//                 </TabsTrigger>
//                 <TabsTrigger value="results" disabled={activeTab !== 'results'}>
//                   <BarChart3 className="h-4 w-4 mr-2" />
//                   Results
//                 </TabsTrigger>
//               </TabsList>

//               <TabsContent value="documents" className="space-y-6">
//                 <div className="flex items-center justify-between mb-4">
//                   <h3 className="text-lg font-semibold">Project Documents</h3>
//                   {currentProject.tenderFile && currentProject.bidFiles.length > 0 && (
//                     <Button onClick={handleProcess} className="shadow-soft">
//                       Resume Process
//                     </Button>
//                   )}
//                 </div>
//                 {/* Accordion for processed files */}
//                 <Accordion type="multiple" className="mb-6">
//                   {[...(currentProject.tenderFile ? [currentProject.tenderFile] : []), ...currentProject.bidFiles].map(file => (
//                     <AccordionItem key={file.id} value={file.id}>
//                       <AccordionTrigger>
//                         <span className="font-medium">{file.name}</span>
//                       </AccordionTrigger>
//                       <AccordionContent>
//                         <div className="space-y-2">
//                           {stages.map(stage => (
//                             <div key={stage.id} className="p-2 bg-muted/40 rounded flex items-center">
//                               {stage.status === 'completed' ? (
//                                 <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
//                               ) : (
//                                 <AlertCircle className="h-4 w-4 text-yellow-500 mr-2" />
//                               )}
//                               <strong>{stage.title}:</strong>
//                               <div className="ml-1 text-sm capitalize">{stage.status}</div>
//                             </div>
//                           ))}
//                         </div>
//                       </AccordionContent>
//                     </AccordionItem>
//                   ))}
//                 </Accordion>
//                 {/* Simple Documents List */}
//                 <div className="space-y-4">
//                   {currentProject.tenderFile && (
//                     <Card>
//                       <CardContent className="p-4">
//                         <div className="flex items-center gap-3">
//                           <FileText className="h-5 w-5 text-green-600" />
//                           <div className="flex-1">
//                             <div className="font-medium">{currentProject.tenderFile.name}</div>
//                             <div className="text-sm text-muted-foreground">
//                               Uploaded on {new Date(currentProject.tenderFile.uploadDate).toLocaleDateString()}
//                             </div>
//                           </div>
//                           <Badge variant="secondary">Tender</Badge>
//                         </div>
//                       </CardContent>
//                     </Card>
//                   )}
                  
//                   {currentProject.bidFiles.map((file) => (
//                     <Card key={file.id}>
//                       <CardContent className="p-4">
//                         <div className="flex items-center gap-3">
//                           <FileText className="h-5 w-5 text-orange-600" />
//                           <div className="flex-1">
//                             <div className="font-medium">{file.name}</div>
//                             <div className="text-sm text-muted-foreground">
//                               {file.bidderName} • Uploaded on {new Date(file.uploadDate).toLocaleDateString()}
//                             </div>
//                           </div>
//                           <Badge variant="outline">Bid</Badge>
//                         </div>
//                       </CardContent>
//                     </Card>
//                   ))}
//                 </div>
//               </TabsContent>

//               <TabsContent value="processing" className="space-y-6">
//                 <ProcessingView 
//                   files={[
//                     ...(currentProject.tenderFile ? [currentProject.tenderFile] : []),
//                     ...currentProject.bidFiles
//                   ]}
//                   onProcessingComplete={handleProcessingComplete}
//                 />
//               </TabsContent>

//               <TabsContent value="results" className="space-y-6">
//                 <ComparisonView
//                   comparisons={[]} // Replace with real data as needed
//                   explanation="" // Replace with real data as needed
//                   onGenerateReport={handleGenerateReport}
//                 />
//               </TabsContent>
//             </Tabs>
//           </div>
//         )}

//         {!currentProject && !isLoading && (
//           <div className="text-center py-12">
//             <FolderOpen className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
//             <h3 className="text-lg font-semibold mb-2">No Project Selected</h3>
//             <p className="text-muted-foreground">
//               Select a project from the sidebar or create a new one to get started.
//             </p>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// };

// export default Dashboard;
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

// --- Configuration ---
const API_BASE_URL = 'http://localhost:8000';

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

  // Mock stages data (in real scenario, fetch from backend)
  const stages = [
    { id: 1, title: 'Parsing and creating structure', status: 'completed' },
    { id: 2, title: 'Finding technical and price compliance from TOC', status: 'pending' },
    { id: 3, title: 'Finding compliance requirements from tree', status: 'pending' },
    { id: 4, title: 'Converting to dataframes & excel sheets', status: 'pending' },
    { id: 5, title: 'Transforming into JSON files', status: 'pending' },
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
        {currentProject && activeProjectId && (
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
                    <Card>
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
                    <Card key={file.id}>
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
                  projectId={activeProjectId}  // Pass project ID to ProcessingView
                  onProcessingComplete={handleProcessingComplete}
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
