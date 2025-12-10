'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { getContractDetails, ContractDetails } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ContractSummary from '@/components/ContractSummary';
import RiskHeatmap from '@/components/RiskHeatmap';
import ChatInterface from '@/components/ChatInterface';
import CostDashboard from '@/components/CostDashboard';

interface PageProps {
  params: Promise<{
    contractId: string;
  }>;
}

export default function DashboardPage({ params }: PageProps) {
  const router = useRouter();
  const [contractId, setContractId] = useState<string | null>(null);
  const [contract, setContract] = useState<ContractDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    params.then((resolvedParams) => {
      setContractId(resolvedParams.contractId);
    });
  }, [params]);

  useEffect(() => {
    if (!contractId) return;

    let cancelled = false;

    const fetchContract = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getContractDetails(contractId);

        if (!cancelled) {
          setContract(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Failed to load contract details'
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchContract();

    return () => {
      cancelled = true;
    };
  }, [contractId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading contract analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !contract) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="max-w-md w-full p-8 text-center">
          <div className="mb-6">
            <div className="h-16 w-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">⚠️</span>
            </div>
            <h2 className="text-2xl font-bold mb-2">Error Loading Contract</h2>
            <p className="text-muted-foreground">
              {error || 'Contract not found'}
            </p>
          </div>
          <Button onClick={() => router.push('/')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push('/')}
                className="mb-2"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Home
              </Button>
              <h1 className="text-2xl font-bold">
                {contract.metadata.filename}
              </h1>
              <p className="text-sm text-muted-foreground">
                Contract ID: {contract.contract_id}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <Tabs defaultValue="summary" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-4">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="risks">Risks</TabsTrigger>
            <TabsTrigger value="chat">Chat</TabsTrigger>
            <TabsTrigger value="costs">Costs</TabsTrigger>
          </TabsList>

          <TabsContent value="summary" className="space-y-6">
            <ContractSummary contract={contract} />
          </TabsContent>

          <TabsContent value="risks" className="space-y-6">
            <RiskHeatmap riskFactors={contract.risk_factors} />
          </TabsContent>

          <TabsContent value="chat" className="space-y-6">
            <ChatInterface contractId={contract.contract_id} />
          </TabsContent>

          <TabsContent value="costs" className="space-y-6">
            <CostDashboard />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
