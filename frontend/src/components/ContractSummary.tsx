'use client';

import { memo } from 'react';
import { FileText, Calendar, Users, Shield } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ContractDetails } from '@/lib/api';

interface ContractSummaryProps {
  contract: ContractDetails;
}

function getRiskBadgeVariant(
  score: number
): 'default' | 'secondary' | 'destructive' {
  if (score < 40) return 'default'; // green
  if (score < 70) return 'secondary'; // yellow
  return 'destructive'; // red
}

function getRiskLabel(score: number): string {
  if (score < 40) return 'Low Risk';
  if (score < 70) return 'Medium Risk';
  return 'High Risk';
}

function ContractSummary({ contract }: ContractSummaryProps) {
  const { metadata, key_terms, risk_score, summary } = contract;

  return (
    <div className="space-y-6">
      {/* Metadata Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Contract Overview
            </CardTitle>
            <Badge variant={getRiskBadgeVariant(risk_score)}>
              {getRiskLabel(risk_score)} ({risk_score}/100)
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <FileText className="h-4 w-4" />
                  <span>Filename</span>
                </div>
                <p className="font-medium">{metadata.filename}</p>
              </div>

              <div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <Calendar className="h-4 w-4" />
                  <span>Uploaded</span>
                </div>
                <p className="font-medium">
                  {new Date(metadata.uploaded_at).toLocaleString()}
                </p>
              </div>

              {metadata.effective_date && (
                <div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                    <Calendar className="h-4 w-4" />
                    <span>Effective Date</span>
                  </div>
                  <p className="font-medium">{metadata.effective_date}</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                  <Users className="h-4 w-4" />
                  <span>Parties</span>
                </div>
                <div className="space-y-1">
                  {metadata.parties.map((party, idx) => (
                    <p key={idx} className="font-medium">
                      {party}
                    </p>
                  ))}
                </div>
              </div>

              {metadata.contract_type && (
                <div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                    <Shield className="h-4 w-4" />
                    <span>Type</span>
                  </div>
                  <p className="font-medium">{metadata.contract_type}</p>
                </div>
              )}
            </div>
          </div>

          {summary && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="font-medium mb-2">Summary</h4>
              <p className="text-sm text-muted-foreground">{summary}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Key Terms Card */}
      <Card>
        <CardHeader>
          <CardTitle>Key Terms</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {key_terms.map((term, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex items-start justify-between">
                  <h4 className="font-medium">{term.term}</h4>
                  {term.section && (
                    <Badge variant="outline" className="text-xs">
                      {term.section}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  {term.description}
                </p>
              </div>
            ))}
          </div>

          {key_terms.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No key terms identified
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default memo(ContractSummary);
