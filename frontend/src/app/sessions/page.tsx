"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Search, ChevronLeft, ChevronRight, Star, Archive, MessageSquare,
  ArrowUpDown, Filter, Zap, Bot, Wrench, Clock,
} from "lucide-react";

interface Session {
  session_id: string;
  project_path: string;
  file_size: number;
  message_count: number;
  user_count: number;
  assistant_count: number;
  first_message: string;
  last_message: string;
  started_at: string;
  model: string;
  starred: number;
  archived: number;
  rating: number;
  importance: number;
  category: string;
  custom_title: string;
  duration_mins: number;
}

interface Project {
  encoded_path: string;
  display_name: string;
  session_count: number;
}

interface Counts {
  major: number;
  standard: number;
  minor: number;
  automated: number;
  starred: number;
  archived: number;
  all: number;
}

const CAT_COLORS: Record<string, { bg: string; text: string }> = {
  major: { bg: "bg-violet-900/30", text: "text-violet-400" },
  standard: { bg: "bg-zinc-800", text: "text-zinc-400" },
  minor: { bg: "bg-zinc-800/50", text: "text-zinc-600" },
  automated: { bg: "bg-blue-900/20", text: "text-blue-500" },
};

export default function SessionsPage() {
  const searchParams = useSearchParams();
  const projectParam = searchParams.get("project") || "";

  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState(projectParam);
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
      const sorted = (d.projects || [])
        .filter((p: Project) => p.session_count > 0)
        .sort((a: Project, b: Project) => b.session_count - a.session_count);
      setProjects(sorted);
      if (!selectedProject && sorted.length > 0) setSelectedProject(sorted[0].encoded_path);
    });
  }, []);

  const loadSessions = useCallback(() => {
    if (!selectedProject) return;
    setLoading(true);
    const params = new URLSearchParams({
      project: selectedProject,
      page: String(page),
      per_page: String(perPage),
      sort,
    });
    if (search) params.set("q", search);
    if (category) params.set("category", category);
    if (showStarred) params.set("starred", "true");
    if (showArchived) params.set("archived", "true");

    fetch(`/api/sessions?${params}`)
      .then((r) => r.json())
      .then((d) => {
        setSessions(d.sessions || []);
        setTotal(d.total || 0);
        setCounts(d.counts || counts);
        setLoading(false);
      });
  }, [selectedProject, page, search, sort, category, showStarred, showArchived]);

  useEffect(() => { loadSessions(); }, [loadSessions]);

  const toggleStar = async (sid: string, current: number) => {
    await fetch(`/api/sessions/${sid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred: !current }),
    });
    loadSessions();
  };

  const toggleArchive = async (sid: string, current: number) => {
    await fetch(`/api/sessions/${sid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ archived: !current }),
    });
    loadSessions();
  };

  const totalPages = Math.ceil(total / perPage);

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold text-zinc-100 mb-4">Sessions</h1>

      {/* Project + search row */}
      <div className="flex flex-col sm:flex-row gap-3 mb-3">
        <select
          value={selectedProject}
          onChange={(e) => { setSelectedProject(e.target.value); setPage(1); }}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200"
        >
          {projects.map((p) => (
            <option key={p.encoded_path} value={p.encoded_path}>
              {p.display_name} ({p.session_count})
            </option>
          ))}
        </select>

        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search sessions..."
            className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
          />
        </div>

        <select
          value={sort}
          onChange={(e) => { setSort(e.target.value); setPage(1); }}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200"
        >
          <option value="importance">By Importance</option>
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
          <option value="rating">By Rating</option>
          <option value="size">By Size</option>
        </select>
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <FilterChip active={!category && !showStarred && !showArchived} onClick={() => { setCategory(""); setShowStarred(false); setShowArchived(false); setPage(1); }} label={`All (${counts.all})`} />
        <FilterChip active={showStarred} onClick={() => { setShowStarred(!showStarred); setCategory(""); setShowArchived(false); setPage(1); }} label={`Starred (${counts.starred})`} icon={<Star className="w-3 h-3" />} color="text-amber-400" />
        <FilterChip active={category === "major"} onClick={() => { setCategory(category === "major" ? "" : "major"); setShowStarred(false); setPage(1); }} label={`Major (${counts.major || 0})`} color="text-violet-400" />
        <FilterChip active={category === "standard"} onClick={() => { setCategory(category === "standard" ? "" : "standard"); setShowStarred(false); setPage(1); }} label={`Standard (${counts.standard || 0})`} />
        <FilterChip active={category === "automated"} onClick={() => { setCategory(category === "automated" ? "" : "automated"); setShowStarred(false); setPage(1); }} label={`Automated (${counts.automated || 0})`} color="text-blue-400" />
        <FilterChip active={category === "minor"} onClick={() => { setCategory(category === "minor" ? "" : "minor"); setShowStarred(false); setPage(1); }} label={`Minor (${counts.minor || 0})`} color="text-zinc-600" />
        <FilterChip active={showArchived} onClick={() => { setShowArchived(!showArchived); setCategory(""); setShowStarred(false); setPage(1); }} label={`Archived (${counts.archived})`} icon={<Archive className="w-3 h-3" />} color="text-zinc-500" />
      </div>

      {/* Results */}
      <div className="text-zinc-500 text-xs mb-3">
        {total} sessions | Page {page}/{totalPages || 1}
      </div>

      {loading ? (
        <div className="animate-pulse text-zinc-500 py-8 text-center">Indexing sessions...</div>
      ) : (
        <div className="space-y-1.5">
          {sessions.map((s) => {
            const catStyle = CAT_COLORS[s.category] || CAT_COLORS.standard;
            const title = s.custom_title || s.first_message?.slice(0, 120) || "—";
            return (
              <div
                key={s.session_id}
                className={`flex items-start gap-2 bg-zinc-900 border rounded-lg px-3 py-2.5 transition-colors ${
                  s.starred ? "border-amber-800/40" : "border-zinc-800 hover:border-zinc-600"
                }`}
              >
                {/* Star button */}
                <button
                  onClick={() => toggleStar(s.session_id, s.starred)}
                  className="mt-0.5 flex-shrink-0"
                >
                  <Star className={`w-4 h-4 ${s.starred ? "fill-amber-400 text-amber-400" : "text-zinc-700 hover:text-zinc-500"}`} />
                </button>

                {/* Content */}
                <Link href={`/sessions/${s.session_id}`} className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider font-bold ${catStyle.bg} ${catStyle.text}`}>
                      {s.category}
                    </span>
                    {s.rating > 0 && (
                      <span className="text-amber-500 text-[10px]">{"★".repeat(s.rating)}</span>
                    )}
                    <span className="text-zinc-600 text-[10px] font-mono">
                      {s.started_at ? new Date(s.started_at).toLocaleDateString() : "?"}
                    </span>
                    <span className="text-zinc-700 text-[10px]">{s.message_count} msg</span>
                    {s.importance >= 50 && (
                      <span className="text-violet-500 text-[10px]">
                        <Zap className="w-3 h-3 inline" /> {s.importance.toFixed(0)}
                      </span>
                    )}
                  </div>
                  <p className="text-zinc-200 text-sm truncate">{title}</p>
                  {s.custom_title && s.first_message && (
                    <p className="text-zinc-600 text-xs truncate mt-0.5">{s.first_message.slice(0, 100)}</p>
                  )}
                </Link>

                {/* Archive button */}
                <button
                  onClick={() => toggleArchive(s.session_id, s.archived)}
                  className="mt-0.5 flex-shrink-0"
                  title={s.archived ? "Unarchive" : "Archive"}
                >
                  <Archive className={`w-3.5 h-3.5 ${s.archived ? "text-zinc-400" : "text-zinc-800 hover:text-zinc-500"}`} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="p-1.5 rounded bg-zinc-800 text-zinc-400 disabled:opacity-30 hover:bg-zinc-700">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-zinc-500 text-sm">Page {page} / {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="p-1.5 rounded bg-zinc-800 text-zinc-400 disabled:opacity-30 hover:bg-zinc-700">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}

function FilterChip({ active, onClick, label, icon, color }: {
  active: boolean;
  onClick: () => void;
  label: string;
  icon?: React.ReactNode;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs transition-colors ${
        active
          ? "bg-violet-600 text-white"
          : `bg-zinc-800 hover:bg-zinc-700 ${color || "text-zinc-400"}`
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
