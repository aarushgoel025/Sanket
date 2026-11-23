import { Compass, GitCompare, BarChart3, AlertTriangle, ShieldCheck } from "lucide-react";

export type NavTab = "playground" | "pairs" | "findings" | "failures";

interface HeaderProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  taskCount?: number;
}

export const Header: React.FC<HeaderProps> = ({ currentTab, onTabChange, taskCount = 23 }) => {
  const tabs = [
    { id: "playground" as NavTab, label: "Task Playground", icon: Compass },
    { id: "pairs" as NavTab, label: "Minimal Pairs", icon: GitCompare },
    { id: "findings" as NavTab, label: "Findings & Figures", icon: BarChart3 },
    { id: "failures" as NavTab, label: "Failure Gallery", icon: AlertTriangle },
  ];

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-900 text-white flex items-center justify-center shadow-xs">
              <Compass className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-slate-900">
                  Sanket <span className="font-normal text-slate-500 text-sm">/ संकेत</span>
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                  <ShieldCheck className="w-3 h-3 mr-1 text-emerald-600" />
                  v1.0 Frozen ({taskCount} Tasks)
                </span>
              </div>
              <p className="text-xs text-slate-500 hidden sm:block">
                Verified Wayfinding Signboard Benchmark & Model Diagnostics
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 sm:space-x-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  className={`flex items-center space-x-2 px-3.5 py-2 rounded-md text-sm font-medium transition-all ${
                    isActive
                      ? "bg-emerald-900 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? "text-emerald-400" : "text-slate-500"}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
};
