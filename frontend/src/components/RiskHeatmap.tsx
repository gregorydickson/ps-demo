'use client';

import { useState, memo } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RiskFactor } from '@/lib/api';

interface RiskHeatmapProps {
  riskFactors: RiskFactor[];
}

function getRiskColor(level: 'low' | 'medium' | 'high'): string {
  switch (level) {
    case 'low':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'medium':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'high':
      return 'bg-red-100 text-red-800 border-red-200';
  }
}

function getRiskBadgeVariant(
  level: 'low' | 'medium' | 'high'
): 'default' | 'secondary' | 'destructive' {
  switch (level) {
    case 'low':
      return 'default';
    case 'medium':
      return 'secondary';
    case 'high':
      return 'destructive';
  }
}

function getRiskPriority(level: 'low' | 'medium' | 'high'): number {
  switch (level) {
    case 'high':
      return 3;
    case 'medium':
      return 2;
    case 'low':
      return 1;
  }
}

function RiskHeatmap({ riskFactors }: RiskHeatmapProps) {
  const [expandedRisks, setExpandedRisks] = useState<Set<number>>(new Set());

  const toggleExpanded = (index: number) => {
    setExpandedRisks((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  // Sort by risk level (high to low)
  const sortedRisks = [...riskFactors].sort(
    (a, b) => getRiskPriority(b.risk_level) - getRiskPriority(a.risk_level)
  );

  // Count risks by level
  const riskCounts = riskFactors.reduce(
    (acc, risk) => {
      acc[risk.risk_level]++;
      return acc;
    },
    { low: 0, medium: 0, high: 0 }
  );

  return (
    <div className="space-y-6">
      {/* Risk Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-green-800">
              {riskCounts.low}
            </div>
            <div className="text-sm text-green-600">Low Risk</div>
          </CardContent>
        </Card>

        <Card className="border-yellow-200 bg-yellow-50/50">
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-yellow-800">
              {riskCounts.medium}
            </div>
            <div className="text-sm text-yellow-600">Medium Risk</div>
          </CardContent>
        </Card>

        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4">
            <div className="text-2xl font-bold text-red-800">
              {riskCounts.high}
            </div>
            <div className="text-sm text-red-600">High Risk</div>
          </CardContent>
        </Card>
      </div>

      {/* Risk Details */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Risk Factors
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {sortedRisks.map((risk, idx) => (
              <div
                key={idx}
                className={`border rounded-lg overflow-hidden transition-colors ${getRiskColor(
                  risk.risk_level
                )}`}
              >
                <button
                  onClick={() => toggleExpanded(idx)}
                  className="w-full p-4 flex items-start justify-between gap-4 text-left hover:opacity-80 transition-opacity"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <Badge variant={getRiskBadgeVariant(risk.risk_level)}>
                        {risk.risk_level.toUpperCase()}
                      </Badge>
                      <span className="text-xs font-medium opacity-70">
                        {risk.section}
                      </span>
                    </div>
                    <p className="font-medium">{risk.concern}</p>
                  </div>
                  <div className="flex-shrink-0">
                    {expandedRisks.has(idx) ? (
                      <ChevronUp className="h-5 w-5" />
                    ) : (
                      <ChevronDown className="h-5 w-5" />
                    )}
                  </div>
                </button>

                {expandedRisks.has(idx) && (
                  <div className="px-4 pb-4 pt-0 border-t border-current/10">
                    <div className="mt-3 space-y-2">
                      <div>
                        <h5 className="text-xs font-semibold opacity-70 mb-1">
                          Recommendation
                        </h5>
                        <p className="text-sm">{risk.recommendation}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {sortedRisks.length === 0 && (
            <div className="text-center py-12">
              <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">No risk factors identified</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default memo(RiskHeatmap);
