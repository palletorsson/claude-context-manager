"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FolderOpen, MessageSquare, FileText, Zap, Clock, GitBranch, Star } from "lucide-react";

interface Project {
  encoded_path: string;
  display_name: string;
  session_count: number;
  memory_count: number;
  last_activity: string | null;
}

interface Session {
  session_id: string;
  project_path: string;
  first_message: string;
  started_at: string;
  message_count: number;
  model: string;
}

interface Thread {
  project: string;
  project_path: string;
  filename: string;
  status: string;
  summary: string;
}

interface Dashboard {
  projects: Project[];
  recent_sessions: Session[];
  total_sessions: number;
  active_threads: Thread[];
  total_memory_files: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [contextStats, setContextStats] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch("/api/dashboard").then((r) => r.json()).then(setData);
    fetch("/api/context/stats").then((r) => r.json()).then((d) => setContextStats(d.stats || {}));
  }, []);

  if (!data) {
    return <div className="animate-pulse text-zinc-500 p-8">Loading dashboard...</div>;
  }

  const totalContext = Object.values(contextStats).reduce((a, b) => a + b, 0);

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">Dashboard</h1>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <Stat icon={FolderOpen} value={data.projects.length} label="Projects" color="text-blue-400" />
        <Stat icon={MessageSquare} value={data.total_sessions} label="Sessions Indexed" color="text-violet-400" />
        <Stat icon={FileText} value={data.total_memory_files} label="Memory Files" color="text-green-400" />
        <Stat icon={Zap} value={totalContext} label="Context Branches" color="text-amber-400" />
      </div>

      {/* Two columns: Projects + Active Threads */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        {/* Projects */}
        <div>
          <h2 className="text-lg font-semibold text-zinc-200 mb-3">Projects</h2>
          <div className="space-y-2">
            {data.projects
              .filter((p) => p.session_count > 0)
              .sort((a, b) => b.session_count - a.session_count)
              .map((p) => (
                <Link
                  key={p.encoded_path}
                  href={`/sessions?project=${p.encoded_path}`}
                  className="block bg-zinc-900 border border-zinc-800 rounded-lg p-3 hover:border-zinc-600 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-200 font-medium text-sm">{p.display_name}</span>
                    <span className="text-zinc-600 text-xs">{p.session_count} sessions</span>
                  </div>
                  {p.memory_count > 0 && (
                    <span className="text-zinc-500 text-xs">{p.memory_count} memory files</span>
                  )}
                </Link>
              ))}
          </div>
        </div>

        {/* Active Threads */}
        <div>
          <h2 className="text-lg font-semibold text-zinc-200 mb-3 flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-violet-400" />
            Active Threads
          </h2>
          {data.active_threads.length === 0 ? (
            <p className="text-zinc-600 text-sm">No active threads</p>
          ) : (
            <div className="space-y-2">
              {data.active_threads.map((t) => (
                <Link
                  key={t.filename}
                  href={`/memory?project=${t.project_path}`}
                  className="block bg-zinc-900 border border-zinc-800 rounded-lg p-3 hover:border-zinc-600 transition-colors"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      t.status === "active" ? "bg-green-900/40 text-green-400" :
                      t.status === "paused" ? "bg-amber-900/40 text-amber-400" :
                      "bg-zinc-800 text-zinc-500"
                    }`}>
                      {t.status}
                    </span>
                    <span className="text-zinc-200 text-sm font-medium">{t.filename.replace("thread_", "").replace(".md", "")}</span>
                  </div>
                  <p className="text-zinc-500 text-xs line-clamp-2">{t.summary}</p>
                </Link>
              ))}
            </div>
          )}

          {/* Context branch summary */}
          {totalContext > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-zinc-300 mb-2">Context Branches</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(contextStats).map(([type, count]) => (
                  <Link
                    key={type}
                    href={`/context?type=${type}`}
                    className="text-xs bg-zinc-800 px-2 py-1 rounded-md text-zinc-400 hover:text-zinc-200 transition-colors"
                  >
                    {type}: {count}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Starred Sessions */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-zinc-200 mb-3 flex items-center gap-2">
          <Star className="w-4 h-4 text-amber-400" />
          Starred Sessions
        </h2>
        <StarredSessions />
      </div>

      {/* Recent Sessions */}
      <div>
        <h2 className="text-lg font-semibold text-zinc-200 mb-3 flex items-center gap-2">
          <Clock className="w-4 h-4 text-cyan-400" />
          Recent Sessions
        </h2>
        <div className="space-y-1.5">
          {data.recent_sessions.map((s) => (
            <Link
              key={s.session_id}
              href={`/sessions/${s.session_id}`}
              className="flex items-center gap-3 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 hover:border-zinc-600 transition-colors"
            >
              <span className="text-zinc-600 text-xs font-mono w-20 flex-shrink-0">
                {s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}
              </span>
              <span className="text-zinc-500 text-xs w-12 flex-shrink-0 text-right">
                {s.message_count} msg
              </span>
              <span className="text-zinc-300 text-sm truncate flex-1">
                {(s as any).custom_title || s.first_message?.slice(0, 100) || "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function StarredSessions() {
  const [starred, setStarred] = useState<Session[]>([]);

  useEffect(() => {
    // Find the main project and get starred sessions
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const main = (d.projects || []).sort((a: any, b: any) => b.session_count - a.session_count)[0];
      if (main) {
        fetch(`/api/sessions?project=${main.encoded_path}&starred=true&sort=rating&per_page=10`)
          .then((r) => r.json())
          .then((d) => setStarred(d.sessions || []));
      }
    });
  }, []);

  if (starred.length === 0) {
    return <p className="text-zinc-600 text-sm">No starred sessions yet. Star important sessions in the Sessions view.</p>;
  }

  return (
    <div className="space-y-1.5">
      {starred.map((s: any) => (
        <Link
          key={s.session_id}
          href={`/sessions/${s.session_id}`}
          className="flex items-center gap-3 bg-zinc-900 border border-amber-800/30 rounded-lg px-3 py-2.5 hover:border-amber-700/50 transition-colors"
        >
          <Star className="w-4 h-4 fill-amber-400 text-amber-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              {s.rating > 0 && <span className="text-amber-500 text-[10px]">{"★".repeat(s.rating)}</span>}
              <span className="text-zinc-600 text-[10px] font-mono">
                {s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}
              </span>
              <span className="text-zinc-700 text-[10px]">{s.message_count} msg</span>
            </div>
            <p className="text-zinc-200 text-sm truncate">{s.custom_title || s.first_message?.slice(0, 100) || "—"}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}

function Stat({ icon: Icon, value, label, color }: { icon: React.ElementType; value: number; label: string; color: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-center">
      <Icon className={`w-5 h-5 mx-auto mb-1 ${color}`} />
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-zinc-600 text-xs">{label}</div>
    </div>
  );
}
