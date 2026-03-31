"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, Plus, Search, Trash2, X, ChevronDown } from "lucide-react";

interface ContextBranch { id: string; type: string; content: string; summary: string; tags: string[]; created_at: string; }

const TYPES = ["formula", "clause", "pattern", "insight", "substrate"];
const TYPE_STYLE: Record<string, string> = {
  formula: "bg-[#ddf4ff] text-[var(--color-accent)] border-[#54aeff]",
  clause: "bg-[#dafbe1] text-[var(--color-success)] border-[#aceebb]",
  pattern: "bg-[#fff8c5] text-[var(--color-attention)] border-[#eac54f]",
  insight: "bg-[#ffeff7] text-[#bf3989] border-[#f0a0c0]",
  substrate: "bg-[#ddf4ff] text-[#0550ae] border-[#54aeff]",
};

export default function ContextPage() {
  const searchParams = useSearchParams();
  const [branches, setBranches] = useState<ContextBranch[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selectedType, setSelectedType] = useState(searchParams.get("type") || "");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
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
    await fetch("/api/context", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: newType, content: newContent, summary: newSummary || undefined, tags: newTags ? newTags.split(",").map((t) => t.trim()).filter(Boolean) : undefined }) });
    setCreating(false); setNewContent(""); setNewSummary(""); setNewTags(""); loadBranches();
  };

  const handleDelete = async (id: string) => { await fetch(`/api/context/${id}`, { method: "DELETE" }); loadBranches(); };

  const totalCount = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-[var(--color-fg-default)] flex items-center gap-2">
          <Zap className="w-6 h-6 text-[var(--color-attention)]" /> Context Branches
        </h1>
        <button onClick={() => setCreating(true)}
          className="flex items-center gap-1 px-3 py-1.5 bg-[var(--color-success)] text-white rounded-md text-sm hover:opacity-90">
          <Plus className="w-3.5 h-3.5" /> Add Branch
        </button>
      </div>

      {/* Type tabs */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        <Chip active={!selectedType} onClick={() => setSelectedType("")} label={`All (${totalCount})`} />
        {TYPES.map((t) => (
          <Chip key={t} active={selectedType === t} onClick={() => setSelectedType(selectedType === t ? "" : t)} label={`${t} (${stats[t] || 0})`} />
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-fg-subtle)]" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search content, summaries, tags..."
          className="w-full pl-10 pr-4 py-1.5 border border-[var(--color-border)] rounded-md text-sm focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]" />
      </div>

      {/* Create form */}
      {creating && (
        <div className="border-2 border-[var(--color-accent)] rounded-md p-4 mb-4 bg-[#ddf4ff]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold">New Context Branch</h3>
            <button onClick={() => setCreating(false)}><X className="w-4 h-4 text-[var(--color-fg-subtle)]" /></button>
          </div>
          <div className="grid gap-3">
            <select value={newType} onChange={(e) => setNewType(e.target.value)}
              className="border border-[var(--color-border)] rounded-md px-3 py-1.5 text-sm">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input value={newSummary} onChange={(e) => setNewSummary(e.target.value)} placeholder="Summary (one line)"
              className="px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm" />
            <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="Full content..." rows={6}
              className="px-3 py-2 border border-[var(--color-border)] rounded-md text-sm font-mono" />
            <input value={newTags} onChange={(e) => setNewTags(e.target.value)} placeholder="Tags (comma separated)"
              className="px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm" />
            <button onClick={handleCreate} disabled={!newContent.trim()}
              className="px-4 py-1.5 bg-[var(--color-success)] text-white rounded-md text-sm disabled:opacity-40 w-fit">Create</button>
          </div>
        </div>
      )}

      {/* Branch list */}
      <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
        {branches.length === 0 ? (
          <div className="text-[var(--color-fg-subtle)] text-center py-12">
            No context branches {selectedType ? `of type "${selectedType}"` : ""} {search ? `matching "${search}"` : ""}
          </div>
        ) : branches.map((b, i) => {
          const isExpanded = expanded === b.id;
          return (
            <div key={b.id} className={`${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
              <div className={`flex items-start justify-between gap-3 px-3 py-2.5 cursor-pointer hover:bg-[var(--color-bg-subtle)] transition-colors ${isExpanded ? "bg-[var(--color-bg-subtle)]" : ""}`}
                onClick={() => setExpanded(isExpanded ? null : b.id)}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-bold uppercase tracking-wider ${TYPE_STYLE[b.type] || TYPE_STYLE.insight}`}>{b.type}</span>
                    <span className="text-sm font-medium text-[var(--color-fg-default)] truncate">{b.summary || b.content.slice(0, 80)}</span>
                  </div>
                  {b.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {b.tags.slice(0, 6).map((tag) => (
                        <span key={tag} className="text-[10px] bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)] px-1.5 py-0.5 rounded-full border border-[var(--color-border-muted)]">{tag}</span>
                      ))}
                      {b.tags.length > 6 && <span className="text-[10px] text-[var(--color-fg-subtle)]">+{b.tags.length - 6}</span>}
                    </div>
                  )}
                </div>
                <button onClick={(e) => { e.stopPropagation(); handleDelete(b.id); }}
                  className="text-[var(--color-border)] hover:text-[var(--color-danger)] p-1 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              {isExpanded && (
                <div className="px-3 pb-3 border-t border-[var(--color-border-muted)] bg-[var(--color-bg-subtle)]">
                  <pre className="text-sm whitespace-pre-wrap font-mono py-2 text-[var(--color-fg-default)]">{b.content}</pre>
                  <div className="text-[10px] text-[var(--color-fg-subtle)]">Created: {b.created_at ? new Date(b.created_at).toLocaleString() : "?"}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
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
