# Variety Engineering: Content Hashing as Inter-Layer Control in AI Session Memory

**Authors:** Palle Torsson[^1]
**Date:** April 2026
**Repository:** github.com/palletorsson/claude-context-manager

[^1]: With assistance from Claude (Anthropic). The AI contributed to code implementation and paper drafting but does not meet authorship criteria under standard academic norms.

## Abstract

Long-running AI coding sessions generate unbounded entropy. Each session produces messages, decisions, tool invocations, and file modifications that accumulate as unstructured JSONL logs. Without active regulation, the cost of managing this context exceeds the value of having it. We apply Ashby's Law of Requisite Variety to design a memory management system that uses content hashing as a control function between system layers, memory temperature classification for prioritization, and turning-point extraction for capturing mid-session meaning shifts. We evaluate the system on a real-world corpus of 2,434 sessions (1.0 GB) across 13 projects, showing that the three-tier hash gate achieves a 99.96% cache hit rate on warm paths with 83% computation reduction on session indexing. The system is implemented as open-source software and has been in daily use for three months.

## 1. Introduction

AI coding assistants such as Claude Code, GitHub Copilot, and Cursor generate persistent session logs as a side effect of their operation. A developer working with Claude Code for several months may accumulate hundreds of sessions across multiple projects, each recorded as a JSONL file of 10 to 50,000+ events. These logs contain valuable information — architectural decisions, debugging breakthroughs, abandoned approaches — but their volume makes them impractical to search manually.

The problem is one of **variety management**. In cybernetic terms (Ashby, 1956), the variety of the session corpus (the number of distinguishable states across all sessions) grows with every new interaction, while the developer's capacity to regulate that variety remains bounded by attention, time, and the AI's context window. When environmental variety exceeds regulatory capacity, the system fails to maintain useful organization. We call this the **variety trap**.

This paper presents Claude Context Manager, a system that applies Ashby's Law of Requisite Variety to tame session entropy through three mechanisms:

1. **Content hashing at layer boundaries** — a maximal variety attenuator that reduces arbitrary file content to a 1-bit control signal ("changed" / "not changed")
2. **Memory temperature classification** — a multi-signal scoring system that prioritizes memories by recency, connectivity, and importance
3. **Turning-point extraction** — a heuristic method for identifying mid-session pivots, breakthroughs, and root-cause discoveries during clone-to-thread operations

We evaluate these mechanisms on a real-world corpus and report cache hit rates, computation savings, and qualitative observations from three months of daily use.

## 2. Related Work

### 2.1 LLM Memory and Context Management

The challenge of maintaining persistent memory across LLM interactions has received growing attention. **MemGPT** (Packer et al., 2023) introduces a virtual memory hierarchy inspired by operating systems, allowing LLMs to manage their own context through explicit memory read/write operations. Our approach differs in operating *outside* the LLM's context window: rather than having the model manage its own memory during inference, we provide a separate tool for the developer to browse and curate session history.

**Zep** (Zep AI, 2024) provides a memory layer for LLM applications with automatic summarization and entity extraction. Unlike Zep, our system avoids LLM-based processing entirely, relying on lightweight heuristics (keyword matching, TF-IDF, Jaccard clustering) to keep the system dependency-free and fast.

**ChatGPT Memory** (OpenAI, 2024) allows the model to persist facts across conversations. This is complementary to our approach: ChatGPT Memory stores what the model *decides* to remember, while our system preserves the full session record and lets the developer decide what matters.

**LangChain** (Chase, 2022) and **LlamaIndex** (Liu, 2022) provide programmatic abstractions for conversation memory (buffer, summary, entity memory), but focus on runtime context management within a single application rather than cross-session corpus management.

### 2.2 Retrieval-Augmented Generation

RAG systems (Lewis et al., 2020) retrieve relevant documents at inference time to augment LLM context. Gao et al. (2024) survey the landscape of RAG approaches including chunking strategies and retrieval methods. Our memory temperature system can be viewed as a pre-filtering step for future RAG integration: hot memories would be candidates for automatic injection, while frozen memories would be excluded. However, our current system does not perform RAG — it provides a browsing and curation interface rather than automated retrieval.

**MemoryBank** (Zhong et al., 2024) enhances LLMs with long-term memory using an Ebbinghaus forgetting curve for memory decay. Our temperature scoring serves a similar purpose but uses a multi-dimensional signal (recency, connectivity, importance) rather than a single temporal decay function, and draws from cybernetics rather than cognitive psychology.

Wang et al. (2024) survey LLM-based autonomous agents including their memory architectures, categorizing memory into sensory, short-term, and long-term. Our system operates as a "meta-memory" layer — it manages the outputs of agent sessions rather than functioning as an agent memory module itself.

### 2.3 Developer Session Management

IDE session persistence (e.g., VS Code workspaces, JetBrains project state) preserves editor state but not the reasoning behind code changes. Git history preserves *what* changed but not *why*. Codoban et al. (2015) found that developers frequently need the "why" behind changes, not just the diffs. Our system fills this gap by preserving the conversational context in which decisions were made.

Fritz and Murphy (2010) introduced the concept of "information fragments" — pieces of knowledge scattered across tools that developers need to reconstruct context. Our session metadata, thread files, and context branches serve exactly this role for AI-assisted development. Murphy et al. (2006) documented the context-switching problem in IDE usage; our clone-to-thread feature directly addresses task resumption across AI coding sessions.

**Cursor** (Anysphere, 2024) maintains project-level context for its AI features but does not expose session history for browsing or curation. **Continue.dev** (Continue, 2024) stores conversation history locally but provides no indexing, search, or classification.

### 2.4 Cybernetics in Software Systems

Ashby's Law of Requisite Variety (1956) has been applied to software architecture (Bider & Jalali, 2016), organizational design (Beer, 1979; Espejo & Reyes, 2011), and sociotechnical systems (Boisot & McKelvey, 2011). Our contribution is a concrete application to AI session memory management, demonstrating that variety-theoretic thinking produces measurable efficiency gains in a practical system.

Shannon's channel capacity theorem (1948) provides a complementary frame: the AI's context window is a noisy channel with fixed bandwidth, and memory temperature provides a principled basis for relevance filtering when injecting context.

## 3. System Design

### 3.1 Architecture Overview

Claude Context Manager is a web application with a Python/FastAPI backend and Next.js frontend. It reads Claude Code's session logs (JSONL files in `~/.claude/projects/`) in read-only mode and maintains a SQLite cache database for indexed metadata.

```
Session JSONL files (raw data layer)
        |
        | content_hash gate (Tier 2)
        v
Session Index (cache.db) -----> Concept reference counts
        |                        (cross-session amplifier)
        | sessions_hash gate
        v
Topic Clusters (topic_cache) --> Memory Temperature
        |                        (hot/warm/cold/frozen)
        | file_hash gate
        v
Memory Files (curated layer) --> Dashboard + API
```

### 3.2 Three-Tier Hash Gate

The central efficiency mechanism is a three-tier gate that prevents redundant computation when session files have not changed:

**Tier 1: Mtime fast-path (O(1)).** Compare the file's filesystem modification time against the cached value. If unchanged within 1 second tolerance, skip entirely. This handles the common case of repeated API requests against stable files.

**Tier 2: Hash comparison (O(file\_size)).** If mtime differs (e.g., the file was copied, backed up, or touched), compute a SHA-256 hash and compare against the cached hash. If content is identical, update only the cached mtime and skip re-indexing.

**Tier 3: Full re-index (O(file\_size + events)).** Only reached when file content has actually changed. Stream the JSONL file, extract metadata (message counts, timestamps, tools used, first/last messages), compute classification and importance score, and update the cache.

The key insight is that the hash creates a **channel carrying exactly 1 bit of information** — "changed" or "not changed" — which is the minimum variety needed for the control decision of whether to re-index.

### 3.3 Memory Temperature

Not all memories are equally relevant. Temperature provides a single-axis summary computed from three signals:

```
score = recency_decay + connectivity + importance

where:
  recency_decay = max(0, 40 - days_since_reference × 1.5)    [0-40]
  connectivity  = min(30, reference_count × 3)                 [0-30]
  importance    = min(30, raw_importance × 0.3)                 [0-30]
```

The score (0-100) maps to four temperature labels:
- **Hot** (≥75 or ≤7 days): actively relevant, candidate for context injection
- **Warm** (≥40 or ≤30 days): recently relevant, worth scanning
- **Cold** (≥15 or ≤60 days): aging, review before relying on
- **Frozen** (<15): candidate for archival

This reduces the multi-dimensional state of a memory (content, age, references, importance) to four categories — variety attenuation from continuous space to a manageable taxonomy.

### 3.4 Session Classification and Importance Scoring

Sessions are auto-classified into four categories:
- **Major**: ≥200 messages or ≥1 MB, representing deep work sessions
- **Standard**: typical interactive sessions
- **Minor**: ≤2 user messages and ≤6 total, quick questions
- **Automated**: batch jobs detected by known prompt patterns

Importance scoring (0-100) combines five signals: message volume (0-30), user engagement (0-20), tool diversity (0-15), file operations (0-10), and file size (0-10), with bonuses for continuation sessions and penalties for automated/minor sessions.

### 3.5 Turning-Point Extraction

When cloning a session into a resumable thread file, the system extracts not just the first user message and last assistant summary, but also **turning points** — moments where understanding shifts mid-session. Two types are detected:

**Pivots** are identified from user messages after the first few exchanges, using markers such as "actually,", "scratch that", "instead,", "let's change", and "different approach". These capture moments where the plan changed direction.

**Breakthroughs** are identified from assistant messages using markers such as "the issue was", "root cause", "found it", "that fixed it", and "turns out". These capture moments of discovery — the "aha" moments that are typically the most valuable information in a debugging session.

This heuristic approach has limitations (see Section 6), but it captures mid-session meaning shifts that pure first-message/last-summary extraction misses entirely.

### 3.6 Topic Clustering

Cross-session topic detection uses TF-IDF keyword extraction from session first messages, followed by Jaccard similarity clustering. Sessions with similarity above a threshold are grouped into suggested meta-threads. Results are cached by a composite hash of all session metadata, so the O(n²) Jaccard computation only runs when sessions are added or modified.

## 4. Theoretical Framework

### 4.1 Ashby's Law Applied

Ashby's Law of Requisite Variety (1956) states that a regulator must have at least as many response states as the disturbances it faces. In our system:

- **Disturbance variety**: the number of distinguishable states across all sessions (grows unboundedly with each new session, message, and tool call)
- **Regulatory capacity**: bounded by human attention (~5-10 sessions per sitting), context window (~200K tokens), and computation time

The three-tier hash gate is an **attenuator**: it reduces the incoming variety at each layer boundary. The content hash reduces arbitrary file content to 256 bits; the control decision reduces it further to 1 bit. Memory temperature reduces multi-dimensional state to four categories. Session classification reduces continuous metadata to four labels.

Concept reference counting and topic clustering serve as **amplifiers**: they increase regulatory capacity by surfacing cross-session patterns that no single session contains, enabling the developer to detect recurring themes without scanning each session individually.

### 4.2 Shannon's Channel Capacity

The AI's context window can be modeled as a noisy channel with fixed bandwidth (Shannon, 1948). When starting a new session, the developer must select which prior context to inject. Memory temperature provides a principled basis for this selection: hot memories maximize information density within the bandwidth constraint, while frozen memories represent noise that would waste channel capacity.

The hash gate itself is an information-theoretic construct: it compresses file content into the minimum entropy needed for the control decision. A SHA-256 hash has 256 bits of entropy, but the comparison yields only 1 bit — the theoretical minimum for a binary decision.

## 5. Evaluation

### 5.1 Dataset

We evaluate on a real-world corpus from three months of daily Claude Code usage:

| Metric | Value |
|--------|-------|
| Projects | 13 |
| Session files | 2,434 |
| Total corpus size | 1,015.3 MB |
| Smallest session | 1.5 KB |
| Largest session | 192.3 MB |
| Median session | 39.1 KB |
| Memory files | 14 |

### 5.2 Cache Hit Rates

On a warm cache (all sessions previously indexed), the three-tier gate was evaluated across all 2,434 sessions:

| Gate Tier | Count | Percentage |
|-----------|-------|-----------|
| Tier 1: Mtime match (O(1) skip) | 2,433 | 99.96% |
| Tier 2: Hash match (content same) | 0 | 0.00% |
| Tier 3: Full re-index (changed) | 1 | 0.04% |
| **Total computation avoided** | **2,433** | **99.96%** |

The Tier 2 (hash) gate shows 0% hits because the warm cache already has correct mtimes — the hash gate activates in scenarios where files are copied, backed up, or touched without content modification, which did not occur during this benchmark run.

### 5.3 Computation Savings

Benchmarks were run on the 20 largest session files (879.1 MB total) to measure the cost difference between cached and uncached paths:

| Subsystem | Uncached | Cached | Reduction |
|-----------|----------|--------|-----------|
| Session indexing (20 files, 879 MB) | 4,292 ms | 718 ms | **83%** |
| Topic clustering (4 projects) | 3.5 ms | 2.7 ms | 23% |
| Projects discovery | 0.06 ms | 0.03 ms | 54% |

**Session indexing** shows the largest absolute savings. Full JSONL parsing of the 20 largest files takes 4.3 seconds; hash-only verification takes 0.7 seconds. The median per-file time drops from 101.6 ms (full parse) to 15.5 ms (hash only) — a 6.5× speedup.

**Topic clustering** shows modest savings (23%) because the clustering itself is fast on this corpus size. The savings would increase with larger corpora where the O(n²) Jaccard computation dominates.

**Projects discovery** is already fast (0.06 ms) so the absolute savings are negligible, but the mtime cache prevents unnecessary directory traversal on high-frequency API calls.

### 5.4 Qualitative Observations

Over three months of daily use, we observed:

1. **Session rediscovery**: Previously forgotten sessions containing relevant decisions were surfaced through keyword search and topic clustering. Without the tool, these would have required manual scanning of JSONL files.

2. **Temperature as triage signal**: The hot/warm/cold/frozen classification provided an intuitive triage mechanism. Hot memories were reliably the ones needed for active work; frozen memories could be safely ignored.

3. **Clone utility**: The clone-to-thread feature was most useful for multi-day tasks that spanned multiple sessions. The turning-point extraction captured debugging breakthroughs that would have been lost in the middle of long transcripts.

4. **Classification accuracy**: The auto-classification (major/standard/minor/automated) correctly categorized sessions in informal review, though we did not perform a formal accuracy study.

## 6. Limitations

**Turning-point extraction is heuristic.** The keyword-based detection of pivots and breakthroughs produces false positives (e.g., "actually" used in non-pivot contexts) and false negatives (insights expressed without any marker keywords). An LLM-based extraction would likely achieve higher precision but would introduce a dependency on external inference and increase latency.

**No formal user study.** The qualitative observations (Section 5.4) are from a single-user deployment over three months. A controlled study with multiple developers would be needed to validate the system's utility more broadly.

**Temperature thresholds are hand-tuned.** The weights (0.4 recency, 0.3 connectivity, 0.3 importance) and thresholds (75/40/15) were chosen based on intuition and informal testing. A principled calibration study would strengthen the design.

**Topic clustering scales quadratically.** The Jaccard similarity computation is O(n²) in the number of sessions. While caching mitigates this on repeated queries, the initial computation could become slow for corpora with thousands of sessions per project.

**The evaluation corpus is from a single developer.** Session patterns, vocabulary, and usage intensity may differ across developers and organizations.

## 7. Future Work

**LLM-based summarization.** Replace heuristic extraction (first message, turning-point markers) with LLM-generated session summaries. This would improve clone quality at the cost of inference latency and external dependency.

**Automated context injection.** Use temperature to automatically select memories for injection into new sessions: hot memories always, warm memories when topic-relevant, cold/frozen never. This would close the loop from passive browsing to active context management.

**Contradiction detection.** With concept reference counting, sessions that make conflicting decisions about the same concept could be flagged. This is a variety amplifier: it surfaces information the developer needs to act on.

**MCP integration.** Expose the context manager as a Model Context Protocol server, allowing the AI assistant to query its own session history during conversations.

**Formal evaluation.** Conduct a multi-user study to validate temperature calibration, clone quality, and the system's impact on developer productivity and decision consistency across sessions.

## 8. Conclusion

We presented Claude Context Manager, a system that applies Ashby's Law of Requisite Variety to manage the growing entropy of AI coding session logs. The three-tier hash gate (mtime → content hash → full index) achieves 99.96% cache hit rates on warm paths and 83% computation reduction on session indexing across a real-world corpus of 2,434 sessions (1.0 GB). Memory temperature classification provides an intuitive triage mechanism, and turning-point extraction captures mid-session meaning shifts that first-message/last-summary approaches miss.

The core insight is that content hashing creates a minimal-variety control signal (1 bit: changed/not changed) at layer boundaries, enabling a system to maintain semantic fidelity while avoiding redundant computation. This principle — attenuate variety at boundaries, amplify regulatory capacity through caching and cross-referencing — is applicable beyond session management to any system that must maintain coherence across growing, loosely structured data.

The system is open-source (MIT license) and available at github.com/palletorsson/claude-context-manager.

## References

- Anysphere. (2024). Cursor: The AI-first code editor. https://cursor.sh
- Ashby, W.R. (1956). *An Introduction to Cybernetics*. Chapman & Hall.
- Bar-Yam, Y. et al. (2025). A Formal Definition of Scale-Dependent Complexity and the Multi-Scale Law of Requisite Variety. *Entropy*, 27(8), 835.
- Beer, S. (1979). *The Heart of Enterprise*. Wiley.
- Bider, I. & Jalali, A. (2016). Applying Ashby's Law of Requisite Variety to Software Systems. In *BIR 2016 Workshops*. CEUR-WS.
- Boisot, M. & McKelvey, B. (2011). Complexity and Organization-Environment Relations: Revisiting Ashby's Law of Requisite Variety. In *The SAGE Handbook of Complexity and Management*. SAGE Publications, 279-298.
- Chase, H. (2022). LangChain. https://github.com/langchain-ai/langchain
- Codoban, M., Jalali, S.S., Bird, C., Czerwonka, J., & Devanbu, P. (2015). Software History Under the Lens: A Study on Why and How Developers Examine It. *Proceedings of ICSME 2015*, IEEE, 1-10.
- Continue. (2024). Continue: Open-source AI code assistant. https://continue.dev
- Espejo, R. & Reyes, A. (2011). *Organizational Systems: Managing Complexity with the Viable System Model*. Springer.
- Fritz, T. & Murphy, G.C. (2010). Using Information Fragments to Answer the Questions Developers Ask. *Proceedings of ICSE 2010*, ACM, 175-184.
- Gao, Y. et al. (2024). Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*.
- Letta. (2024). Letta: The open-source framework for building stateful AI agents. https://github.com/letta-ai/letta
- Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*, 33, 9459-9474.
- Liu, J. (2022). LlamaIndex. https://github.com/run-llama/llama_index
- Murphy, G.C., Kersten, M., & Findlater, L. (2006). How Are Java Software Developers Using the Eclipse IDE? *IEEE Software*, 23(4), 76-83.
- OpenAI. (2024). Memory and new controls for ChatGPT. https://openai.com/blog/memory-and-new-controls-for-chatgpt
- Packer, C. et al. (2023). MemGPT: Towards LLMs as Operating Systems. *arXiv:2310.08560*.
- Shannon, C.E. (1948). A Mathematical Theory of Communication. *Bell System Technical Journal*, 27, 379-423.
- Wang, L. et al. (2024). A Survey on Large Language Model based Autonomous Agents. *Frontiers of Computer Science*, 18(6), 186345.
- Zhong, W. et al. (2024). MemoryBank: Enhancing Large Language Models with Long-Term Memory. *Proceedings of AAAI 2024*.
- Zep AI. (2024). Zep: Long-term memory for AI assistants. https://www.getzep.com

## Appendix A: Running Example

To make the system concrete, we trace a single session through the pipeline.

**Input.** A JSONL session file (847 KB, 312 events) from a debugging session where the developer asked Claude Code to investigate failing tests.

**Step 1: Indexing.** The JSONL is streamed. Extracted metadata:
- 42 user messages, 38 assistant messages (80 total)
- Tools used: Read, Edit, Bash, Grep (4 unique)
- Duration: 47 minutes
- Classification: **standard** (80 messages, interactive)
- Importance: **62.3** (high engagement, 4 tools, file operations)

**Step 2: Turning-point extraction** (during clone). Two turning points detected:
- `[pivot]` User message #28: "actually, the issue might not be in the test — check the migration script instead"
- `[breakthrough]` Assistant message #31: "Found it — the migration was using INTEGER instead of BIGINT, causing silent overflow on IDs above 2^31"

**Step 3: Cache behavior.** On the next API request (30 seconds later), the session's mtime has not changed → Tier 1 skip (O(1)). On the next day, a backup tool touches the file → mtime changes → Tier 2 hash comparison → content identical → skip re-index.

**Step 4: Temperature.** After being referenced in two subsequent sessions and cloned into a thread file: recency = 40 (referenced today), connectivity = 6 (2 references × 3), importance = 18.7 (62.3 × 0.3) → **score 64.7 → warm**.

## Appendix B: Test Coverage

The implementation includes 199 automated tests (2,111 lines of test code):
- 53 security tests (path traversal, SQL injection, input validation)
- 103 API and service tests (full CRUD on all endpoints)
- 32 variety engineering tests (hashing, temperature, caching, reference counting)
- 11 additional integration tests

All tests pass in under 2.4 seconds.
