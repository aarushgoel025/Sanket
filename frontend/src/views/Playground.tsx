import { useState, useEffect } from "react";
import type { Task, VenueInfo } from "../types";
import { VenueMapSVG } from "../components/VenueMapSVG";
import { ReceiptCard } from "../components/ReceiptCard";
import { ModelEvaluator } from "../components/ModelEvaluator";
import {
  Sparkles,
  Filter,
  Eye,
  RefreshCw,
} from "lucide-react";

interface PlaygroundProps {
  tasks: Task[];
  venues: VenueInfo[];
  onTasksUpdated?: () => void;
}

export const Playground: React.FC<PlaygroundProps> = ({ tasks, venues, onTasksUpdated }) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string>(tasks[0]?.task_id || "");
  const [qtypeFilter, setQtypeFilter] = useState<string>("All");
  const [pairsOnly, setPairsOnly] = useState<boolean>(false);
  const [generatorMode, setGeneratorMode] = useState<boolean>(false);

  // Live Generator State
  const [genVenue, setGenVenue] = useState<string>("railway_station");
  const [genQtype, setGenQtype] = useState<string>("DIRECT");
  const [genSeed, setGenSeed] = useState<number>(42);
  const [genEntries, setGenEntries] = useState<number>(4);
  const [genTilt, setGenTilt] = useState<number>(10);
  const [genClutter, setGenClutter] = useState<number>(4);
  const [genBlur, setGenBlur] = useState<number>(0.5);
  const [generating, setGenerating] = useState<boolean>(false);
  const [genError, setGenError] = useState<string | null>(null);

  // Bounding box toggle
  const [showBoxes, setShowBoxes] = useState<boolean>(false);

  const QUESTION_TYPES = ["All", "DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"];

  const filteredTasks = tasks.filter((t) => {
    if (qtypeFilter !== "All" && t.qtype !== qtypeFilter) return false;
    if (pairsOnly && !t.pair_id) return false;
    return true;
  });

  const currentTask = tasks.find((t) => t.task_id === selectedTaskId) || filteredTasks[0] || tasks[0];

  // Auto-select valid task if filtered out
  useEffect(() => {
    if (filteredTasks.length > 0 && !filteredTasks.some((t) => t.task_id === selectedTaskId)) {
      setSelectedTaskId(filteredTasks[0].task_id);
    }
  }, [qtypeFilter, pairsOnly]);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenError(null);
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          venue_id: genVenue,
          qtype: genQtype,
          seed: genSeed,
          n_entries: genEntries,
          perspective_deg: genTilt,
          clutter: genClutter,
          blur: genBlur,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Generation failed on server");
      }

      const newTask: Task = await res.json();
      setSelectedTaskId(newTask.task_id);
      if (onTasksUpdated) onTasksUpdated();
      setGeneratorMode(false);
    } catch (err: any) {
      setGenError(err.message || "Failed generating task");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Top Controls Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        {/* Filter / Mode selectors */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Filter className="w-3.5 h-3.5" />
            <span>Question Type:</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {QUESTION_TYPES.map((qt) => (
              <button
                key={qt}
                onClick={() => setQtypeFilter(qt)}
                className={`text-xs px-2.5 py-1 rounded font-medium transition-colors ${
                  qtypeFilter === qt
                    ? "bg-emerald-900 text-white shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {qt}
              </button>
            ))}
          </div>

          <label className="flex items-center space-x-1.5 text-xs text-slate-700 cursor-pointer ml-2">
            <input
              type="checkbox"
              checked={pairsOnly}
              onChange={(e) => setPairsOnly(e.target.checked)}
              className="rounded border-slate-300 text-emerald-800 focus:ring-emerald-700"
            />
            <span className="font-medium">Minimal Pairs Only</span>
          </label>
        </div>

        {/* Live generator toggle */}
        <button
          onClick={() => setGeneratorMode(!generatorMode)}
          className={`flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-md font-semibold transition-all shadow-xs ${
            generatorMode
              ? "bg-amber-600 text-white"
              : "bg-white border border-slate-300 text-slate-800 hover:bg-slate-50"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{generatorMode ? "Close Generator" : "Synthesize New Signboard"}</span>
        </button>
      </div>

      {/* Live Generator Panel Drawer */}
      {generatorMode && (
        <div className="bg-white border border-amber-300 rounded-lg p-5 mb-6 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <h3 className="font-bold text-sm text-slate-900">
                Procedural Signboard Synthesizer (Playwright DOM + Dual Verifier)
              </h3>
            </div>
            <span className="text-xs text-slate-500">
              Generates scene graph, renders HTML/CSS, applies 3D homography, and computes dual receipts.
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Venue Topology</label>
              <select
                value={genVenue}
                onChange={(e) => setGenVenue(e.target.value)}
                className="w-full text-xs rounded border border-slate-300 p-1.5 bg-white font-medium"
              >
                {venues.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Question Type</label>
              <select
                value={genQtype}
                onChange={(e) => setGenQtype(e.target.value)}
                className="w-full text-xs rounded border border-slate-300 p-1.5 bg-white font-medium"
              >
                {QUESTION_TYPES.filter((q) => q !== "All").map((qt) => (
                  <option key={qt} value={qt}>
                    {qt}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Task Seed</label>
              <div className="flex space-x-1">
                <input
                  type="number"
                  value={genSeed}
                  onChange={(e) => setGenSeed(parseInt(e.target.value) || 0)}
                  className="w-full text-xs rounded border border-slate-300 p-1.5 font-mono"
                />
                <button
                  onClick={() => setGenSeed(Math.floor(Math.random() * 100000))}
                  className="px-2 py-1 bg-slate-100 border border-slate-300 rounded hover:bg-slate-200 text-xs"
                  title="Randomize Seed"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-slate-600" />
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Entries on Signboard ({genEntries})
              </label>
              <input
                type="range"
                min="2"
                max="8"
                value={genEntries}
                onChange={(e) => setGenEntries(parseInt(e.target.value))}
                className="w-full"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4 pt-3 border-t border-slate-100">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Perspective Tilt: {genTilt}°
              </label>
              <input
                type="range"
                min="0"
                max="30"
                value={genTilt}
                onChange={(e) => setGenTilt(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Environmental Clutter: {genClutter} items
              </label>
              <input
                type="range"
                min="0"
                max="8"
                value={genClutter}
                onChange={(e) => setGenClutter(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Lens Blur ($\sigma$): {genBlur}
              </label>
              <input
                type="range"
                min="0.1"
                max="1.5"
                step="0.1"
                value={genBlur}
                onChange={(e) => setGenBlur(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>
          </div>

          {genError && (
            <div className="p-3 mb-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {genError}
            </div>
          )}

          <div className="flex justify-end">
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center space-x-2 px-4 py-2 rounded-md bg-emerald-900 text-white font-semibold text-xs hover:bg-emerald-800 transition-colors shadow-xs disabled:opacity-50"
            >
              {generating ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                  <span>Synthesizing Scene & Rendering DOM...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate Task & Verify Receipts</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Main Grid: Task Viewer + Proof Inspector */}
      {currentTask ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Signboard Viewer & Question (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            {/* Task selector pill strip */}
            <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Select Task ({filteredTasks.length} available)
                </span>
                <span className="font-mono text-xs text-slate-600">ID: {currentTask.task_id}</span>
              </div>
              <div className="flex overflow-x-auto space-x-1.5 pb-1">
                {filteredTasks.map((t) => (
                  <button
                    key={t.task_id}
                    onClick={() => setSelectedTaskId(t.task_id)}
                    className={`shrink-0 px-2.5 py-1.5 rounded text-xs font-mono transition-colors ${
                      t.task_id === currentTask.task_id
                        ? "bg-emerald-900 text-white font-bold shadow-xs"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    [{t.qtype.slice(0, 3)}] {t.task_id}
                  </button>
                ))}
              </div>
            </div>

            {/* Signboard Image Card */}
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-xs">
              <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-white uppercase tracking-wider">
                    {currentTask.qtype}
                  </span>
                  <span className="text-xs text-slate-600">
                    Target: <strong className="text-slate-900">{currentTask.target_dest_id}</strong>
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                    EXIF Clean
                  </span>
                  <button
                    onClick={() => setShowBoxes(!showBoxes)}
                    className={`text-xs px-2.5 py-1 rounded border transition-colors flex items-center space-x-1 ${
                      showBoxes
                        ? "bg-amber-100 border-amber-300 text-amber-900 font-medium"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <Eye className="w-3 h-3" />
                    <span>{showBoxes ? "Hide Target Box" : "Highlight Target"}</span>
                  </button>
                </div>
              </div>

              {/* Image preview */}
              <div className="relative p-3 bg-slate-900/90 flex justify-center items-center min-h-[320px]">
                <img
                  src={currentTask.image_url}
                  alt={`Signboard for task ${currentTask.task_id}`}
                  className="max-h-[420px] w-auto object-contain rounded shadow-md"
                />

                {/* Optional overlay indicator */}
                {showBoxes && currentTask.scene?.entries && (
                  <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                    <div className="border-2 border-dashed border-amber-400 bg-amber-400/20 px-3 py-1 rounded text-xs font-bold text-amber-200 shadow-lg">
                      Target: {currentTask.target_dest_id}
                    </div>
                  </div>
                )}
              </div>

              {/* Signboard specs footer */}
              {currentTask.difficulty && (
                <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex flex-wrap items-center justify-between text-xs text-slate-500 font-mono">
                  <span>Entries: {currentTask.difficulty.n_entries || 4}</span>
                  <span>Tilt: {currentTask.difficulty.perspective_deg || 0}°</span>
                  <span>Clutter: {currentTask.difficulty.clutter || 0}</span>
                  <span>Blur: {currentTask.difficulty.blur || 0}</span>
                  <span>Template: {currentTask.difficulty.template || "board_list"}</span>
                </div>
              )}
            </div>

            {/* Question & Options Card */}
            <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-xs">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
                Contextual Wayfinding Question
              </span>
              <h2 className="text-base font-bold text-slate-900 mt-1 mb-4 leading-relaxed">
                {currentTask.question}
              </h2>

              {/* Options Dial / Grid */}
              <div>
                <span className="text-xs font-medium text-slate-500 block mb-2">
                  Invariant 10 Canonical Options (Multiples of 45°):
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {currentTask.options.map((opt) => {
                    const isGold = opt === currentTask.gold;
                    return (
                      <div
                        key={opt}
                        className={`p-2 rounded-md border text-center transition-all ${
                          isGold
                            ? "bg-emerald-50 border-emerald-400 text-emerald-950 font-bold shadow-xs ring-1 ring-emerald-400"
                            : "bg-slate-50/70 border-slate-200 text-slate-700"
                        }`}
                      >
                        <div className="text-[11px] font-mono tracking-tight">{opt}</div>
                        {isGold && (
                          <div className="text-[10px] text-emerald-700 font-sans mt-0.5">
                            ★ Reference Gold
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Model Evaluator, Venue Map & Receipts (5 cols) */}
          <div className="lg:col-span-5 space-y-6">
            {/* Model Evaluation Console */}
            <ModelEvaluator taskId={currentTask.task_id} gold={currentTask.gold} />

            {/* Interactive SVG Venue Route Map */}
            <VenueMapSVG
              venueId={currentTask.scene?.venue_id || "railway_station"}
              junctionId={currentTask.scene?.junction_id || "j_main"}
              targetDestId={currentTask.target_dest_id}
              closedEdges={currentTask.scene?.closed_edges || []}
              taskId={currentTask.task_id}
            />

            {/* Cryptographic Verification Receipt */}
            <ReceiptCard
              receipt={currentTask.receipt}
              gold={currentTask.gold}
              seed={currentTask.seed}
            />
          </div>
        </div>
      ) : (
        <div className="p-12 text-center bg-white border border-slate-200 rounded-lg text-slate-500">
          No tasks match the selected filter.
        </div>
      )}
    </div>
  );
};
