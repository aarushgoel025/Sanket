import { useEffect, useState } from "react";
import type { MinimalPair, AskResult } from "../types";
import { GitCompare, CheckCircle2, XCircle, Bot, Play, Sparkles } from "lucide-react";

export const MinimalPairsView: React.FC = () => {
  const [pairs, setPairs] = useState<MinimalPair[]>([]);
  const [selectedPairId, setSelectedPairId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [model, setModel] = useState<string>("gemini_flash");
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [resultA, setResultA] = useState<AskResult | null>(null);
  const [resultB, setResultB] = useState<AskResult | null>(null);

  useEffect(() => {
    fetch("/api/pairs")
      .then((res) => res.json())
      .then((data: MinimalPair[]) => {
        setPairs(data);
        if (data.length > 0) setSelectedPairId(data[0].pair_id);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed loading minimal pairs:", err);
        setLoading(false);
      });
  }, []);

  const currentPair = pairs.find((p) => p.pair_id === selectedPairId) || pairs[0];

  const handleEvaluatePair = async () => {
    if (!currentPair) return;
    setEvaluating(true);
    setResultA(null);
    setResultB(null);

    try {
      const [resA, resB] = await Promise.all([
        fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: currentPair.task_a.task_id,
            model_name: model,
            mode: "image",
          }),
        }).then((r) => r.json()),
        fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            task_id: currentPair.task_b.task_id,
            model_name: model,
            mode: "image",
          }),
        }).then((r) => r.json()),
      ]);

      setResultA(resA);
      setResultB(resB);
    } catch (err) {
      console.error("Pair evaluation failed:", err);
    } finally {
      setEvaluating(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-slate-500">
        Loading minimal counterfactual pairs...
      </div>
    );
  }

  if (pairs.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-slate-500 bg-white border border-slate-200 rounded-lg">
        No minimal pairs found in sample tasks dataset.
      </div>
    );
  }

  const bothCorrect = resultA?.is_correct && resultB?.is_correct;
  const pairConsistent =
    resultA && resultB && resultA.model_answer !== resultB.model_answer && bothCorrect;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Intro Header */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6 shadow-xs">
        <div className="flex items-center space-x-2 mb-2">
          <GitCompare className="w-5 h-5 text-emerald-800" />
          <h2 className="text-base font-bold text-slate-900">
            Counterfactual Minimal Pairs (Causal Visual Sensitivity)
          </h2>
        </div>
        <p className="text-xs text-slate-600 max-w-3xl leading-relaxed">
          A minimal pair contains two tasks differing by an <strong>atomic visual alteration</strong> (e.g., rotating
          an arrow 45°, affixing a closure sticker, or moving a destination text entry). This tests whether models
          truly ground spatial visual cues or rely on statistical text priors.
        </p>

        {/* Pair selector pills */}
        <div className="mt-4 pt-3 border-t border-slate-100 flex items-center space-x-2 overflow-x-auto">
          <span className="text-xs font-semibold uppercase text-slate-500 shrink-0">Select Pair:</span>
          {pairs.map((p) => (
            <button
              key={p.pair_id}
              onClick={() => {
                setSelectedPairId(p.pair_id);
                setResultA(null);
                setResultB(null);
              }}
              className={`text-xs px-3 py-1.5 rounded-md font-mono transition-all shrink-0 ${
                p.pair_id === currentPair.pair_id
                  ? "bg-emerald-900 text-white font-bold shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              [{p.qtype}] {p.pair_id}
            </button>
          ))}
        </div>
      </div>

      {/* Model test bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <Bot className="w-4 h-4 text-emerald-800" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-700">Test Visual Grounding:</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="text-xs rounded border border-slate-300 p-1.5 bg-white font-medium"
          >
            <option value="gemini_flash">Gemini 1.5 Flash (VLM)</option>
            <option value="oracle">Oracle (Ground Truth Verifier)</option>
            <option value="random_baseline">Random Baseline</option>
          </select>
        </div>

        <button
          onClick={handleEvaluatePair}
          disabled={evaluating}
          className="flex items-center space-x-2 px-4 py-1.5 rounded-md bg-emerald-900 text-white font-semibold text-xs hover:bg-emerald-800 transition-colors shadow-xs disabled:opacity-50"
        >
          {evaluating ? (
            <>
              <Sparkles className="w-3.5 h-3.5 animate-spin text-emerald-400" />
              <span>Evaluating Both Signs...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Evaluate Pair Consistency</span>
            </>
          )}
        </button>
      </div>

      {/* Consistency result banner */}
      {resultA && resultB && (
        <div
          className={`p-4 mb-6 rounded-lg border text-xs flex items-center justify-between ${
            pairConsistent
              ? "bg-emerald-50 border-emerald-300 text-emerald-950"
              : "bg-rose-50 border-rose-300 text-rose-950"
          }`}
        >
          <div className="flex items-center space-x-2 font-bold text-sm">
            {pairConsistent ? (
              <>
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>JOINT PAIR CONSISTENT — Model flipped prediction appropriately!</span>
              </>
            ) : (
              <>
                <XCircle className="w-5 h-5 text-rose-600" />
                <span>
                  PAIR INCONSISTENT — Model failed to recognize the visual alteration or predicted incorrectly.
                </span>
              </>
            )}
          </div>
          <span className="font-mono text-xs">
            A: {resultA.model_answer} (Gold: {currentPair.gold_a}) | B: {resultB.model_answer} (Gold:{" "}
            {currentPair.gold_b})
          </span>
        </div>
      )}

      {/* Side-by-Side Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Task A (Base) */}
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs flex flex-col">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-slate-800">
              Task A: Base Signboard ({currentPair.task_a.task_id})
            </span>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 font-bold border border-emerald-200">
              Gold: {currentPair.gold_a}
            </span>
          </div>

          <div className="p-4 bg-slate-900/90 flex justify-center items-center h-80">
            <img
              src={currentPair.task_a.image_url}
              alt="Base task"
              className="max-h-72 w-auto object-contain rounded"
            />
          </div>

          <div className="p-4 flex-1 flex flex-col justify-between">
            <div>
              <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">Question</span>
              <p className="text-xs font-medium text-slate-900 mb-3">{currentPair.task_a.question}</p>
            </div>

            {resultA && (
              <div
                className={`p-2.5 rounded border text-xs flex items-center justify-between ${
                  resultA.is_correct
                    ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                    : "bg-rose-50 border-rose-200 text-rose-900"
                }`}
              >
                <span>
                  Model Answer: <strong>{resultA.model_answer}</strong>
                </span>
                <span className="font-semibold">{resultA.is_correct ? "CORRECT" : "WRONG"}</span>
              </div>
            )}
          </div>
        </div>

        {/* Task B (Counterfactual Variant) */}
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs flex flex-col">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex items-center justify-between">
            <span className="font-bold text-xs uppercase tracking-wider text-slate-800">
              Task B: Counterfactual Variant ({currentPair.task_b.task_id})
            </span>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-800 font-bold border border-amber-200">
              Gold: {currentPair.gold_b}
            </span>
          </div>

          <div className="p-4 bg-slate-900/90 flex justify-center items-center h-80">
            <img
              src={currentPair.task_b.image_url}
              alt="Counterfactual task"
              className="max-h-72 w-auto object-contain rounded"
            />
          </div>

          <div className="p-4 flex-1 flex flex-col justify-between">
            <div>
              <span className="text-[11px] font-semibold uppercase text-slate-400 block mb-1">Question</span>
              <p className="text-xs font-medium text-slate-900 mb-3">{currentPair.task_b.question}</p>
            </div>

            {resultB && (
              <div
                className={`p-2.5 rounded border text-xs flex items-center justify-between ${
                  resultB.is_correct
                    ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                    : "bg-rose-50 border-rose-200 text-rose-900"
                }`}
              >
                <span>
                  Model Answer: <strong>{resultB.model_answer}</strong>
                </span>
                <span className="font-semibold">{resultB.is_correct ? "CORRECT" : "WRONG"}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
