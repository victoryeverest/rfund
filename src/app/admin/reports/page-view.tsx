"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_REPORT_QUERY } from "@/graphql/operations";
import { titleize } from "@/lib/money";
import { Download } from "lucide-react";

const REPORTS = [
  { value: "agent_performance", label: "Agent performance" },
  { value: "loan_portfolio", label: "Loan portfolio" },
  { value: "savings", label: "Savings" },
  { value: "customer_growth", label: "Customer growth" },
];

function parseCsv(csv: string): { headers: string[]; rows: string[][] } {
  const lines = csv.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return { headers: [], rows: [] };
  const split = (line: string) => {
    const out: string[] = [];
    let cur = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === "," && !inQuotes) {
        out.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out;
  };
  const headers = split(lines[0]);
  const rows = lines.slice(1).map(split);
  return { headers, rows };
}

export default function AdminReportsPage() {
  const [reportType, setReportType] = useState(REPORTS[0].value);
  const { data, loading, error, refetch } = useQuery(ADMIN_REPORT_QUERY, {
    variables: { reportType },
    fetchPolicy: "cache-and-network",
  });

  const csv = data?.adminReport ?? "";
  const parsed = useMemo(() => parseCsv(csv), [csv]);

  const download = () => {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rfund-${reportType}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <PageHeader
        title="Reports & exports"
        description="Operational reports as CSV. Every export is recorded in the audit trail."
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {REPORTS.map((r) => (
          <Button
            key={r.value}
            variant={reportType === r.value ? "default" : "outline"}
            className={`min-h-11 font-bold ${reportType === r.value ? "bg-rfund-700 text-white" : ""}`}
            onClick={() => setReportType(r.value)}
          >
            {r.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <LoadingState label={`Building ${titleize(reportType)} report…`} />
      ) : error ? (
        <ErrorState message="We could not build this report (permission required)." onRetry={() => refetch()} />
      ) : !csv ? (
        <EmptyState title="Report is empty." description="No data available for this report yet." />
      ) : (
        <SectionCard
          title={`${titleize(reportType)} — ${parsed.rows.length} rows`}
          action={
            <Button
              size="sm"
              className="min-h-10 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
              onClick={download}
            >
              <Download className="mr-1.5 h-4 w-4" aria-hidden /> Download CSV
            </Button>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  {parsed.headers.map((h) => (
                    <th key={h} className="py-2 pr-4 font-semibold">{titleize(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {parsed.rows.map((row, i) => (
                  <tr key={i} className="border-b border-rfund-line/60 last:border-0">
                    {row.map((cell, j) => (
                      <td key={j} className="py-2 pr-4 whitespace-nowrap">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
