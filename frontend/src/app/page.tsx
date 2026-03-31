"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FolderOpen, MessageSquare, FileText, Zap, Clock, GitBranch, Star, Sparkles, Plus } from "lucide-react";

interface Project { encoded_path: string; display_name: string; session_count: number; memory_count: number; last_activity: string | null; }
interface Session { session_id: string; project_path: string; first_message: string; started_at: string; message_count: number; model: string; custom_title?: string; importance?: number; category?: string; rating?: number; starred?: number; }
interface Thread { project: string; project_path: string; filename: string; status: string; summary: string; }
interface Dashboard { projects: Project[]; recent_sessions: Session[]; total_sessions: number; active_threads: Thread[]; total_memory_files: number; }

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [contextStats, setContextStats] = useState<Record<string, number>>({});
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch("/api/dashboard").then((r) => r.json()),
      fetch("/api/context/stats").then((r) => r.json()),
    ])
      .then(([d, cs]) => { setData(d); setContextStats(cs.stats || {}); })
      .catch(() => setError(true));
  }, []);

  if (error) return <div className="p-8 text-[var(--color-danger)]">Could not connect to backend. Run: <code className="bg-[var(--color-bg-subtle)] px-1 rounded">cd backend && uvicorn main:app --port 8000</code></div>;
  if (!data) return <div className="p-8 text-[var(--color-fg-subtle)]">Loading...</div>;

  const totalContext = Object.values(contextStats).reduce((a, b) => a + b, 0);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[var(--color-fg-default)] mb-5">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <Stat icon={FolderOpen} value={data.projects.length} label="Projects" />
        <Stat icon={MessageSquare} value={data.total_sessions} label="Sessions Indexed" />
        <Stat icon={FileText} value={data.total_memory_files} label="Memory Files" />
        <Stat icon={Zap} value={totalContext} label="Context Branches" />
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-6">
        {/* Projects */}
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-fg-default)] mb-2 uppercase tracking-wide">Projects</h2>
          <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
            {data.projects.filter((p) => p.session_count > 0).sort((a, b) => b.session_count - a.session_count).map((p, i) => (
              <Link key={p.encoded_path} href={`/sessions?project=${p.encoded_path}`}
                className={`flex items-center justify-between px-3 py-2.5 hover:bg-[var(--color-bg-subtle)] transition-colors ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
                <div>
                  <span className="text-sm font-medium text-[var(--color-accent)]">{p.display_name}</span>
                  {p.memory_count > 0 && <span className="text-xs text-[var(--color-fg-subtle)] ml-2">{p.memory_count} memory files</span>}
                </div>
                <span className="text-xs text-[var(--color-fg-subtle)] bg-[var(--color-bg-subtle)] px-2 py-0.5 rounded-full">{p.session_count}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Threads + Context */}
        <div>
          <h2 className="text-sm font-semibold text-[var(--color-fg-default)] mb-2 uppercase tracking-wide flex items-center gap-1.5">
            <GitBranch className="w-3.5 h-3.5" /> Active Threads
          </h2>
          {data.active_threads.length === 0 ? (
            <p className="text-sm text-[var(--color-fg-subtle)]">No active threads</p>
          ) : (
            <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
              {data.active_threads.map((t, i) => (
                <Link key={t.filename} href={`/memory?project=${t.project_path}`}
                  className={`block px-3 py-2.5 hover:bg-[var(--color-bg-subtle)] ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <StatusBadge status={t.status} />
                    <span className="text-sm font-medium">{t.filename.replace("thread_", "").replace(".md", "")}</span>
                  </div>
                  <p className="text-xs text-[var(--color-fg-subtle)] truncate">{t.summary}</p>
                </Link>
              ))}
            </div>
          )}

          {totalContext > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-semibold text-[var(--color-fg-muted)] mb-1.5 uppercase tracking-wide">Context Branches</h3>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(contextStats).map(([type, count]) => (
                  <Link key={type} href={`/context?type=${type}`}
                    className="text-xs border border-[var(--color-border)] px-2 py-1 rounded-full text-[var(--color-fg-muted)] hover:text-[var(--color-accent)] hover:border-[var(--color-accent)] transition-colors">
                    {type}: {count}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Suggested Threads */}
      <SuggestedThreads />

      {/* Starred */}
      <div className="mt-6 mb-6">
        <h2 className="text-sm font-semibold text-[var(--color-fg-default)] mb-2 uppercase tracking-wide flex items-center gap-1.5">
          <Star className="w-3.5 h-3.5 text-[var(--color-attention)]" /> Starred Sessions
        </h2>
        <StarredSessions />
      </div>

      {/* Recent */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--color-fg-default)] mb-2 uppercase tracking-wide flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" /> Recent Sessions
        </h2>
        <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
          {data.recent_sessions.map((s, i) => (
            <Link key={s.session_id} href={`/sessions/${s.session_id}`}
              className={`flex items-center gap-3 px-3 py-2 hover:bg-[var(--color-bg-subtle)] transition-colors ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
              <span className="text-xs text-[var(--color-fg-subtle)] font-mono w-20 shrink-0">
                {s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}
              </span>
              <span className="text-xs text-[var(--color-fg-subtle)] w-12 shrink-0 text-right">{s.message_count} msg</span>
              <span className="text-sm text-[var(--color-fg-default)] truncate flex-1">
                {(s as any).custom_title || s.first_message?.slice(0, 100) || "—"}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function SuggestedThreads() {
  const [suggestions, setSuggestions] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const main = (d.projects || []).sort((a: any, b: any) => b.session_count - a.session_count)[0];
      if (main) {
        fetch(`/api/threads/suggest?project=${main.encoded_path}&min_sessions=2`)
          .then((r) => r.json())
          .then((d) => setSuggestions((d.suggestions || []).filter((s: any) => s.session_count <= 50 && s.session_count >= 2).slice(0, 6)))
          .catch(() => {});
      }
    });
  }, []);

  if (suggestions.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold text-[var(--color-fg-default)] mb-2 uppercase tracking-wide flex items-center gap-1.5">
        <Sparkles className="w-3.5 h-3.5 text-[var(--color-done)]" /> Suggested Meta-Threads
      </h2>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {suggestions.map((s: any) => (
          <div key={s.topic} className="border border-[var(--color-border)] rounded-md p-3 hover:border-[var(--color-done)] transition-colors">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-[var(--color-done)]">{s.session_count} sessions</span>
                  <span className="text-[10px] text-[var(--color-fg-subtle)]">{s.total_messages} msgs</span>
                </div>
                <p className="text-sm font-medium text-[var(--color-fg-default)] truncate">{s.suggested_title}</p>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {s.keywords.slice(0, 4).map((kw: string) => (
                    <span key={kw} className="text-[10px] bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)] px-1.5 py-0.5 rounded-full border border-[var(--color-border-muted)]">{kw}</span>
                  ))}
                </div>
              </div>
              <button className="shrink-0 p-1.5 rounded-md border border-[var(--color-border)] text-[var(--color-fg-subtle)] hover:text-[var(--color-done)] hover:border-[var(--color-done)] transition-colors" title="Create thread">
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StarredSessions() {
  const [starred, setStarred] = useState<Session[]>([]);

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const main = (d.projects || []).sort((a: any, b: any) => b.session_count - a.session_count)[0];
      if (main) {
        fetch(`/api/sessions?project=${main.encoded_path}&starred=true&sort=rating&per_page=10`)
          .then((r) => r.json()).then((d) => setStarred(d.sessions || []));
      }
    });
  }, []);

  if (starred.length === 0) return <p className="text-sm text-[var(--color-fg-subtle)]">No starred sessions yet. Star important sessions in the Sessions view.</p>;

  return (
    <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
      {starred.map((s: any, i: number) => (
        <Link key={s.session_id} href={`/sessions/${s.session_id}`}
          className={`flex items-center gap-3 px-3 py-2 hover:bg-[#fff8c5] transition-colors ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
          <Star className="w-4 h-4 fill-[var(--color-attention)] text-[var(--color-attention)] shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              {s.rating > 0 && <span className="text-[var(--color-attention)] text-xs">{"★".repeat(s.rating)}</span>}
              <span className="text-xs text-[var(--color-fg-subtle)] font-mono">{s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}</span>
              <span className="text-[10px] text-[var(--color-fg-subtle)]">{s.message_count} msg</span>
            </div>
            <p className="text-sm text-[var(--color-fg-default)] truncate">{s.custom_title || s.first_message?.slice(0, 100) || "—"}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}

function Stat({ icon: Icon, value, label }: { icon: React.ElementType; value: number; label: string }) {
  return (
    <div className="border border-[var(--color-border)] rounded-md p-3 text-center">
      <Icon className="w-5 h-5 mx-auto mb-1 text-[var(--color-fg-subtle)]" />
      <div className="text-xl font-semibold text-[var(--color-fg-default)]">{value}</div>
      <div className="text-xs text-[var(--color-fg-subtle)]">{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    active: "bg-[#dafbe1] text-[var(--color-success)] border-[#aceebb]",
    paused: "bg-[#fff8c5] text-[var(--color-attention)] border-[#eac54f]",
    merged: "bg-[#ddf4ff] text-[var(--color-accent)] border-[#54aeff]",
    archived: "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)] border-[var(--color-border)]",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${colors[status] || colors.active}`}>
      {status}
    </span>
  );
}
