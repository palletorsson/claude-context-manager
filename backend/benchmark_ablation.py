"""Ablation benchmark: measure contribution of each tier and each feature.

Ablation 1 — Gate tiers:
  (a) mtime-only: skip if mtime matches, else full re-index
  (b) mtime + hash: skip if mtime matches, else hash-check, else full re-index
  (c) full pipeline: mtime + hash + indexing (current system)

Ablation 2 — Clone extraction:
  (a) first-message + last-summary only (baseline)
  (b) + decisions/questions (current minus turning points)
  (c) + turning points (full system)

Measures wall-clock cost and extraction yield.
"""

import json
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PROJECTS_DIR
from services.claude_fs import discover_projects as list_projects, list_session_files
from services.indexer import index_session
from services.variety import file_content_hash
from db import db_connection, init_db


def ablation_gate_tiers(session_files):
    """Simulate three gating strategies on the 20 largest files."""
    sample = sorted(session_files, key=lambda s: s["size"], reverse=True)[:20]
    total_bytes = sum(s["size"] for s in sample)

    results = {}

    # (a) mtime-only: on cache miss, go straight to full re-index (no hash check)
    times_a = []
    for s in sample:
        # Simulate: mtime differs -> full re-index (no hash tier)
        t0 = time.perf_counter()
        index_session(s["path"])
        t1 = time.perf_counter()
        times_a.append(t1 - t0)

    results["mtime_only"] = {
        "label": "Mtime-only gate",
        "description": "mtime match -> skip, else full re-index",
        "total_ms": sum(times_a) * 1000,
        "median_ms": statistics.median(times_a) * 1000,
    }

    # (b) mtime + hash: on mtime miss, check hash before re-indexing
    times_b = []
    for s in sample:
        # Simulate: mtime differs -> hash check -> content same -> skip
        t0 = time.perf_counter()
        file_content_hash(s["path"])
        t1 = time.perf_counter()
        times_b.append(t1 - t0)

    results["mtime_hash"] = {
        "label": "Mtime + hash gate",
        "description": "mtime match -> skip, else hash check, else re-index",
        "total_ms": sum(times_b) * 1000,
        "median_ms": statistics.median(times_b) * 1000,
    }

    # (c) full pipeline cost (same as mtime-only for cache miss, but this
    #     represents the cost when content HAS changed and full re-index runs)
    results["full_pipeline"] = results["mtime_only"].copy()
    results["full_pipeline"]["label"] = "Full re-index (Tier 3)"
    results["full_pipeline"]["description"] = "Full JSONL parse + metadata extraction"

    # Cost saved by hash tier (when content unchanged)
    hash_savings = (1 - sum(times_b) / sum(times_a)) * 100

    return results, hash_savings, len(sample), total_bytes


def ablation_clone_extraction(session_files):
    """Compare extraction yield: baseline vs decisions vs full (with turning points)."""
    # Pick 10 medium-to-large sessions for extraction
    candidates = [s for s in session_files if s["size"] > 50_000]
    sample = sorted(candidates, key=lambda s: s["size"], reverse=True)[:10]

    if not sample:
        return None

    # Turning-point markers (from clone.py)
    pivot_markers = [
        "actually,", "wait,", "scratch that", "instead,", "let's change",
        "on second thought", "different approach", "won't work", "doesn't work",
        "let me try", "better approach", "i was wrong",
    ]
    breakthrough_markers = [
        "the issue was", "the problem was", "root cause", "found it",
        "that fixed it", "now it works", "the fix is", "turns out",
        "the real issue", "the bug was", "aha,", "the key insight",
        "mystery solved", "that explains",
    ]
    decision_markers = [
        "decided", "chose", "approach:", "decision:", "going with", "the plan is"
    ]

    results = []

    for s in sample:
        counts = {
            "file": str(s["path"].name),
            "size_kb": s["size"] / 1024,
            "user_msgs": 0,
            "assistant_msgs": 0,
            "decisions": 0,
            "questions": 0,
            "pivots": 0,
            "breakthroughs": 0,
        }

        msg_index = 0
        try:
            with open(s["path"], "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    msg = event.get("message", {})
                    content = msg.get("content", "")

                    if isinstance(content, list):
                        texts = [b.get("text", "") for b in content
                                 if isinstance(b, dict) and b.get("type") == "text"]
                        text = "\n".join(texts)
                    elif isinstance(content, str):
                        text = content
                    else:
                        text = ""

                    text_lower = text.lower()

                    if event_type == "user":
                        counts["user_msgs"] += 1
                        msg_index += 1
                        if msg_index > 2:
                            for m in pivot_markers:
                                if m in text_lower:
                                    counts["pivots"] += 1
                                    break

                    elif event_type == "assistant" and text:
                        counts["assistant_msgs"] += 1
                        msg_index += 1

                        for m in decision_markers:
                            if m in text_lower:
                                counts["decisions"] += 1
                                break

                        for m in breakthrough_markers:
                            if m in text_lower:
                                counts["breakthroughs"] += 1
                                break

                        for sentence in text.split(". "):
                            if sentence.strip().endswith("?") and len(sentence.strip()) > 20:
                                counts["questions"] += 1

        except Exception as e:
            print(f"  Error reading {s['path']}: {e}")
            continue

        results.append(counts)

    return results


def format_ablation(gate_results, hash_savings, n_files, total_bytes, clone_results):
    lines = []
    lines.append("=" * 72)
    lines.append("ABLATION BENCHMARK RESULTS")
    lines.append("=" * 72)
    lines.append("")

    # Gate tiers
    lines.append(f"## Ablation 1: Gate Tiers (N={n_files} files, {total_bytes/1024/1024:.1f} MB)")
    lines.append("")
    lines.append(f"  {'Strategy':<30} {'Total (ms)':>12} {'Median/file (ms)':>18}")
    lines.append(f"  {'-'*30} {'-'*12} {'-'*18}")
    for key in ["mtime_hash", "mtime_only"]:
        r = gate_results[key]
        lines.append(f"  {r['label']:<30} {r['total_ms']:>12.1f} {r['median_ms']:>18.2f}")
    lines.append("")
    lines.append(f"  Hash tier savings (when content unchanged): {hash_savings:.1f}%")
    lines.append(f"  Cost of hash check vs full parse: {gate_results['mtime_hash']['total_ms']:.1f} ms vs {gate_results['mtime_only']['total_ms']:.1f} ms")
    lines.append("")
    lines.append("  Interpretation: When mtime differs but content is unchanged,")
    lines.append("  the hash tier avoids full re-indexing at ~{:.0f}% of the cost.".format(
        gate_results['mtime_hash']['total_ms'] / gate_results['mtime_only']['total_ms'] * 100
    ))
    lines.append("")

    # Clone extraction
    if clone_results:
        lines.append(f"## Ablation 2: Clone Extraction Yield (N={len(clone_results)} sessions)")
        lines.append("")

        total_decisions = sum(r["decisions"] for r in clone_results)
        total_questions = sum(r["questions"] for r in clone_results)
        total_pivots = sum(r["pivots"] for r in clone_results)
        total_breakthroughs = sum(r["breakthroughs"] for r in clone_results)
        total_tp = total_pivots + total_breakthroughs
        total_baseline = 0  # first msg + last summary = always 2 items per session
        n = len(clone_results)

        lines.append(f"  {'Extraction level':<40} {'Total':>8} {'Per session':>12}")
        lines.append(f"  {'-'*40} {'-'*8} {'-'*12}")
        lines.append(f"  {'(a) First msg + last summary (baseline)':<40} {n*2:>8} {2.0:>12.1f}")
        lines.append(f"  {'(b) + decisions + questions':<40} {n*2 + total_decisions + total_questions:>8} {(n*2 + total_decisions + total_questions)/n:>12.1f}")
        lines.append(f"  {'(c) + turning points (full system)':<40} {n*2 + total_decisions + total_questions + total_tp:>8} {(n*2 + total_decisions + total_questions + total_tp)/n:>12.1f}")
        lines.append("")
        lines.append(f"  Turning points breakdown:")
        lines.append(f"    Pivots (user redirections):      {total_pivots} ({total_pivots/n:.1f} per session)")
        lines.append(f"    Breakthroughs (discoveries):     {total_breakthroughs} ({total_breakthroughs/n:.1f} per session)")
        lines.append(f"    Total turning points:            {total_tp} ({total_tp/n:.1f} per session)")
        lines.append("")

        # Incremental value
        baseline_items = n * 2
        with_decisions = baseline_items + total_decisions + total_questions
        with_tp = with_decisions + total_tp
        if baseline_items > 0:
            lines.append(f"  Incremental extraction yield:")
            lines.append(f"    Decisions+questions add:         +{total_decisions + total_questions} items (+{(total_decisions + total_questions)/baseline_items*100:.0f}% over baseline)")
            lines.append(f"    Turning points add:              +{total_tp} items (+{total_tp/with_decisions*100:.0f}% over decisions)")
            lines.append(f"    Full system vs baseline:         +{with_tp - baseline_items} items (+{(with_tp - baseline_items)/baseline_items*100:.0f}% total)")
        lines.append("")

        # Per-session detail
        lines.append("  Per-session detail:")
        lines.append(f"  {'Session':<25} {'Msgs':>5} {'Dec':>5} {'Q':>5} {'Piv':>5} {'Brk':>5} {'TP':>5}")
        lines.append(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
        for r in clone_results:
            total = r["user_msgs"] + r["assistant_msgs"]
            tp = r["pivots"] + r["breakthroughs"]
            lines.append(f"  {r['file'][:25]:<25} {total:>5} {r['decisions']:>5} {r['questions']:>5} {r['pivots']:>5} {r['breakthroughs']:>5} {tp:>5}")

    lines.append("")
    return "\n".join(lines)


def main():
    init_db()

    print("Discovering data...")
    projects = list_projects()
    session_files = []
    for p in projects:
        for f in list_session_files(p["encoded_path"]):
            session_files.append({
                "path": f,
                "project": p["encoded_path"],
                "size": f.stat().st_size,
            })
    print(f"  Found {len(session_files)} sessions")

    print("\nRunning gate tier ablation...")
    gate_results, hash_savings, n_files, total_bytes = ablation_gate_tiers(session_files)

    print("Running clone extraction ablation...")
    clone_results = ablation_clone_extraction(session_files)

    report = format_ablation(gate_results, hash_savings, n_files, total_bytes, clone_results)
    print("\n" + report)

    output_path = Path(__file__).parent / "benchmark_ablation_results.txt"
    output_path.write_text(report, encoding="utf-8")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
