import { useEffect, useState } from "react";
import type { FindingsData } from "../types";
import { BarChart3, TrendingDown, Eye, AlertOctagon, Layers, ShieldCheck } from "lucide-react";

export const FindingsView: React.FC = () => {
  const [data, setData] = useState<FindingsData | null>(null);
  const [selectedFigure, setSelectedFigure] = useState<string>("F1");
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    fetch("/api/findings")
      .then((res) => res.json())
      .then((resData: FindingsData) => {
        setData(resData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed loading findings:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-slate-500">
        Loading benchmark evaluation findings...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center text-slate-500 bg-white border border-slate-200 rounded-lg">
        Findings data unavailable.
      </div>
    );
  }

  const currentFigure = data.figures.find((f) => f.id === selectedFigure) || data.figures[0];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-8">
      {/* Page Title */}
      <div>
        <div className="flex items-center space-x-2">
          <BarChart3 className="w-5 h-5 text-emerald-800" />
          <h2 className="text-lg font-bold text-slate-900">Empirical Benchmark Findings & Diagnostics</h2>
        </div>
        <p className="text-xs text-slate-600 mt-1">
          Quantitative evaluation across image and text modalities. All reference answers derived from verified venue graphs.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Perception Gap (Δ)</span>
            <Eye className="w-4 h-4 text-emerald-700" />
          </div>
          <div className="text-2xl font-bold text-slate-900">+50.0 pp</div>
          <p className="text-[11px] text-slate-500 mt-1 leading-tight">
            Gemini Flash scores 83.3% on text vs. 33.3% on raw images (symbol binding bottleneck).
          </p>
        </div>

        {/* KPI 2 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">ABSENT Hallucination</span>
            <AlertOctagon className="w-4 h-4 text-rose-600" />
          </div>
          <div className="text-2xl font-bold text-rose-700">100.0%</div>
          <p className="text-[11px] text-slate-500 mt-1 leading-tight">
            Models assert a directional arrow 100% of the time when destinations are unlisted.
          </p>
        </div>

        {/* KPI 3 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Pair Consistency</span>
            <TrendingDown className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">0.0%</div>
          <p className="text-[11px] text-slate-500 mt-1 leading-tight">
            Joint consistency on counterfactual pairs: models fail to track subtle 45° arrow shifts.
          </p>
        </div>

        {/* KPI 4 */}
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Oracle Ground Truth</span>
            <ShieldCheck className="w-4 h-4 text-emerald-700" />
          </div>
          <div className="text-2xl font-bold text-emerald-800">100.0%</div>
          <p className="text-[11px] text-slate-500 mt-1 leading-tight">
            Cryptographic sanity check passes across all synthetic and real station photos.
          </p>
        </div>
      </div>

      {/* Publication Figures F1 - F6 Showcase */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
        <div className="px-5 py-3.5 border-b border-slate-100 bg-slate-50/70 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-emerald-800" />
            <span className="font-bold text-xs uppercase tracking-wider text-slate-700">
              Publication Figures (F1 – F6)
            </span>
          </div>
          {/* Figure selector tabs */}
          <div className="flex space-x-1 overflow-x-auto">
            {data.figures.map((fig) => (
              <button
                key={fig.id}
                onClick={() => setSelectedFigure(fig.id)}
                className={`text-xs px-2.5 py-1 rounded font-semibold transition-colors ${
                  selectedFigure === fig.id
                    ? "bg-emerald-900 text-white shadow-xs"
                    : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                }`}
              >
                {fig.id}
              </button>
            ))}
          </div>
        </div>

        {/* Active Figure Showcase */}
        {currentFigure && (
          <div className="p-6">
            <div className="mb-4">
              <span className="text-xs font-mono text-emerald-800 font-bold uppercase tracking-wider">
                {currentFigure.id}
              </span>
              <h3 className="text-base font-bold text-slate-900">{currentFigure.title}</h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed bg-emerald-50/60 p-2.5 rounded border border-emerald-100">
                <strong>Empirical Finding:</strong> {currentFigure.takeaway}
              </p>
            </div>

            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex justify-center items-center">
              <img
                src={currentFigure.url}
                alt={currentFigure.title}
                className="max-h-[480px] w-auto object-contain rounded shadow-xs"
              />
            </div>
          </div>
        )}
      </div>

      {/* Quantitative Model Performance Table */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
          Overall Model Performance & Wilson 95% Confidence Intervals
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase tracking-wider font-semibold">
              <tr>
                <th className="py-2.5 px-3">Model</th>
                <th className="py-2.5 px-3">Modality</th>
                <th className="py-2.5 px-3 text-center">Tasks</th>
                <th className="py-2.5 px-3 text-center">Correct</th>
                <th className="py-2.5 px-3 text-right">Exact Accuracy</th>
                <th className="py-2.5 px-3 text-right">95% Wilson Interval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {data.model_metrics.map((row, idx) => (
                <tr key={idx} className="hover:bg-slate-50/70">
                  <td className="py-2 px-3 font-sans font-medium text-slate-900">{row.model}</td>
                  <td className="py-2 px-3 font-sans">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        row.mode === "image"
                          ? "bg-slate-100 text-slate-800"
                          : "bg-emerald-50 text-emerald-800 border border-emerald-200"
                      }`}
                    >
                      {row.mode}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">{row.tasks}</td>
                  <td className="py-2 px-3 text-center">{row.correct}</td>
                  <td className="py-2 px-3 text-right font-bold text-slate-900">{row.acc}%</td>
                  <td className="py-2 px-3 text-right text-slate-500">{row.ci}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
