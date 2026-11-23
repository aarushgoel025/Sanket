import { useState } from "react";
import type { AskResult } from "../types";
import { Play, CheckCircle2, XCircle, Clock, Database, ChevronDown, ChevronUp, Bot, Sparkles } from "lucide-react";

interface ModelEvaluatorProps {
  taskId: string;
  gold?: string;
}

export const ModelEvaluator: React.FC<ModelEvaluatorProps> = ({ taskId }) => {
  const [model, setModel] = useState<string>("oracle");
  const [mode, setMode] = useState<string>("image");
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [showRaw, setShowRaw] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const models = [
    { id: "oracle", label: "Oracle (Ground Truth Verifier)", badge: "Instant" },
    { id: "random_baseline", label: "Random Baseline (~10% Chance)", badge: "Baseline" },
    { id: "always_ahead", label: "Always AHEAD (Heuristic)", badge: "Bias Test" },
    { id: "gemini_flash", label: "Gemini 1.5 Flash (Vision-Language)", badge: "VLM" },
  ];

  const handleAsk = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          model_name: model,
          mode: mode,
          prompt_version: "v1",
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server responded with ${res.status}`);
      }

      const data: AskResult = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed querying model");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
        <div className="flex items-center space-x-2">
          <Bot className="w-4 h-4 text-emerald-800" />
          <span className="font-semibold text-xs tracking-wider uppercase text-slate-700">
            Model Evaluation Harness
          </span>
        </div>
        <span className="text-xs text-slate-500">Dual Modality (Vision vs. Text)</span>
      </div>

      {/* Controls row */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 mb-4">
        {/* Model dropdown */}
        <div className="sm:col-span-6">
          <label className="block text-xs font-medium text-slate-700 mb-1">Select Evaluator Model</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full text-xs rounded-md border border-slate-300 bg-white px-2.5 py-1.5 font-medium text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-emerald-700"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* Mode selector */}
        <div className="sm:col-span-3">
          <label className="block text-xs font-medium text-slate-700 mb-1">Evaluation Mode</label>
          <div className="flex rounded-md border border-slate-200 bg-slate-100 p-0.5">
            <button
              onClick={() => setMode("image")}
              className={`flex-1 text-xs py-1 rounded font-medium transition-colors ${
                mode === "image" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Image (VLM)
            </button>
            <button
              onClick={() => setMode("text")}
              className={`flex-1 text-xs py-1 rounded font-medium transition-colors ${
                mode === "text" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Text (LLM)
            </button>
          </div>
        </div>

        {/* Run Button */}
        <div className="sm:col-span-3 flex items-end">
          <button
            onClick={handleAsk}
            disabled={loading}
            className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-md bg-emerald-900 text-white text-xs font-semibold hover:bg-emerald-800 transition-colors shadow-xs disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                <span>Querying...</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1">
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Ask Model</span>
              </span>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 mb-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-start space-x-2">
          <XCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-600" />
          <div>{error}</div>
        </div>
      )}

      {/* Result Card */}
      {result && (
        <div
          className={`p-3.5 rounded-lg border transition-all ${
            result.is_correct
              ? "bg-emerald-50/70 border-emerald-300 text-emerald-950"
              : "bg-rose-50/70 border-rose-300 text-rose-950"
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {result.is_correct ? (
                <div className="flex items-center space-x-1 text-emerald-800 font-bold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <span>CORRECT VERDICT</span>
                </div>
              ) : (
                <div className="flex items-center space-x-1 text-rose-800 font-bold text-sm">
                  <XCircle className="w-5 h-5 text-rose-600" />
                  <span>WRONG PREDICTION</span>
                </div>
              )}
            </div>

            <div className="flex items-center space-x-2 text-xs text-slate-500">
              <span className="flex items-center font-mono">
                <Clock className="w-3.5 h-3.5 mr-1" />
                {result.latency_s}s
              </span>
              <span className="flex items-center font-mono px-2 py-0.5 rounded bg-white/70 border border-slate-200 text-slate-700">
                <Database className="w-3 h-3 mr-1 text-slate-400" />
                {result.source}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-slate-200/60">
            <div>
              <span className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">Model Output</span>
              <div className="font-mono text-base font-bold mt-0.5 text-slate-900">
                {result.model_answer}
              </div>
            </div>
            <div>
              <span className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">Ground Truth Gold</span>
              <div className="font-mono text-base font-bold mt-0.5 text-emerald-800">
                {result.gold_answer}
              </div>
            </div>
          </div>

          {/* Raw response toggle */}
          <div className="mt-3 pt-2 border-t border-slate-200/50">
            <button
              onClick={() => setShowRaw(!showRaw)}
              className="text-xs text-slate-600 hover:text-slate-900 flex items-center space-x-1 font-medium"
            >
              <span>{showRaw ? "Hide Raw Response" : "View Raw Response & Traces"}</span>
              {showRaw ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showRaw && (
              <pre className="mt-2 p-2.5 bg-slate-900 text-slate-200 rounded text-[11px] font-mono whitespace-pre-wrap overflow-x-auto max-h-48 border border-slate-800">
                {result.raw_response}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
