import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileText, Download, Eye, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface DocumentSection {
  id: string;
  title: string;
  type: 'technical' | 'price' | 'other';
  status: 'compliant' | 'non-compliant' | 'pending';
  tables: any[];
}

interface Document {
  id: string;
  name: string;
  type: 'tender' | 'bid';
  status: 'processing' | 'completed' | 'error';
  sections: DocumentSection[];
  toc: string[];
}

interface DocumentViewerProps {
  documents: Document[];
  onDownload: (docId: string, format: 'excel' | 'json') => void;
}

const DocumentViewer = ({ documents, onDownload }: DocumentViewerProps) => {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'compliant':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'non-compliant':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <AlertCircle className="h-4 w-4 text-warning" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'compliant':
        return <Badge variant="outline" className="text-success border-success">Compliant</Badge>;
      case 'non-compliant':
        return <Badge variant="outline" className="text-destructive border-destructive">Non-Compliant</Badge>;
      default:
        return <Badge variant="outline" className="text-warning border-warning">Pending</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {documents.map((doc) => (
        <Card key={doc.id} className="shadow-medium">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="h-6 w-6 text-primary" />
                <div>
                  <CardTitle className="text-lg">{doc.name}</CardTitle>
                  <p className="text-sm text-muted-foreground capitalize">{doc.type} Document</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={doc.status === 'completed' ? 'default' : 'secondary'}>
                  {doc.status}
                </Badge>
                <Button variant="outline" size="sm" onClick={() => onDownload(doc.id, 'excel')}>
                  <Download className="h-4 w-4 mr-1" />
                  Excel
                </Button>
                <Button variant="outline" size="sm" onClick={() => onDownload(doc.id, 'json')}>
                  <Download className="h-4 w-4 mr-1" />
                  JSON
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="sections" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="sections">Sections</TabsTrigger>
                <TabsTrigger value="toc">Table of Contents</TabsTrigger>
              </TabsList>
              <TabsContent value="sections" className="mt-4">
                <div className="space-y-3">
                  {doc.sections.map((section) => (
                    <div key={section.id} className="p-4 border rounded-lg bg-card">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(section.status)}
                          <h4 className="font-medium">{section.title}</h4>
                          <Badge variant="outline" className="text-xs">
                            {section.type}
                          </Badge>
                        </div>
                        {getStatusBadge(section.status)}
                      </div>
                      {section.tables.length > 0 && (
                        <p className="text-sm text-muted-foreground">
                          {section.tables.length} table(s) extracted
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>
              <TabsContent value="toc" className="mt-4">
                <div className="bg-muted p-4 rounded-lg">
                  <pre className="text-sm whitespace-pre-wrap font-mono">
                    {doc.toc.join('\n')}
                  </pre>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default DocumentViewer;