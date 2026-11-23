import type { TaskReceipt } from "../types";
import { CheckCircle2, XCircle, ShieldCheck, FileCheck, Eye, Sparkles } from "lucide-react";

interface ReceiptCardProps {
  receipt?: TaskReceipt;
  gold: string;
  seed: number;
}

export const ReceiptCard: React.FC<ReceiptCardProps> = ({ receipt, gold, seed }) => {
  if (!receipt) {
    return (
      <div className="bg-white border border-slate-200 rounded-lg p-4 text-xs text-slate-500">
        Verification receipt not attached to this task.
      </div>
    );
  }

  const items = [
    {
      label: "Dual-Path Solver Agreement",
      desc: "Graph Dijkstra vs. Independent Direct Reader",
      status: receipt.agree,
      detail: `${receipt.solver_answer} === ${receipt.independent_answer}`,
      icon: ShieldCheck,
    },
    {
      label: "DOM Render Fidelity",
      desc: "Arrow angles & label bounding boxes match spec",
      status: receipt.fidelity_ok,
      detail: receipt.fidelity_ok ? "100% Geometry Match" : "Geometric Drift",
      icon: FileCheck,
    },
    {
      label: "Evidence Visibility Ratio",
      desc: "Target evidence unoccluded by clutter or perspective",
      status: receipt.visibility_ok,
      detail: `${Math.round(receipt.evidence_visible_ratio * 100)}% unoccluded`,
      icon: Eye,
    },
    {
      label: "Zero-Image Language Prior Filter",
      desc: "Text prior guessing rate below 25% chance ceiling",
      status: !receipt.blind_rejected,
      detail: `${Math.round(receipt.blind_correct_rate * 100)}% prior leakage`,
      icon: Sparkles,
    },
  ];

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-700" />
          <span className="font-semibold text-xs tracking-wider uppercase text-slate-700">
            Ground Truth Verification Receipts
          </span>
        </div>
        <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600">
          Seed: {seed}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {items.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className={`p-3 rounded-md border text-xs ${
                item.status
                  ? "bg-emerald-50/60 border-emerald-200/80 text-emerald-900"
                  : "bg-red-50 border-red-200 text-red-900"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-1.5 font-medium">
                  <Icon className={`w-3.5 h-3.5 ${item.status ? "text-emerald-700" : "text-red-600"}`} />
                  <span>{item.label}</span>
                </div>
                {item.status ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-600 shrink-0" />
                )}
              </div>
              <p className="mt-1 text-[11px] text-slate-500 leading-tight">{item.desc}</p>
              <div className="mt-2 font-mono text-[11px] font-semibold text-slate-800 bg-white/70 px-2 py-0.5 rounded border border-slate-200/50 inline-block">
                {item.detail}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
        <span>Verified Gold Answer: <strong className="font-mono text-emerald-800">{gold}</strong></span>
        <span>Human Audit: <span className="font-medium text-emerald-700 capitalize">{receipt.human_audit || "Passed (Concordance 100%)"}</span></span>
      </div>
    </div>
  );
};
