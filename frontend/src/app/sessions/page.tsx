"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Search, ChevronLeft, ChevronRight, Star, Archive, MessageSquare, Zap } from "lucide-react";

interface Session { session_id: string; project_path: string; file_size: number; message_count: number; user_count: number; assistant_count: number; first_message: string; last_message: string; started_at: string; model: string; starred: number; archived: number; rating: number; importance: number; category: string; custom_title: string; duration_mins: number; }
interface Project { encoded_path: string; display_name: string; session_count: number; }
interface Counts { major: number; standard: number; minor: number; automated: number; starred: number; archived: number; all: number; }

const CAT_STYLES: Record<string, string> = {
  major: "bg-[#ddf4ff] text-[var(--color-accent)] border-[#54aeff]",
  standard: "bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)] border-[var(--color-border)]",
  minor: "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)] border-[var(--color-border-muted)]",
  automated: "bg-[#dafbe1] text-[var(--color-success)] border-[#aceebb]",
};

export default function SessionsPage() {
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState(searchParams.get("project") || "");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Counts>({ major: 0, standard: 0, minor: 0, automated: 0, starred: 0, archived: 0, all: 0 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("importance");
  const [category, setCategory] = useState("");
  const [showStarred, setShowStarred] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [loading, setLoading] = useState(false);
  const perPage = 30;

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const sorted = (d.projects || []).filter((p: Project) => p.session_count > 0).sort((a: Project, b: Project) => b.session_count - a.session_count);
      setProjects(sorted);
      if (!selectedProject && sorted.length > 0) setSelectedProject(sorted[0].encoded_path);
    });
  }, []);

  const loadSessions = useCallback(() => {
    if (!selectedProject) return;
    setLoading(true);
    const params = new URLSearchParams({ project: selectedProject, page: String(page), per_page: String(perPage), sort });
    if (search) params.set("q", search);
    if (category) params.set("category", category);
    if (showStarred) params.set("starred", "true");
    if (showArchived) params.set("archived", "true");
    fetch(`/api/sessions?${params}`).then((r) => r.json()).then((d) => {
      setSessions(d.sessions || []); setTotal(d.total || 0); setCounts(d.counts || counts); setLoading(false);
    });
  }, [selectedProject, page, search, sort, category, showStarred, showArchived]);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const toggleStar = async (sid: string, current: number) => {
    await fetch(`/api/sessions/${sid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ starred: !current }) });
    loadSessions();
  };

  const toggleArchive = async (sid: string, current: number) => {
    await fetch(`/api/sessions/${sid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived: !current }) });
    loadSessions();
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[var(--color-fg-default)] mb-4">Sessions</h1>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-2 mb-3">
        <select value={selectedProject} onChange={(e) => { setSelectedProject(e.target.value); setPage(1); }}
          className="border border-[var(--color-border)] rounded-md px-3 py-1.5 text-sm bg-[var(--color-bg-subtle)]">
          {projects.map((p) => <option key={p.encoded_path} value={p.encoded_path}>{p.display_name} ({p.session_count})</option>)}
        </select>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-fg-subtle)]" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search sessions..."
            className="w-full pl-10 pr-4 py-1.5 border border-[var(--color-border)] rounded-md text-sm bg-white focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]" />
        </div>
        <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}
          className="border border-[var(--color-border)] rounded-md px-3 py-1.5 text-sm bg-[var(--color-bg-subtle)]">
          <option value="importance">By Importance</option>
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
          <option value="rating">By Rating</option>
          <option value="size">By Size</option>
        </select>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <Chip active={!category && !showStarred && !showArchived} onClick={() => { setCategory(""); setShowStarred(false); setShowArchived(false); setPage(1); }} label={`All (${counts.all})`} />
        <Chip active={showStarred} onClick={() => { setShowStarred(!showStarred); setCategory(""); setShowArchived(false); setPage(1); }} label={`★ Starred (${counts.starred})`} />
        <Chip active={category === "major"} onClick={() => { setCategory(category === "major" ? "" : "major"); setShowStarred(false); setPage(1); }} label={`Major (${counts.major || 0})`} />
        <Chip active={category === "standard"} onClick={() => { setCategory(category === "standard" ? "" : "standard"); setShowStarred(false); setPage(1); }} label={`Standard (${counts.standard || 0})`} />
        <Chip active={category === "automated"} onClick={() => { setCategory(category === "automated" ? "" : "automated"); setShowStarred(false); setPage(1); }} label={`Automated (${counts.automated || 0})`} />
        <Chip active={category === "minor"} onClick={() => { setCategory(category === "minor" ? "" : "minor"); setShowStarred(false); setPage(1); }} label={`Minor (${counts.minor || 0})`} />
        <Chip active={showArchived} onClick={() => { setShowArchived(!showArchived); setCategory(""); setShowStarred(false); setPage(1); }} label={`Archived (${counts.archived})`} />
      </div>

      <p className="text-xs text-[var(--color-fg-subtle)] mb-2">{total} sessions | Page {page}/{totalPages || 1}</p>

      {loading ? (
        <p className="text-sm text-[var(--color-fg-subtle)] py-8 text-center">Indexing sessions...</p>
      ) : (
        <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
          {sessions.map((s, i) => {
            const title = s.custom_title || s.first_message?.slice(0, 120) || "—";
            return (
              <div key={s.session_id} className={`flex items-start gap-2 px-3 py-2.5 hover:bg-[var(--color-bg-subtle)] transition-colors ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""} ${s.starred ? "bg-[#fffbdd]" : ""}`}>
                <button onClick={() => toggleStar(s.session_id, s.starred)} className="mt-0.5 shrink-0">
                  <Star className={`w-4 h-4 ${s.starred ? "fill-[var(--color-attention)] text-[var(--color-attention)]" : "text-[var(--color-border)] hover:text-[var(--color-fg-subtle)]"}`} />
                </button>
                <Link href={`/sessions/${s.session_id}`} className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${CAT_STYLES[s.category] || CAT_STYLES.standard}`}>{s.category}</span>
                    {s.rating > 0 && <span className="text-[var(--color-attention)] text-[10px]">{"★".repeat(s.rating)}</span>}
                    <span className="text-[11px] text-[var(--color-fg-subtle)] font-mono">{s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}</span>
                    <span className="text-[10px] text-[var(--color-fg-subtle)]">{s.message_count} msg</span>
                    {s.importance >= 50 && <span className="text-[10px] text-[var(--color-done)]"><Zap className="w-3 h-3 inline" /> {s.importance.toFixed(0)}</span>}
                  </div>
                  <p className="text-sm text-[var(--color-fg-default)] truncate">{title}</p>
                  {s.custom_title && s.first_message && <p className="text-xs text-[var(--color-fg-subtle)] truncate mt-0.5">{s.first_message.slice(0, 100)}</p>}
                </Link>
                <button onClick={() => toggleArchive(s.session_id, s.archived)} className="mt-0.5 shrink-0" title={s.archived ? "Unarchive" : "Archive"}>
                  <Archive className={`w-3.5 h-3.5 ${s.archived ? "text-[var(--color-fg-muted)]" : "text-[var(--color-border)] hover:text-[var(--color-fg-subtle)]"}`} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="p-1.5 rounded border border-[var(--color-border)] disabled:opacity-30 hover:bg-[var(--color-bg-subtle)]">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-[var(--color-fg-subtle)]">Page {page} / {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="p-1.5 rounded border border-[var(--color-border)] disabled:opacity-30 hover:bg-[var(--color-bg-subtle)]">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function Chip({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button onClick={onClick}
      className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${active ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]" : "bg-white text-[var(--color-fg-muted)] border-[var(--color-border)] hover:bg-[var(--color-bg-subtle)]"}`}>
      {label}
    </button>
  );
}
