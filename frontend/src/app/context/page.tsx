"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, Plus, Search, Trash2, X } from "lucide-react";

interface ContextBranch {
  id: string;
  type: string;
  content: string;
  summary: string;
  tags: string[];
  created_at: string;
}

const TYPES = ["formula", "clause", "pattern", "insight", "substrate"];

const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  formula: { bg: "bg-indigo-900/30", text: "text-indigo-400" },
  clause: { bg: "bg-green-900/30", text: "text-green-400" },
  pattern: { bg: "bg-orange-900/30", text: "text-orange-400" },
  insight: { bg: "bg-pink-900/30", text: "text-pink-400" },
  substrate: { bg: "bg-cyan-900/30", text: "text-cyan-400" },
};

export default function ContextPage() {
  const searchParams = useSearchParams();
  const typeParam = searchParams.get("type") || "";

  const [branches, setBranches] = useState<ContextBranch[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selectedType, setSelectedType] = useState(typeParam);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Create form
  const [newType, setNewType] = useState("insight");
  const [newContent, setNewContent] = useState("");
  const [newSummary, setNewSummary] = useState("");
  const [newTags, setNewTags] = useState("");

  const loadBranches = () => {
    const params = new URLSearchParams();
    if (selectedType) params.set("type", selectedType);
    if (search) params.set("q", search);
    fetch(`/api/context?${params}`).then((r) => r.json()).then((d) => setBranches(d.results || []));
    fetch("/api/context/stats").then((r) => r.json()).then((d) => setStats(d.stats || {}));
  };

  useEffect(() => { loadBranches(); }, [selectedType, search]);

  const handleCreate = async () => {
    const res = await fetch("/api/context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: newType,
        content: newContent,
        summary: newSummary || undefined,
        tags: newTags ? newTags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
      }),
    });
    if (res.ok) {
      setCreating(false);
      setNewContent("");
      setNewSummary("");
      setNewTags("");
      loadBranches();
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/context/${id}`, { method: "DELETE" });
    loadBranches();
  };

  const totalCount = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
          <Zap className="w-6 h-6 text-amber-400" />
          Context Branches
        </h1>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-1 px-3 py-1.5 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-500"
        >
          <Plus className="w-3.5 h-3.5" /> Add Branch
        </button>
      </div>

      {/* Type filter tabs */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <button
          onClick={() => setSelectedType("")}
          className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
            !selectedType ? "bg-violet-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
          }`}
        >
          All ({totalCount})
        </button>
        {TYPES.map((t) => {
          const colors = TYPE_COLORS[t] || TYPE_COLORS.insight;
          return (
            <button
              key={t}
              onClick={() => setSelectedType(selectedType === t ? "" : t)}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                selectedType === t ? `${colors.bg} ${colors.text}` : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {t} ({stats[t] || 0})
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search content, summaries, tags..."
          className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-violet-500"
        />
      </div>

      {/* Create form */}
      {creating && (
        <div className="bg-zinc-900 border border-violet-500/30 rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-zinc-200 font-semibold">New Context Branch</h3>
            <button onClick={() => setCreating(false)} className="text-zinc-500 hover:text-zinc-300">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid gap-3">
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-sm text-zinc-200"
            >
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input
              value={newSummary}
              onChange={(e) => setNewSummary(e.target.value)}
              placeholder="Summary (one line)"
              className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600"
            />
            <textarea
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="Full content..."
              rows={6}
              className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600 font-mono"
            />
            <input
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
              placeholder="Tags (comma separated)"
              className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 placeholder-zinc-600"
            />
            <button
              onClick={handleCreate}
              disabled={!newContent.trim()}
              className="px-4 py-1.5 bg-violet-600 text-white rounded text-sm hover:bg-violet-500 disabled:opacity-40 w-fit"
            >
              Create Branch
            </button>
          </div>
        </div>
      )}

      {/* Branch list */}
      <div className="space-y-2">
        {branches.map((b) => {
          const colors = TYPE_COLORS[b.type] || TYPE_COLORS.insight;
          const isExpanded = expanded === b.id;
          return (
            <div
              key={b.id}
              className={`bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 cursor-pointer hover:border-zinc-600 transition-colors ${
                isExpanded ? "border-zinc-600" : ""
              }`}
              onClick={() => setExpanded(isExpanded ? null : b.id)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${colors.bg} ${colors.text}`}>
                      {b.type}
                    </span>
                    <span className="text-zinc-200 text-sm font-medium truncate">
                      {b.summary || b.content.slice(0, 80)}
                    </span>
                  </div>
                  {b.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {b.tags.slice(0, 6).map((tag) => (
                        <span key={tag} className="text-[10px] bg-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                      {b.tags.length > 6 && (
                        <span className="text-[10px] text-zinc-600">+{b.tags.length - 6}</span>
                      )}
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(b.id); }}
                  className="text-zinc-700 hover:text-red-400 p-1 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-zinc-800">
                  <pre className="text-zinc-300 text-sm whitespace-pre-wrap font-mono">{b.content}</pre>
                  <div className="mt-2 text-zinc-600 text-xs">
                    Created: {b.created_at ? new Date(b.created_at).toLocaleString() : "?"}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {branches.length === 0 && (
        <div className="text-zinc-600 text-center py-12">
          No context branches {selectedType ? `of type "${selectedType}"` : ""} {search ? `matching "${search}"` : ""}
        </div>
      )}
    </div>
  );
}
