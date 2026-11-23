import { useEffect, useState } from "react";
import type { FailureCase } from "../types";
import { AlertTriangle, ShieldAlert, EyeOff } from "lucide-react";

export const FailureGalleryView: React.FC = () => {
  const [failures, setFailures] = useState<FailureCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetch("/api/failures")
      .then((res) => res.json())
      .then((data: FailureCase[]) => {
        setFailures(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed loading failures:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-slate-500">
        Loading failure gallery cases...
      </div>
    );
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "HIGH":
        return "bg-amber-100 text-amber-800 border-amber-300";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300";
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Intro Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <div className="flex items-center space-x-2 mb-2">
          <AlertTriangle className="w-5 h-5 text-rose-600" />
          <h2 className="text-base font-bold text-slate-900">
            Qualitative Failure Gallery & Real-World Safety Impact
          </h2>
        </div>
        <p className="text-xs text-slate-600 max-w-3xl leading-relaxed">
          Autonomous wayfinding and assistive mobility agents cannot afford silent perception errors. In critical
          public environments (railway junctions, airports, emergency hospitals), misreading a closed corridor or
          hallucinating non-existent signage creates immediate passenger safety hazards.
        </p>
      </div>

      {/* Failure Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {failures.map((item, idx) => (
          <div
            key={idx}
            className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs flex flex-col justify-between"
          >
            <div>
              {/* Card Header */}
              <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-slate-700">{item.task_id}</span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${getSeverityBadge(
                    item.severity
                  )}`}
                >
                  {item.severity} SEVERITY
                </span>
              </div>

              {/* Signboard Image */}
              <div className="p-3 bg-slate-900/90 flex justify-center items-center h-52">
                <img
                  src={item.image_url}
                  alt={`Failure task ${item.task_id}`}
                  className="max-h-48 w-auto object-contain rounded"
                />
              </div>

              {/* Details Body */}
              <div className="p-4 space-y-3">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                    Question
                  </span>
                  <p className="text-xs font-semibold text-slate-900">{item.question}</p>
                </div>

                {/* Answer comparison */}
                <div className="grid grid-cols-2 gap-2 p-2.5 bg-slate-50 rounded border border-slate-200/80 text-xs font-mono">
                  <div>
                    <span className="text-[10px] font-sans text-rose-600 font-bold block uppercase">
                      Model Predicted
                    </span>
                    <span className="text-slate-900 font-bold text-sm">{item.model_pred}</span>
                  </div>
                  <div>
                    <span className="text-[10px] font-sans text-emerald-700 font-bold block uppercase">
                      Ground Truth
                    </span>
                    <span className="text-emerald-800 font-bold text-sm">{item.gold}</span>
                  </div>
                </div>

                {/* Failure Taxonomy */}
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                    Failure Taxonomy
                  </span>
                  <span className="inline-flex items-center text-xs font-semibold text-rose-800 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                    <EyeOff className="w-3 h-3 mr-1" />
                    {item.failure_reason}
                  </span>
                  <p className="text-[11px] text-slate-600 mt-1 leading-snug">{item.explanation}</p>
                </div>
              </div>
            </div>

            {/* Real-World Safety Consequence */}
            <div className="p-4 bg-amber-50/70 border-t border-amber-200 text-xs">
              <div className="flex items-center space-x-1 font-bold text-amber-900 mb-1">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-700" />
                <span>Real-World Physical Consequence:</span>
              </div>
              <p className="text-amber-950 text-[11px] leading-tight font-medium">
                "{item.real_world_consequence}"
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
