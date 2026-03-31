"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FileText, Plus, Save, X, GitBranch } from "lucide-react";

interface MemoryFile { filename: string; file_size: number; modified_at: string; status: string; summary: string; }
interface Project { encoded_path: string; display_name: string; memory_count: number; }

const STATUS_STYLE: Record<string, string> = {
  active: "bg-[#dafbe1] text-[var(--color-success)] border-[#aceebb]",
  paused: "bg-[#fff8c5] text-[var(--color-attention)] border-[#eac54f]",
  merged: "bg-[#ddf4ff] text-[var(--color-accent)] border-[#54aeff]",
  archived: "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)] border-[var(--color-border)]",
};

export default function MemoryPage() {
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState(searchParams.get("project") || "");
  const [files, setFiles] = useState<MemoryFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/projects").then((r) => r.json()).then((d) => {
      const withMemory = (d.projects || []).filter((p: Project) => p.memory_count > 0);
      setProjects(withMemory);
      if (!selectedProject && withMemory.length > 0) setSelectedProject(withMemory[0].encoded_path);
    });
  }, []);

  useEffect(() => {
    if (!selectedProject) return;
    fetch(`/api/memory?project=${selectedProject}`).then((r) => r.json()).then((d) => setFiles(d.files || []));
  }, [selectedProject]);

  const loadFile = (filename: string) => {
    setSelectedFile(filename); setEditing(false);
    fetch(`/api/memory/${selectedProject}/${filename}`).then((r) => r.json()).then((d) => setContent(d.content || ""));
  };

  const saveFile = async () => {
    await fetch(`/api/memory/${selectedProject}/${selectedFile}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) });
    setSaveStatus("Saved"); setEditing(false); setTimeout(() => setSaveStatus(null), 2000);
  };

  const createFile = async () => {
    if (!newName.trim()) return;
    let fn = newName; if (!fn.endsWith(".md")) fn += ".md";
    await fetch(`/api/memory/${selectedProject}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: fn, content: newContent }) });
    setCreating(false); setNewName(""); setNewContent("");
    const d = await fetch(`/api/memory?project=${selectedProject}`).then((r) => r.json());
    setFiles(d.files || []);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-[var(--color-fg-default)]">Memory Files</h1>
        <div className="flex gap-2">
          <select value={selectedProject} onChange={(e) => { setSelectedProject(e.target.value); setSelectedFile(null); }}
            className="border border-[var(--color-border)] rounded-md px-3 py-1.5 text-sm bg-[var(--color-bg-subtle)]">
            {projects.map((p) => <option key={p.encoded_path} value={p.encoded_path}>{p.display_name} ({p.memory_count})</option>)}
          </select>
          <button onClick={() => setCreating(true)}
            className="flex items-center gap-1 px-3 py-1.5 bg-[var(--color-success)] text-white rounded-md text-sm hover:opacity-90">
            <Plus className="w-3.5 h-3.5" /> New Thread
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {/* File list */}
        <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
          {files.map((f, i) => (
            <button key={f.filename} onClick={() => loadFile(f.filename)}
              className={`w-full text-left px-3 py-2.5 transition-colors ${selectedFile === f.filename ? "bg-[#ddf4ff]" : "hover:bg-[var(--color-bg-subtle)]"} ${i > 0 ? "border-t border-[var(--color-border-muted)]" : ""}`}>
              <div className="flex items-center gap-2 mb-0.5">
                {f.filename.startsWith("thread_") || f.filename.startsWith("meta_thread_") ? <GitBranch className="w-3.5 h-3.5 text-[var(--color-done)]" /> : <FileText className="w-3.5 h-3.5 text-[var(--color-fg-subtle)]" />}
                <span className="text-sm font-medium text-[var(--color-fg-default)] truncate">{f.filename.replace(".md", "")}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${STATUS_STYLE[f.status] || STATUS_STYLE.active}`}>{f.status}</span>
                <span className="text-[10px] text-[var(--color-fg-subtle)]">{(f.file_size / 1024).toFixed(1)}KB</span>
              </div>
            </button>
          ))}
        </div>

        {/* Editor */}
        <div className="md:col-span-2">
          {creating ? (
            <div className="border border-[var(--color-border)] rounded-md p-4">
              <h3 className="font-semibold mb-3">Create New Thread</h3>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="thread_my_topic.md"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm mb-3 focus:outline-none focus:border-[var(--color-accent)]" />
              <textarea value={newContent} onChange={(e) => setNewContent(e.target.value)}
                placeholder="# Thread: My Topic&#10;&#10;## Status: ACTIVE&#10;&#10;## Open Questions&#10;- ..."
                rows={12} className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm font-mono mb-3 focus:outline-none focus:border-[var(--color-accent)]" />
              <div className="flex gap-2">
                <button onClick={createFile} className="px-4 py-1.5 bg-[var(--color-success)] text-white rounded-md text-sm">Create</button>
                <button onClick={() => setCreating(false)} className="px-4 py-1.5 border border-[var(--color-border)] rounded-md text-sm">Cancel</button>
              </div>
            </div>
          ) : selectedFile ? (
            <div className="border border-[var(--color-border)] rounded-md overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-[var(--color-bg-subtle)] border-b border-[var(--color-border)]">
                <span className="text-sm font-medium">{selectedFile}</span>
                <div className="flex items-center gap-2">
                  {saveStatus && <span className="text-xs text-[var(--color-success)]">{saveStatus}</span>}
                  {editing ? (
                    <>
                      <button onClick={saveFile} className="flex items-center gap-1 px-2 py-1 bg-[var(--color-success)] text-white rounded text-xs"><Save className="w-3 h-3" /> Save</button>
                      <button onClick={() => { setEditing(false); loadFile(selectedFile); }} className="px-2 py-1 border border-[var(--color-border)] rounded text-xs">Cancel</button>
                    </>
                  ) : (
                    <button onClick={() => setEditing(true)} className="px-2 py-1 border border-[var(--color-border)] rounded text-xs hover:bg-[var(--color-bg-subtle)]">Edit</button>
                  )}
                </div>
              </div>
              {editing ? (
                <textarea value={content} onChange={(e) => setContent(e.target.value)}
                  className="w-full p-3 text-sm font-mono min-h-[500px] focus:outline-none resize-y border-none" />
              ) : (
                <pre className="p-3 text-sm whitespace-pre-wrap font-mono overflow-auto max-h-[600px] text-[var(--color-fg-default)]">{content}</pre>
              )}
            </div>
          ) : (
            <div className="text-[var(--color-fg-subtle)] text-center py-20 border border-dashed border-[var(--color-border)] rounded-md">
              Select a memory file to view
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
