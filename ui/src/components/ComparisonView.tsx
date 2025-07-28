import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CheckCircle, XCircle, AlertCircle, Award, DollarSign, FileCheck } from 'lucide-react';

interface BidComparison {
  bidId: string;
  bidderName: string;
  technicalScore: number;
  priceScore: number;
  overallScore: number;
  status: 'winner' | 'qualified' | 'disqualified';
  technicalCompliance: {
    compliant: number;
    nonCompliant: number;
    total: number;
  };
  priceCompliance: {
    totalPrice: number;
    breakdown: Record<string, number>;
  };
}

interface ComparisonViewProps {
  comparisons: BidComparison[];
  explanation: string;
  onGenerateReport: () => void;
}

const ComparisonView = ({ comparisons, explanation, onGenerateReport }: ComparisonViewProps) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'winner':
        return 'text-success';
      case 'qualified':
        return 'text-info';
      default:
        return 'text-destructive';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'winner':
        return <Award className="h-4 w-4 text-success" />;
      case 'qualified':
        return <CheckCircle className="h-4 w-4 text-info" />;
      default:
        return <XCircle className="h-4 w-4 text-destructive" />;
    }
  };

  const sortedComparisons = [...comparisons].sort((a, b) => b.overallScore - a.overallScore);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Bid Comparison Results</h2>
        <Button onClick={onGenerateReport} className="shadow-soft">
          <FileCheck className="h-4 w-4 mr-2" />
          Generate Report
        </Button>
      </div>

      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="technical">Technical Analysis</TabsTrigger>
          <TabsTrigger value="explanation">AI Explanation</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid gap-4">
            {sortedComparisons.map((bid, index) => (
              <Card key={bid.bidId} className={`shadow-medium ${bid.status === 'winner' ? 'ring-2 ring-success' : ''}`}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-2xl font-bold text-muted-foreground">#{index + 1}</span>
                        {getStatusIcon(bid.status)}
                      </div>
                      <div>
                        <CardTitle className="text-lg">{bid.bidderName}</CardTitle>
                        <Badge 
                          variant="outline" 
                          className={`mt-1 ${getStatusColor(bid.status)} border-current`}
                        >
                          {bid.status.charAt(0).toUpperCase() + bid.status.slice(1)}
                        </Badge>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-primary">{bid.overallScore}%</div>
                      <p className="text-sm text-muted-foreground">Overall Score</p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="flex items-center gap-3 p-3 bg-accent rounded-lg">
                      <FileCheck className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">{bid.technicalScore}%</p>
                        <p className="text-sm text-muted-foreground">Technical Score</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-accent rounded-lg">
                      <DollarSign className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">{bid.priceScore}%</p>
                        <p className="text-sm text-muted-foreground">Price Score</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-accent rounded-lg">
                      <span className="text-lg">💰</span>
                      <div>
                        <p className="font-medium">${bid.priceCompliance.totalPrice.toLocaleString()}</p>
                        <p className="text-sm text-muted-foreground">Total Price</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">
                      Technical: {bid.technicalCompliance.compliant}/{bid.technicalCompliance.total} compliant
                    </span>
                    <span className="text-muted-foreground">
                      {bid.technicalCompliance.nonCompliant} non-compliant items
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="technical" className="mt-6">
          <div className="grid gap-6">
            {sortedComparisons.map((bid) => (
              <Card key={bid.bidId} className="shadow-medium">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {getStatusIcon(bid.status)}
                    {bid.bidderName} - Technical Details
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-medium mb-2">Compliance Summary</h4>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>Compliant Items:</span>
                          <Badge variant="outline" className="text-success border-success">
                            {bid.technicalCompliance.compliant}
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span>Non-Compliant Items:</span>
                          <Badge variant="outline" className="text-destructive border-destructive">
                            {bid.technicalCompliance.nonCompliant}
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span>Total Items:</span>
                          <Badge variant="outline">
                            {bid.technicalCompliance.total}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Price Breakdown</h4>
                      <div className="space-y-2">
                        {Object.entries(bid.priceCompliance.breakdown).map(([item, price]) => (
                          <div key={item} className="flex justify-between">
                            <span className="text-sm">{item}:</span>
                            <span className="text-sm font-medium">${price.toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="explanation" className="mt-6">
          <Card className="shadow-medium">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-primary" />
                AI-Generated Explanation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose max-w-none">
                <div className="bg-accent p-4 rounded-lg">
                  <p className="whitespace-pre-wrap leading-relaxed">{explanation}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default ComparisonView;