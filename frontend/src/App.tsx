import { useEffect, useState } from "react";
import type { Task, VenueInfo } from "./types";
import { Header, type NavTab } from "./components/Header";
import { Playground } from "./views/Playground";
import { MinimalPairsView } from "./views/MinimalPairsView";
import { FindingsView } from "./views/FindingsView";
import { FailureGalleryView } from "./views/FailureGalleryView";
import { Compass, Shield, ExternalLink } from "lucide-react";

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>("playground");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [venues, setVenues] = useState<VenueInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = async () => {
    try {
      const res = await fetch("/api/tasks");
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data: Task[] = await res.json();
      setTasks(data);
    } catch (err: any) {
      console.error("Failed loading tasks:", err);
      setError("Unable to connect to Sanket API backend. Ensure the backend server is running on port 8000.");
    }
  };

  const fetchVenues = async () => {
    try {
      const res = await fetch("/api/venues");
      if (res.ok) {
        const data: VenueInfo[] = await res.json();
        setVenues(data);
      }
    } catch (err) {
      console.error("Failed loading venues:", err);
    }
  };

  useEffect(() => {
    Promise.all([fetchTasks(), fetchVenues()]).finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-[#f8faf9] flex flex-col justify-between text-slate-900 font-sans">
      <div>
        <Header
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          taskCount={tasks.length}
        />

        {error && (
          <div className="max-w-7xl mx-auto px-4 mt-4">
            <div className="p-3 bg-red-50 border border-red-200 text-xs text-red-700 rounded-md">
              {error}
            </div>
          </div>
        )}

        <main>
          {loading ? (
            <div className="max-w-7xl mx-auto px-4 py-20 text-center">
              <Compass className="w-8 h-8 animate-spin mx-auto text-emerald-800 mb-3" />
              <p className="text-xs text-slate-500 font-medium">Initializing Sanket benchmark harness...</p>
            </div>
          ) : (
            <>
              {currentTab === "playground" && (
                <Playground tasks={tasks} venues={venues} onTasksUpdated={fetchTasks} />
              )}
              {currentTab === "pairs" && <MinimalPairsView />}
              {currentTab === "findings" && <FindingsView />}
              {currentTab === "failures" && <FailureGalleryView />}
            </>
          )}
        </main>
      </div>

      {/* Footer */}
      <footer className="mt-16 bg-white border-t border-slate-200 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-slate-800">Sanket Benchmark Suite</span>
            <span>•</span>
            <span>Ground-truth wayfinding evaluation factory</span>
          </div>

          <div className="flex items-center space-x-6">
            <span className="flex items-center">
              <Shield className="w-3.5 h-3.5 mr-1 text-emerald-700" />
              MIT License
            </span>
            <a
              href="https://github.com/aarushgoel025/Sanket"
              target="_blank"
              rel="noreferrer"
              className="flex items-center text-slate-700 hover:text-slate-950 font-medium"
            >
              <ExternalLink className="w-3.5 h-3.5 mr-1" />
              GitHub: aarushgoel025/Sanket
            </a>
            <span className="font-mono text-[11px] text-slate-400">
              Tag: v1.0-dataset
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
