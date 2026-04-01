"""Benchmark: cached vs uncached performance on real session data.

Measures:
1. Session indexing: full parse vs hash-gated skip
2. Topic clustering: full Jaccard vs cached result
3. Memory metadata: full file read vs hash-gated cache
4. Projects discovery: full scan vs mtime cache

Outputs a table suitable for inclusion in the paper.
"""

import json
import sys
import time
import statistics
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from config import PROJECTS_DIR
from services.claude_fs import discover_projects as list_projects, list_session_files
from services.indexer import index_session
from services.variety import (
    file_content_hash,
    compute_sessions_hash,
    get_cached_topics,
    compute_temperature,
)
from services.topic_extractor import extract_topics_from_sessions as extract_topics
from db import db_connection, init_db


def discover_data():
    """Find all projects and session files."""
    projects = list_projects()
    total_sessions = 0
    total_bytes = 0
    session_files = []

    for p in projects:
        files = list_session_files(p["encoded_path"])
        for f in files:
            stat = f.stat()
            session_files.append({
                "path": f,
                "project": p["encoded_path"],
                "size": stat.st_size,
            })
            total_bytes += stat.st_size
        total_sessions += len(files)

    return projects, session_files, total_bytes


def benchmark_session_indexing(session_files, runs=3):
    """Benchmark full JSONL parse vs content hash computation."""
    # Pick a representative sample (up to 20 sessions, mix of sizes)
    sample = sorted(session_files, key=lambda s: s["size"], reverse=True)[:20]

    results = {
        "full_parse_times": [],
        "hash_only_times": [],
        "files_tested": len(sample),
        "total_bytes": sum(s["size"] for s in sample),
    }

    for s in sample:
        # Full parse (what happens when no cache exists)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            index_session(s["path"])
            t1 = time.perf_counter()
            times.append(t1 - t0)
        results["full_parse_times"].append(statistics.median(times))

        # Hash only (what happens when mtime differs but content same)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            file_content_hash(s["path"])
            t1 = time.perf_counter()
            times.append(t1 - t0)
        results["hash_only_times"].append(statistics.median(times))

    return results


def benchmark_topic_clustering(projects):
    """Benchmark full topic extraction vs cached lookup."""
    results = {
        "full_extract_times": [],
        "cached_lookup_times": [],
        "projects_tested": 0,
    }

    for p in projects:
        project_path = p["encoded_path"]
        files = list_session_files(project_path)
        if len(files) < 3:
            continue

        results["projects_tested"] += 1

        # Full extraction
        with db_connection() as db:
            rows = db.execute(
                "SELECT session_id, first_message FROM sessions WHERE project_path = ?",
                (project_path,)
            ).fetchall()

        if not rows:
            continue

        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            extract_topics(project_path)
            t1 = time.perf_counter()
            times.append(t1 - t0)
        results["full_extract_times"].append(statistics.median(times))

        # Cached lookup (after first computation populates cache)
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            get_cached_topics(project_path)
            t1 = time.perf_counter()
            times.append(t1 - t0)
        results["cached_lookup_times"].append(statistics.median(times))

    return results


def benchmark_memory_metadata(projects):
    """Benchmark full file read + status detection vs hash-gated cache."""
    results = {
        "full_read_times": [],
        "hash_check_times": [],
        "files_tested": 0,
    }

    for p in projects:
        memory_dir = PROJECTS_DIR / p["encoded_path"] / "memory"
        if not memory_dir.exists():
            continue

        for md_file in memory_dir.glob("*.md"):
            results["files_tested"] += 1

            # Full read + parse
            times = []
            for _ in range(3):
                t0 = time.perf_counter()
                content = md_file.read_text(encoding="utf-8")
                # Simulate status detection
                lines = content.split("\n")
                status = "active"
                summary = ""
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith("## Status:"):
                        status = line_stripped.split(":", 1)[1].strip().lower()
                    if not summary and line_stripped and not line_stripped.startswith(("#", "---", ">")):
                        summary = line_stripped[:200]
                t1 = time.perf_counter()
                times.append(t1 - t0)
            results["full_read_times"].append(statistics.median(times))

            # Hash check only
            times = []
            for _ in range(3):
                t0 = time.perf_counter()
                file_content_hash(md_file)
                t1 = time.perf_counter()
                times.append(t1 - t0)
            results["hash_check_times"].append(statistics.median(times))

    return results


def benchmark_projects_discovery():
    """Benchmark full project directory scan."""
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        list_projects()
        t1 = time.perf_counter()
        times.append(t1 - t0)

    # Mtime check (simulated cached path)
    mtime_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        PROJECTS_DIR.stat().st_mtime
        t1 = time.perf_counter()
        mtime_times.append(t1 - t0)

    return {
        "full_scan_ms": statistics.median(times) * 1000,
        "mtime_check_ms": statistics.median(mtime_times) * 1000,
    }


def simulate_cache_hits(session_files):
    """Simulate the three-tier gate across all sessions to measure hit rates."""
    # First pass: index everything (cold cache)
    cold_results = {"full_index": 0, "hash_match": 0, "mtime_match": 0}

    with db_connection() as db:
        for s in session_files:
            session_id = s["path"].stem
            row = db.execute(
                "SELECT file_mtime, content_hash FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            current_mtime = s["path"].stat().st_mtime

            if row and abs(row["file_mtime"] - current_mtime) < 1.0:
                cold_results["mtime_match"] += 1
                continue

            if row and row["content_hash"]:
                new_hash = file_content_hash(s["path"])
                if new_hash == row["content_hash"]:
                    cold_results["hash_match"] += 1
                    continue

            cold_results["full_index"] += 1

    return cold_results


def format_results(data, idx_results, topic_results, mem_results, proj_results, hit_results):
    """Format all results as a printable report."""
    projects, session_files, total_bytes = data

    lines = []
    lines.append("=" * 72)
    lines.append("BENCHMARK RESULTS: Claude Context Manager v0.3.0")
    lines.append("=" * 72)
    lines.append("")

    # Dataset summary
    lines.append("## Dataset")
    lines.append(f"  Projects:       {len(projects)}")
    lines.append(f"  Session files:  {len(session_files)}")
    lines.append(f"  Total size:     {total_bytes / 1024 / 1024:.1f} MB")
    sizes = [s["size"] for s in session_files]
    if sizes:
        lines.append(f"  Smallest file:  {min(sizes) / 1024:.1f} KB")
        lines.append(f"  Largest file:   {max(sizes) / 1024 / 1024:.2f} MB")
        lines.append(f"  Median file:    {statistics.median(sizes) / 1024:.1f} KB")
    lines.append("")

    # Session indexing
    lines.append("## 1. Session Indexing (N={} files, {:.1f} MB)".format(
        idx_results["files_tested"],
        idx_results["total_bytes"] / 1024 / 1024
    ))
    full_total = sum(idx_results["full_parse_times"])
    hash_total = sum(idx_results["hash_only_times"])
    lines.append(f"  Full JSONL parse (total):    {full_total * 1000:.1f} ms")
    lines.append(f"  Hash-only check (total):     {hash_total * 1000:.1f} ms")
    if full_total > 0:
        savings = (1 - hash_total / full_total) * 100
        lines.append(f"  Savings (hash vs parse):     {savings:.1f}%")
    lines.append(f"  Per-file parse (median):     {statistics.median(idx_results['full_parse_times']) * 1000:.2f} ms")
    lines.append(f"  Per-file hash (median):      {statistics.median(idx_results['hash_only_times']) * 1000:.2f} ms")
    lines.append("")

    # Topic clustering
    lines.append(f"## 2. Topic Clustering (N={topic_results['projects_tested']} projects)")
    if topic_results["full_extract_times"]:
        full_median = statistics.median(topic_results["full_extract_times"])
        cached_median = statistics.median(topic_results["cached_lookup_times"])
        lines.append(f"  Full extraction (median):    {full_median * 1000:.1f} ms")
        lines.append(f"  Cached lookup (median):      {cached_median * 1000:.3f} ms")
        if full_median > 0:
            speedup = full_median / cached_median if cached_median > 0 else float("inf")
            savings = (1 - cached_median / full_median) * 100
            lines.append(f"  Speedup:                     {speedup:.0f}x")
            lines.append(f"  Savings:                     {savings:.1f}%")
    else:
        lines.append("  (no projects with enough sessions to cluster)")
    lines.append("")

    # Memory metadata
    lines.append(f"## 3. Memory Metadata (N={mem_results['files_tested']} files)")
    if mem_results["full_read_times"]:
        full_median = statistics.median(mem_results["full_read_times"])
        hash_median = statistics.median(mem_results["hash_check_times"])
        lines.append(f"  Full read+parse (median):    {full_median * 1000:.3f} ms")
        lines.append(f"  Hash check (median):         {hash_median * 1000:.3f} ms")
        # Note: hash check reads the whole file too, so the savings come from
        # avoiding the DB upsert and status detection on cache hit
        full_total = sum(mem_results["full_read_times"])
        hash_total = sum(mem_results["hash_check_times"])
        lines.append(f"  Full read+parse (total):     {full_total * 1000:.1f} ms")
        lines.append(f"  Hash check (total):          {hash_total * 1000:.1f} ms")
    else:
        lines.append("  (no memory files found)")
    lines.append("")

    # Projects discovery
    lines.append("## 4. Projects Discovery")
    lines.append(f"  Full directory scan:         {proj_results['full_scan_ms']:.2f} ms")
    lines.append(f"  Mtime check (cached):        {proj_results['mtime_check_ms']:.4f} ms")
    if proj_results["mtime_check_ms"] > 0:
        speedup = proj_results["full_scan_ms"] / proj_results["mtime_check_ms"]
        lines.append(f"  Speedup:                     {speedup:.0f}x")
    lines.append("")

    # Cache hit simulation
    total_files = hit_results["mtime_match"] + hit_results["hash_match"] + hit_results["full_index"]
    lines.append(f"## 5. Cache Hit Rates (warm cache, N={total_files} sessions)")
    if total_files > 0:
        lines.append(f"  Mtime match (O(1) skip):     {hit_results['mtime_match']} ({hit_results['mtime_match']/total_files*100:.1f}%)")
        lines.append(f"  Hash match (content same):   {hit_results['hash_match']} ({hit_results['hash_match']/total_files*100:.1f}%)")
        lines.append(f"  Full re-index (changed):     {hit_results['full_index']} ({hit_results['full_index']/total_files*100:.1f}%)")
        skipped = hit_results["mtime_match"] + hit_results["hash_match"]
        lines.append(f"  Total avoided:               {skipped}/{total_files} ({skipped/total_files*100:.1f}%)")
    lines.append("")

    # Overall summary
    lines.append("## Summary")
    lines.append("  Subsystem               | Uncached    | Cached      | Reduction")
    lines.append("  ------------------------|-------------|-------------|----------")
    if idx_results["full_parse_times"]:
        fp = sum(idx_results["full_parse_times"]) * 1000
        hp = sum(idx_results["hash_only_times"]) * 1000
        lines.append(f"  Session indexing         | {fp:>8.1f} ms | {hp:>8.1f} ms | {(1-hp/fp)*100:.0f}%")
    if topic_results["full_extract_times"]:
        fe = statistics.median(topic_results["full_extract_times"]) * 1000
        ce = statistics.median(topic_results["cached_lookup_times"]) * 1000
        lines.append(f"  Topic clustering        | {fe:>8.1f} ms | {ce:>8.3f} ms | {(1-ce/fe)*100:.0f}%")
    if proj_results["full_scan_ms"] > 0:
        lines.append(f"  Projects discovery      | {proj_results['full_scan_ms']:>8.2f} ms | {proj_results['mtime_check_ms']:>8.4f} ms | {(1-proj_results['mtime_check_ms']/proj_results['full_scan_ms'])*100:.0f}%")
    if total_files > 0:
        lines.append(f"  Cache hit rate (warm)   |           — |           — | {skipped/total_files*100:.0f}% skipped")
    lines.append("")

    return "\n".join(lines)


def main():
    print("Initializing database...")
    init_db()

    print("Discovering data...")
    data = discover_data()
    projects, session_files, total_bytes = data
    print(f"  Found {len(projects)} projects, {len(session_files)} sessions, {total_bytes/1024/1024:.1f} MB total")

    if not session_files:
        print("ERROR: No session files found. Is CLAUDE_DIR set correctly?")
        sys.exit(1)

    # Warm the cache by indexing sessions one at a time (avoids nested DB locks)
    print("\nWarming cache (indexing all sessions)...")
    with db_connection() as db:
        for s in session_files:
            session_id = s["path"].stem
            row = db.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            if row:
                continue
            meta = index_session(s["path"])
            meta["project_path"] = s["project"]
            meta["indexed_at"] = ""
            db.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, project_path, file_path, file_size, file_mtime,
                 message_count, user_count, assistant_count,
                 first_message, last_message, started_at, model, indexed_at,
                 tools_used, category, importance, duration_mins, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meta["session_id"], s["project"], str(s["path"]),
                meta["file_size"], meta["file_mtime"],
                meta["message_count"], meta["user_count"], meta["assistant_count"],
                meta["first_message"], meta["last_message"],
                meta["started_at"], meta["model"], meta["indexed_at"],
                meta.get("tools_used", "[]"),
                meta.get("category", "standard"),
                meta.get("importance", 0),
                meta.get("duration_mins", 0),
                meta.get("content_hash", ""),
            ))
        db.commit()
    print("  Cache warmed.")

    print("\nRunning benchmarks...")

    print("  [1/5] Session indexing...")
    idx_results = benchmark_session_indexing(session_files)

    print("  [2/5] Topic clustering...")
    topic_results = benchmark_topic_clustering(projects)

    print("  [3/5] Memory metadata...")
    mem_results = benchmark_memory_metadata(projects)

    print("  [4/5] Projects discovery...")
    proj_results = benchmark_projects_discovery()

    print("  [5/5] Cache hit simulation...")
    hit_results = simulate_cache_hits(session_files)

    report = format_results(data, idx_results, topic_results, mem_results, proj_results, hit_results)

    print("\n" + report)

    # Also save to file
    output_path = Path(__file__).parent / "benchmark_results.txt"
    output_path.write_text(report, encoding="utf-8")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
