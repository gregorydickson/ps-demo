'use client';

import { useRouter } from 'next/navigation';
import { Scale, Shield, Brain, TrendingUp } from 'lucide-react';
import FileUpload from '@/components/FileUpload';

export default function Home() {
  const router = useRouter();

  const handleUploadSuccess = (contractId: string) => {
    router.push(`/dashboard/${contractId}`);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
              <Scale className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Legal Contract Intelligence</h1>
              <p className="text-sm text-muted-foreground">
                AI-powered contract analysis platform
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-12">
        <div className="max-w-5xl mx-auto space-y-12">
          {/* Hero Section */}
          <div className="text-center space-y-4">
            <h2 className="text-4xl font-bold tracking-tight">
              Analyze Legal Contracts with AI
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Upload your PDF contracts and get instant AI-powered analysis,
              risk assessment, and intelligent Q&A capabilities.
            </p>
          </div>

          {/* Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex flex-col items-center text-center p-6 rounded-lg border bg-card">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Brain className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-2">Smart Analysis</h3>
              <p className="text-sm text-muted-foreground">
                Advanced AI extracts key terms, parties, and critical clauses
                automatically
              </p>
            </div>

            <div className="flex flex-col items-center text-center p-6 rounded-lg border bg-card">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-2">Risk Assessment</h3>
              <p className="text-sm text-muted-foreground">
                Identify potential risks and get actionable recommendations for
                mitigation
              </p>
            </div>

            <div className="flex flex-col items-center text-center p-6 rounded-lg border bg-card">
              <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <TrendingUp className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold mb-2">Interactive Q&A</h3>
              <p className="text-sm text-muted-foreground">
                Ask questions about your contract and get instant, accurate
                answers
              </p>
            </div>
          </div>

          {/* Upload Section */}
          <div className="flex justify-center">
            <FileUpload onUploadSuccess={handleUploadSuccess} />
          </div>

          {/* Footer Info */}
          <div className="text-center text-sm text-muted-foreground">
            <p>
              Powered by Google Gemini, LlamaParse, LangGraph, ChromaDB, and
              FalkorDB
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
