import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Clock, 
  CheckCircle, 
  FileText,
  Play,
  Pause,
  SkipForward,
  AlertCircle
} from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';

interface ProjectFile {
  id: string;
  name: string;
  type: 'tender' | 'bid';
  bidderName?: string;
  uploadDate: string;
}

interface ProcessingStage {
  id: number;
  title: string;
  description: string;
  status: 'pending' | 'processing' | 'completed' | 'needs_verification';
}

interface ProcessingViewProps {
  files: ProjectFile[];
  onProcessingComplete: () => void;
}

interface StageResponse {
  [stageId: number]: string;
}

const processingStages: ProcessingStage[] = [
  {
    id: 1,
    title: "Parsing and creating structure",
    description: "Extracting and organizing document content",
    status: 'pending'
  },
  {
    id: 2,
    title: "Finding technical and price compliance from TOC",
    description: "Analyzing table of contents for compliance sections",
    status: 'pending'
  },
  {
    id: 3,
    title: "Finding compliance requirements from tree",
    description: "Mapping requirements to document structure",
    status: 'pending'
  },
  {
    id: 4,
    title: "Converting to dataframes & excel sheets",
    description: "Structuring data into processable formats",
    status: 'pending'
  },
  {
    id: 5,
    title: "Transforming into JSON files",
    description: "Creating final structured output",
    status: 'pending'
  }
];

const ProcessingView = ({ files, onProcessingComplete }: ProcessingViewProps) => {
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [currentStage, setCurrentStage] = useState(0);
  const [stages, setStages] = useState<ProcessingStage[]>(processingStages);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [showContinueDialog, setShowContinueDialog] = useState(false);
  const [stageResponses, setStageResponses] = useState<StageResponse>({});

  const currentFile = files[currentFileIndex];
  const isFirstFile = currentFileIndex === 0;
  const isLastFile = currentFileIndex === files.length - 1;

  // Refactored processNextStage to accept a stage index
  const processNextStage = (stageIndex: number) => {
    if (stageIndex < stages.length) {
      setStages(prev => prev.map((stage, index) =>
        index === stageIndex
          ? { ...stage, status: 'processing' }
          : stage
      ));
      // Simulate processing time
      setTimeout(() => {
        setStageResponses(prev => ({
          ...prev,
          [stages[stageIndex].id]: getSimulatedResponse(stages[stageIndex].id, currentFile.name)
        }));
        // Stage 1 does not require verification, auto-complete it
        if (stageIndex === 0) {
          setStages(prev => prev.map((stage, index) =>
            index === stageIndex
              ? { ...stage, status: 'completed' }
              : stage
          ));
          setCurrentStage(stageIndex + 1);
          setTimeout(() => processNextStage(stageIndex + 1), 500);
        } else {
          setStages(prev => prev.map((stage, index) =>
            index === stageIndex
              ? { ...stage, status: 'needs_verification' }
              : stage
          ));
          setNeedsVerification(true);
          setIsProcessing(false);
        }
      }, 2000);
    }
  };

  // Update startProcessing to use the new signature
  const startProcessing = () => {
    setIsProcessing(true);
    setIsPaused(false);
    processNextStage(currentStage);
  };

  // Simulate a response for each stage (in real app, this would come from backend)
  const getSimulatedResponse = (stageId: number, fileName: string) => {
    if (stageId === 1) {
      return `Created Tree structure for the pdf`;
    }
    return `Simulated response for stage ${stageId} of file ${fileName}`;
  };

  // Update verifyStage to use the new signature
  const verifyStage = () => {
    setStages(prev => prev.map((stage, index) =>
      index === currentStage
        ? { ...stage, status: 'completed' }
        : stage
    ));
    setNeedsVerification(false);
    if (currentStage < stages.length - 1) {
      setCurrentStage(prev => prev + 1);
      setIsProcessing(true);
      setTimeout(() => processNextStage(currentStage + 1), 500);
    } else {
      // File processing complete
      if (isFirstFile && !isLastFile) {
        setShowContinueDialog(true);
      } else if (isLastFile) {
        onProcessingComplete();
      } else {
        moveToNextFile();
      }
    }
  };

  // Update moveToNextFile to reset currentStage and start processing from stage 0
  const moveToNextFile = () => {
    setCurrentFileIndex(prev => prev + 1);
    setCurrentStage(0);
    setStages(processingStages.map(stage => ({ ...stage, status: 'pending' as const })));
    setIsProcessing(true);
    setTimeout(() => processNextStage(0), 500);
  };

  const continueWithRemainingFiles = () => {
    setShowContinueDialog(false);
    moveToNextFile();
  };

  const getStageIcon = (status: ProcessingStage['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'processing':
        return <Clock className="h-4 w-4 text-primary animate-spin" />;
      case 'needs_verification':
        return <AlertCircle className="h-4 w-4 text-warning" />;
      default:
        return <div className="h-4 w-4 rounded-full border-2 border-muted" />;
    }
  };

  const getFileStatusIcon = (index: number) => {
    if (index < currentFileIndex) {
      return <CheckCircle className="h-4 w-4 text-success" />;
    } else if (index === currentFileIndex) {
      return <Clock className="h-4 w-4 text-primary animate-spin" />;
    } else {
      return <FileText className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const progress = ((currentFileIndex * stages.length + currentStage + (currentStage < stages.length ? 1 : 0)) / (files.length * stages.length)) * 100;

  return (
    <div className="space-y-6">
      {/* Overall Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            Processing Documents
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-sm">
            <span>Overall Progress</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="w-full" />
          <div className="text-center text-sm text-muted-foreground">
            Processing {currentFileIndex + 1} of {files.length} documents
          </div>
        </CardContent>
      </Card>

      {/* Files List */}
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {files.map((file, index) => (
              <div 
                key={file.id} 
                className={`flex items-center gap-3 p-3 rounded-lg border ${
                  index === currentFileIndex ? 'bg-primary/5 border-primary/20' : 'bg-muted/20'
                }`}
              >
                {getFileStatusIcon(index)}
                <div className="flex-1">
                  <div className="font-medium text-sm">{file.name}</div>
                  {file.bidderName && (
                    <div className="text-xs text-muted-foreground">{file.bidderName}</div>
                  )}
                </div>
                <Badge variant={file.type === 'tender' ? 'secondary' : 'outline'}>
                  {file.type}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Current File Processing */}
      {currentFile && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Processing: {currentFile.name}</span>
              <div className="flex items-center gap-2">
                {!isProcessing && !needsVerification && (
                  <Button onClick={startProcessing} size="sm">
                    <Play className="h-4 w-4 mr-2" />
                    Start
                  </Button>
                )}
                {needsVerification && (
                  <Button onClick={verifyStage} size="sm" variant="secondary">
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Verify & Continue
                  </Button>
                )}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Accordion type="multiple" className="w-full">
                {stages.map((stage, index) => (
                  <AccordionItem key={stage.id} value={`stage-${stage.id}`}>
                    <AccordionTrigger>
                      <div className="flex items-center gap-4 w-full">
                        {getStageIcon(stage.status)}
                        <div className="flex-1 text-left">
                          <div className={`font-medium ${
                            stage.status === 'completed' ? 'text-success' :
                            stage.status === 'processing' ? 'text-primary' :
                            stage.status === 'needs_verification' ? 'text-warning' :
                            'text-muted-foreground'
                          }`}>
                            {stage.title.replace('{currently_processing_pdf}', currentFile.name)}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {stage.description}
                          </div>
                        </div>
                        {stage.status === 'needs_verification' && (
                          <Badge variant="outline" className="text-warning">
                            Needs Verification
                          </Badge>
                        )}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="p-2 bg-muted/40 rounded">
                        <strong>Stage Output:</strong>
                        <div className="mt-1 text-sm">
                          {stageResponses[stage.id] || <span className="italic text-muted-foreground">No output yet.</span>}
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Continue Dialog */}
      <Dialog open={showContinueDialog} onOpenChange={setShowContinueDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>First Document Processed</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-muted-foreground">
              The first document has been successfully processed. Would you like to continue 
              processing the remaining {files.length - 1} documents?
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowContinueDialog(false)}>
                Review First
              </Button>
              <Button onClick={continueWithRemainingFiles}>
                Continue Processing
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ProcessingView;