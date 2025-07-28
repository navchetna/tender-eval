import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  Upload, 
  FileText, 
  Eye, 
  BarChart3, 
  CheckCircle, 
  Clock, 
  AlertTriangle,
  Target,
  DollarSign,
  Users
} from 'lucide-react';
import FileUpload from './FileUpload';
import DocumentViewer from './DocumentViewer';
import ComparisonView from './ComparisonView';

// Mock data for demonstration
const mockDocuments = [
  {
    id: '1',
    name: 'Infrastructure Tender - Road Construction',
    type: 'tender' as const,
    status: 'completed' as const,
    sections: [
      {
        id: '1-1',
        title: 'Technical Requirements',
        type: 'technical' as const,
        status: 'compliant' as const,
        tables: [{}]
      },
      {
        id: '1-2',
        title: 'Price Schedule',
        type: 'price' as const,
        status: 'compliant' as const,
        tables: [{}]
      }
    ],
    toc: ['1. Introduction', '2. Technical Requirements', '3. Price Schedule', '4. Terms & Conditions']
  },
  {
    id: '2',
    name: 'Bid Response - ABC Construction',
    type: 'bid' as const,
    status: 'completed' as const,
    sections: [
      {
        id: '2-1',
        title: 'Technical Compliance',
        type: 'technical' as const,
        status: 'compliant' as const,
        tables: [{}]
      },
      {
        id: '2-2',
        title: 'Price Submission',
        type: 'price' as const,
        status: 'compliant' as const,
        tables: [{}]
      }
    ],
    toc: ['1. Company Profile', '2. Technical Compliance', '3. Price Submission', '4. Supporting Documents']
  }
];

const mockComparisons = [
  {
    bidId: '1',
    bidderName: 'ABC Construction Ltd.',
    technicalScore: 95,
    priceScore: 85,
    overallScore: 92,
    status: 'winner' as const,
    technicalCompliance: { compliant: 18, nonCompliant: 1, total: 19 },
    priceCompliance: { 
      totalPrice: 2450000, 
      breakdown: { 'Materials': 1200000, 'Labor': 800000, 'Equipment': 450000 }
    }
  },
  {
    bidId: '2',
    bidderName: 'XYZ Infrastructure Co.',
    technicalScore: 88,
    priceScore: 92,
    overallScore: 89,
    status: 'qualified' as const,
    technicalCompliance: { compliant: 16, nonCompliant: 3, total: 19 },
    priceCompliance: { 
      totalPrice: 2380000, 
      breakdown: { 'Materials': 1150000, 'Labor': 750000, 'Equipment': 480000 }
    }
  },
  {
    bidId: '3',
    bidderName: 'BuildTech Solutions',
    technicalScore: 75,
    priceScore: 78,
    overallScore: 76,
    status: 'disqualified' as const,
    technicalCompliance: { compliant: 12, nonCompliant: 7, total: 19 },
    priceCompliance: { 
      totalPrice: 2650000, 
      breakdown: { 'Materials': 1300000, 'Labor': 850000, 'Equipment': 500000 }
    }
  }
];

const mockExplanation = `Based on the comprehensive analysis of all submitted bids, ABC Construction Ltd. emerges as the winning bidder with an overall score of 92%.

Technical Evaluation:
ABC Construction demonstrates superior technical compliance with 18 out of 19 requirements fully met. Their proposed methodology shows deep understanding of the project requirements, with only minor documentation gaps in environmental impact assessments.

Price Evaluation:
While not the lowest bidder, ABC Construction offers excellent value for money at $2,450,000. Their pricing is competitive and well-justified with detailed cost breakdowns that demonstrate transparency and realistic project costing.

Key Differentiators:
1. Strong technical capability with proven track record
2. Comprehensive project management approach
3. Realistic timeline and resource allocation
4. Excellent safety protocols and environmental compliance

Recommendations:
Award the contract to ABC Construction Ltd. with conditions to address the minor environmental documentation gap within 30 days of contract signing.`;

const Dashboard = () => {
  const [tenderFiles, setTenderFiles] = useState<File[]>([]);
  const [bidFiles, setBidFiles] = useState<File[]>([]);
  const [activeTab, setActiveTab] = useState('upload');
  const [processStep, setProcessStep] = useState(0);

  const steps = [
    'Upload Documents',
    'Parse & Extract',
    'Analyze Compliance',
    'Generate Comparison',
    'Review Results'
  ];

  const handleProcess = () => {
    setActiveTab('processing');
    // Simulate processing steps
    let step = 0;
    const interval = setInterval(() => {
      step++;
      setProcessStep(step);
      if (step >= 5) {
        clearInterval(interval);
        setTimeout(() => setActiveTab('results'), 1000);
      }
    }, 1500);
  };

  const handleDownload = (docId: string, format: 'excel' | 'json') => {
    console.log(`Downloading ${format} for document ${docId}`);
    // Implement download logic
  };

  const handleGenerateReport = () => {
    console.log('Generating final report');
    // Implement report generation
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-gradient-to-r from-primary/5 to-accent/5">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">TenderEval</h1>
              <p className="text-muted-foreground mt-1">
                AI-Powered Tender & Bid Evaluation Platform
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

      {/* Stats Overview */}
      <div className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card className="shadow-soft">
            <CardContent className="p-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <FileText className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">12</p>
                  <p className="text-sm text-muted-foreground">Documents Processed</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="shadow-soft">
            <CardContent className="p-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-success/10 rounded-lg">
                  <CheckCircle className="h-5 w-5 text-success" />
                </div>
                <div>
                  <p className="text-2xl font-bold">8</p>
                  <p className="text-sm text-muted-foreground">Compliant Bids</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="shadow-soft">
            <CardContent className="p-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-warning/10 rounded-lg">
                  <DollarSign className="h-5 w-5 text-warning" />
                </div>
                <div>
                  <p className="text-2xl font-bold">$2.4M</p>
                  <p className="text-sm text-muted-foreground">Avg. Bid Value</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="shadow-soft">
            <CardContent className="p-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-info/10 rounded-lg">
                  <BarChart3 className="h-5 w-5 text-info" />
                </div>
                <div>
                  <p className="text-2xl font-bold">94%</p>
                  <p className="text-sm text-muted-foreground">Processing Accuracy</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4 mb-8">
            <TabsTrigger value="upload">
              <Upload className="h-4 w-4 mr-2" />
              Upload
            </TabsTrigger>
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

          <TabsContent value="upload" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FileUpload
                title="Upload Tender Documents"
                description="Upload the main tender document containing requirements and specifications"
                onFilesChange={setTenderFiles}
                files={tenderFiles}
                multiple={false}
              />
              <FileUpload
                title="Upload Bid Documents"
                description="Upload bid responses from different vendors for evaluation"
                onFilesChange={setBidFiles}
                files={bidFiles}
                multiple={true}
              />
            </div>
            
            {(tenderFiles.length > 0 || bidFiles.length > 0) && (
              <Card className="shadow-medium">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold mb-2">Ready to Process</h3>
                      <p className="text-muted-foreground">
                        {tenderFiles.length} tender document(s) and {bidFiles.length} bid document(s) uploaded
                      </p>
                    </div>
                    <Button 
                      onClick={handleProcess}
                      className="shadow-soft"
                      disabled={tenderFiles.length === 0 && bidFiles.length === 0}
                    >
                      Start Processing
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="documents" className="space-y-6">
            <DocumentViewer documents={mockDocuments} onDownload={handleDownload} />
          </TabsContent>

          <TabsContent value="processing" className="space-y-6">
            <Card className="shadow-medium">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-primary animate-spin" />
                  Processing Documents
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  {steps.map((step, index) => (
                    <div key={index} className="flex items-center gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        index < processStep ? 'bg-success text-success-foreground' :
                        index === processStep ? 'bg-primary text-primary-foreground' :
                        'bg-muted text-muted-foreground'
                      }`}>
                        {index < processStep ? <CheckCircle className="h-4 w-4" /> : index + 1}
                      </div>
                      <div className="flex-1">
                        <p className={`font-medium ${
                          index <= processStep ? 'text-foreground' : 'text-muted-foreground'
                        }`}>
                          {step}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <Progress value={(processStep / steps.length) * 100} className="w-full" />
                <p className="text-center text-muted-foreground">
                  {processStep < steps.length ? 
                    `Processing step ${processStep + 1} of ${steps.length}...` : 
                    'Processing complete!'
                  }
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="results" className="space-y-6">
            <ComparisonView
              comparisons={mockComparisons}
              explanation={mockExplanation}
              onGenerateReport={handleGenerateReport}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default Dashboard;