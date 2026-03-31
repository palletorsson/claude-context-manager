"use client";

import { useEffect, useState } from "react";
import {
  ChevronRight, ChevronDown, Circle, CheckCircle2, AlertCircle,
  Clock, Minus, Plus, Sparkles, GitBranch, Pencil, X, Save,
} from "lucide-react";

interface TreeNode {
  id: string;
  label: string;
  type: "branch" | "leaf";
  status: string;
  children?: TreeNode[];
  note?: string;
  priority?: number;
  overridden?: boolean;
  map_count?: number;
  phase?: string;
  order?: number;
}

interface TreeData {
  generated: string;
  project: string;
  children: TreeNode[];
  stats: Record<string, number>;
}

interface Project { encoded_path: string; display_name: string; full_path: string; session_count: number; }

const STATUS_ICON: Record<string, { icon: typeof Circle; color: string }> = {
  done: { icon: CheckCircle2, color: "text-[var(--color-success)]" },
  complete: { icon: CheckCircle2, color: "text-[var(--color-success)]" },
  active: { icon: Clock, color: "text-[var(--color-accent)]" },
  partial: { icon: AlertCircle, color: "text-[var(--color-attention)]" },
  exists: { icon: Circle, color: "text-[var(--color-fg-subtle)]" },
  todo: { icon: Minus, color: "text-[var(--color-border)]" },
  empty: { icon: Minus, color: "text-[var(--color-danger)]" },
  blocked: { icon: AlertCircle, color: "text-[var(--color-danger)]" },
  noted: { icon: Sparkles, color: "text-[var(--color-done)]" },
};

const STATUSES = ["done", "active", "partial", "todo", "empty", "blocked", "noted"];

export default function TreePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [tree, setTree] = useState<TreeData | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["game", "encyclopedia", "context", "writer", "discoveries"]));
  const [editing, setEditing] = useState<string | null>(null);
  const [editStatus, setEditStatus] = useState("");
  const [editNote, setEditNote] = useState("");
  const [discoveryLabel, setDiscoveryLabel] = useState("");
  const [discoveryNote, setDiscoveryNote] = useState("");
  const [showAddDiscovery, setShowAddDiscovery] = useState(false);

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const sorted = (d.projects || []).filter((p: Project) => p.session_count > 0).sort((a: Project, b: Project) => b.session_count - a.session_count);
      setProjects(sorted);
      if (sorted.length > 0) setSelectedProject(sorted[0].encoded_path);
    });
  }, []);

  const loadTree = () => {
    if (!selectedProject) return;
    const proj = projects.find((p) => p.encoded_path === selectedProject);
    const repoPath = proj?.full_path || "";
    fetch(`/api/tree?project=${selectedProject}&repo=${encodeURIComponent(repoPath)}`)
      .then((r) => r.json()).then(setTree).catch(() => {});
  };

  useEffect(() => { loadTree(); }, [selectedProject, projects]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const startEdit = (node: TreeNode) => {
    setEditing(node.id);
    setEditStatus(node.status);
    setEditNote(node.note || "");
  };

  const saveEdit = async () => {
    if (!editing) return;
    await fetch(`/api/tree/override?project=${selectedProject}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: editing, status: editStatus, note: editNote }),
    });
    setEditing(null);
    loadTree();
  };

  const addDiscovery = async () => {
    if (!discoveryLabel.trim()) return;
    await fetch(`/api/tree/discovery?project=${selectedProject}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: discoveryLabel, note: discoveryNote }),
    });
    setDiscoveryLabel("");
    setDiscoveryNote("");
    setShowAddDiscovery(false);
    loadTree();
  };

  if (!tree) return <div className="p-8 text-[var(--color-fg-subtle)]">Loading tree...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-fg-default)] flex items-center gap-2">
            <GitBranch className="w-6 h-6 text-[var(--color-done)]" /> Working Tree
          </h1>
          <p className="text-xs text-[var(--color-fg-subtle)] mt-0.5">
            Auto-generated + manual overrides. Click any node to annotate.
          </p>
        </div>
        <div className="flex gap-2">
          <select value={selectedProject} onChange={(e) => setSelectedProject(e.target.value)}
            className="border border-[var(--color-border)] rounded-md px-3 py-1.5 text-sm bg-[var(--color-bg-subtle)]">
            {projects.map((p) => <option key={p.encoded_path} value={p.encoded_path}>{p.display_name}</option>)}
          </select>
          <button onClick={() => setShowAddDiscovery(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-[var(--color-done)] text-white rounded-md text-sm hover:opacity-90">
            <Sparkles className="w-3.5 h-3.5" /> Add Discovery
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex flex-wrap gap-3 mb-4 text-xs">
        {Object.entries(tree.stats).filter(([k]) => k !== "total").map(([status, count]) => {
          if (count === 0) return null;
          const s = STATUS_ICON[status] || STATUS_ICON.todo;
          const Icon = s.icon;
          return (
            <span key={status} className={`flex items-center gap-1 ${s.color}`}>
              <Icon className="w-3 h-3" /> {status}: {count}
            </span>
          );
        })}
        <span className="text-[var(--color-fg-subtle)]">total: {tree.stats.total}</span>
      </div>

      {/* Add discovery form */}
      {showAddDiscovery && (
        <div className="border-2 border-[var(--color-done)] rounded-md p-3 mb-4 bg-[#f5f0ff]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold">Add Discovery</span>
            <button onClick={() => setShowAddDiscovery(false)}><X className="w-4 h-4 text-[var(--color-fg-subtle)]" /></button>
          </div>
          <input value={discoveryLabel} onChange={(e) => setDiscoveryLabel(e.target.value)} placeholder="What did you discover?"
            className="w-full px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm mb-2" />
          <input value={discoveryNote} onChange={(e) => setDiscoveryNote(e.target.value)} placeholder="Details (optional)"
            className="w-full px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm mb-2" />
          <button onClick={addDiscovery} disabled={!discoveryLabel.trim()}
            className="px-4 py-1.5 bg-[var(--color-done)] text-white rounded-md text-sm disabled:opacity-40">Add</button>
        </div>
      )}

      {/* Tree */}
      <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
        {tree.children.map((node) => (
          <TreeNodeView
            key={node.id}
            node={node}
            depth={0}
            expanded={expanded}
            toggle={toggle}
            editing={editing}
            editStatus={editStatus}
            editNote={editNote}
            setEditStatus={setEditStatus}
            setEditNote={setEditNote}
            startEdit={startEdit}
            saveEdit={saveEdit}
            cancelEdit={() => setEditing(null)}
          />
        ))}
      </div>
    </div>
  );
}

function TreeNodeView({ node, depth, expanded, toggle, editing, editStatus, editNote, setEditStatus, setEditNote, startEdit, saveEdit, cancelEdit }: {
  node: TreeNode; depth: number; expanded: Set<string>; toggle: (id: string) => void;
  editing: string | null; editStatus: string; editNote: string;
  setEditStatus: (s: string) => void; setEditNote: (s: string) => void;
  startEdit: (n: TreeNode) => void; saveEdit: () => void; cancelEdit: () => void;
}) {
  const isExpanded = expanded.has(node.id);
  const hasChildren = node.children && node.children.length > 0;
  const isEditing = editing === node.id;
  const statusInfo = STATUS_ICON[node.status] || STATUS_ICON.todo;
  const StatusIcon = statusInfo.icon;

  return (
    <>
      <div
        className={`flex items-center gap-1.5 px-3 py-1.5 hover:bg-[var(--color-bg-subtle)] transition-colors cursor-pointer group ${depth > 0 ? "border-t border-[var(--color-border-muted)]" : depth === 0 ? "border-t border-[var(--color-border)]" : ""}`}
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
      >
        {/* Expand toggle */}
        {hasChildren ? (
          <button onClick={() => toggle(node.id)} className="shrink-0">
            {isExpanded ? <ChevronDown className="w-4 h-4 text-[var(--color-fg-subtle)]" /> : <ChevronRight className="w-4 h-4 text-[var(--color-fg-subtle)]" />}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}

        {/* Status icon */}
        <StatusIcon className={`w-4 h-4 shrink-0 ${statusInfo.color}`} />

        {/* Label */}
        <span className={`text-sm flex-1 ${node.type === "branch" ? "font-medium" : ""} ${node.status === "empty" ? "text-[var(--color-danger)]" : node.status === "done" || node.status === "complete" ? "text-[var(--color-success)]" : "text-[var(--color-fg-default)]"}`}
          onClick={() => startEdit(node)}>
          {node.label}
          {node.map_count !== undefined && <span className="text-[10px] text-[var(--color-fg-subtle)] ml-1">({node.map_count} maps)</span>}
          {node.phase && <span className="text-[10px] text-[var(--color-done)] ml-1">{node.phase}</span>}
          {node.overridden && <span className="text-[10px] text-[var(--color-attention)] ml-1">*</span>}
        </span>

        {/* Note preview */}
        {node.note && !isEditing && (
          <span className="text-[10px] text-[var(--color-fg-subtle)] truncate max-w-48">{node.note}</span>
        )}

        {/* Edit button */}
        <button onClick={() => startEdit(node)} className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5">
          <Pencil className="w-3 h-3 text-[var(--color-fg-subtle)]" />
        </button>
      </div>

      {/* Inline edit form */}
      {isEditing && (
        <div className="px-3 py-2 bg-[#ddf4ff] border-t border-[var(--color-accent)]" style={{ paddingLeft: `${depth * 20 + 36}px` }}>
          <div className="flex items-center gap-2 mb-1.5">
            <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}
              className="border border-[var(--color-border)] rounded px-2 py-1 text-xs bg-white">
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <input value={editNote} onChange={(e) => setEditNote(e.target.value)} placeholder="Note..."
              className="flex-1 px-2 py-1 border border-[var(--color-border)] rounded text-xs" />
            <button onClick={saveEdit} className="px-2 py-1 bg-[var(--color-accent)] text-white rounded text-xs"><Save className="w-3 h-3" /></button>
            <button onClick={cancelEdit} className="px-2 py-1 border border-[var(--color-border)] rounded text-xs"><X className="w-3 h-3" /></button>
          </div>
        </div>
      )}

      {/* Children */}
      {isExpanded && hasChildren && node.children!.map((child) => (
        <TreeNodeView
          key={child.id}
          node={child}
          depth={depth + 1}
          expanded={expanded}
          toggle={toggle}
          editing={editing}
          editStatus={editStatus}
          editNote={editNote}
          setEditStatus={setEditStatus}
          setEditNote={setEditNote}
          startEdit={startEdit}
          saveEdit={saveEdit}
          cancelEdit={cancelEdit}
        />
      ))}
    </>
  );
}
