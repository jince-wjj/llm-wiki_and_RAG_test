# Agent Instructions: 红楼梦 LLM-Wiki vs RAG 对比实验

> **READ THIS DOCUMENT IN FULL BEFORE TAKING ANY ACTION.**
> **DO NOT skip sections. DO NOT improvise beyond explicit instructions.**
> **You are Agent 1 (Builder & Runner). A separate Agent 2 will handle evaluation.**

---

## 0. Identity, Role, and Hard Constraints

You are an autonomous coding agent executing a controlled experiment comparing the LLM-Wiki paradigm against vanilla RAG on Chinese classical literature (《红楼梦》, Dream of the Red Chamber). Your role is **Builder & Runner**. You build the system, ingest data, generate benchmark, run both systems, and produce answer files. **You do NOT score answers** — that is Agent 2's job.

### Hard Constraints (violating any of these invalidates the experiment)

1. **Single working directory.** All work happens under the current directory. NEVER write outside it. NEVER touch system files.
2. **No silent improvisation.** If instructions are ambiguous OR you encounter unexpected state, STOP and write a question to `BLOCKERS.md` then halt that phase. Do not "do your best guess".
3. **All intermediate artifacts must be persisted to disk.** Every wiki page, every API call result, every benchmark question, every answer — must be a file. In-memory only state is forbidden.
4. **No data leakage between systems.** When the RAG baseline answers questions, it MUST NOT have access to wiki pages. When the wiki system answers, it MUST NOT have access to raw chunks. Enforce via separate code paths and separate inputs.
5. **No model swapping mid-run.** The model for ingest, the model for answering, and the model for benchmark generation MUST stay fixed throughout a phase. Record exact model IDs in `MANIFEST.json`.
6. **Checkpoint everything.** After every phase, write a checkpoint. After every batch of 10 ingests / 10 questions, write progress to disk. Resume from checkpoint on restart.
7. **Budget cap.** Track total API token usage in `usage.json`. If estimated cost exceeds **$15 USD**, STOP and write to `BLOCKERS.md`.
8. **Determinism where possible.** Use `temperature=0.0` for benchmark generation and answering. Use `temperature=0.3` only for wiki ingest (some creativity needed for synthesis).
9. **You are NOT to score answers, judge quality, or write the final report comparing systems.** That happens in a separate session by a separate agent reading the artifacts you produce.
10. **Git is enabled. You MUST commit at every phase boundary and at sub-checkpoints during long phases.** This gives the user a clean rollback history. NEVER `git push`, NEVER `git reset --hard`, NEVER `git rebase`, NEVER force-push, NEVER amend or reorder previous commits. See Section 4.5 for the full git protocol.

---

## 1. Tech Stack and Configuration

### 1.1 Models

| Purpose | Model | API |
|---|---|---|
| Wiki ingest (read source, write wiki pages) | `deepseek-chat` (DeepSeek-V3) | DeepSeek API |
| Wiki query (answer benchmark questions) | `deepseek-chat` | DeepSeek API |
| RAG baseline query (answer benchmark questions) | `deepseek-chat` | DeepSeek API |
| Benchmark question generation | `deepseek-chat` | DeepSeek API |
| Embedding (for RAG baseline and wiki search) | `BAAI/bge-m3` | SiliconFlow API |

**Why same model for wiki-query and rag-query**: ensures the comparison measures the *retrieval paradigm*, not the *generator*.

### 1.2 Environment Variables (.env)

The user will provide these. You MUST verify they exist before any API call.

```
DEEPSEEK_API_KEY=...
SILICONFLOW_API_KEY=...
```

API endpoints:
- DeepSeek: `https://api.deepseek.com/v1` (OpenAI-compatible)
- SiliconFlow: `https://api.siliconflow.cn/v1` (OpenAI-compatible)

### 1.3 Dependencies (Python 3.10+)

```
openai>=1.30
chromadb>=0.5
tiktoken
python-dotenv
tqdm
tenacity
numpy
jieba          # Chinese tokenization for chunking
```

Write `requirements.txt` and `pip install -r requirements.txt` before any code.

---

## 2. Directory Structure (MUST match exactly)

Create this structure FIRST, before any other work. Empty directories must contain a `.gitkeep`.

```
.
├── AGENT_INSTRUCTIONS.md           # this file (already exists)
├── MANIFEST.json                   # experiment metadata (models, versions, timestamps)
├── BLOCKERS.md                     # any questions/blockers for the human
├── PROGRESS.md                     # human-readable progress log, append-only
├── usage.json                      # API token usage tracking
├── checkpoints/                    # phase completion markers
├── .env.example                    # template for the user
├── requirements.txt
├── README.md                       # written LAST
│
├── raw/
│   ├── sources.csv                 # source inventory
│   ├── hongloumeng_full.txt        # 红楼梦 120回全本
│   └── chapters/                   # 120 individual chapter files: 001.txt ... 120.txt
│
├── wiki/                           # LLM-Wiki output
│   ├── index.md
│   ├── log.md
│   ├── 人物/
│   ├── 地点/
│   ├── 事件/
│   ├── 概念/
│   └── 综合/
│
├── benchmark/
│   ├── questions.json              # all 100 questions with metadata
│   ├── ground_truth.json           # reference answers + source chapter pointers
│   └── generation_log.md           # how each question was generated
│
├── rag_baseline/
│   ├── chunks.jsonl                # all chunks with metadata
│   ├── chroma_db/                  # ChromaDB persistent storage
│   └── README.md                   # describes the baseline implementation
│
├── src/
│   ├── config.py                   # loads .env, exposes clients
│   ├── api_client.py               # DeepSeek + SiliconFlow wrappers with retry
│   ├── data_prep.py                # download + split into chapters
│   ├── wiki_ingest.py              # main ingest loop
│   ├── wiki_query.py               # answer questions using wiki
│   ├── rag_ingest.py               # chunk + embed + store in Chroma
│   ├── rag_query.py                # answer questions using RAG
│   ├── benchmark_gen.py            # generate 100 questions
│   ├── run_experiment.py           # orchestrator
│   └── utils.py
│
└── results/
    ├── wiki_answers.json           # LLM-Wiki's answers to all questions
    ├── rag_answers.json            # RAG baseline's answers to all questions
    └── stats.json                  # latency, token usage, page counts per system
```

---

## 3. Execution Phases

You MUST execute phases in order. Each phase has an entry condition, actions, exit condition, and checkpoint file.

### Phase 0: Bootstrap

**Entry**: fresh repository.

**Actions**:
1. Create the full directory structure from Section 2.
2. Write `requirements.txt`.
3. Write `.env.example` with the two required keys (empty values).
4. Write `MANIFEST.json` with:
   ```json
   {
     "experiment_name": "hongloumeng-wiki-vs-rag",
     "agent_role": "builder_runner",
     "started_at": "<ISO timestamp>",
     "models": {
       "ingest": "deepseek-chat",
       "answer": "deepseek-chat",
       "benchmark_gen": "deepseek-chat",
       "embedding": "BAAI/bge-m3"
     },
     "data_scope": "前80回",
     "rag_baseline": "naive_chunk_embed_topk",
     "phases_completed": []
   }
   ```
5. Initialize `usage.json` with `{"total_input_tokens": 0, "total_output_tokens": 0, "estimated_cost_usd": 0.0, "calls": 0}`.
6. Initialize `PROGRESS.md` with a header and the bootstrap timestamp.
7. **Create `.gitignore`** with at minimum these entries (one per line):
   ```
   .env
   __pycache__/
   *.pyc
   .DS_Store
   rag_baseline/chroma_db/
   wiki/.ingest_logs/
   *.swp
   .venv/
   venv/
   ```
   Rationale: `.env` contains secrets and MUST NEVER be committed. ChromaDB binary files and raw ingest logs are large and noisy — they're regeneratable from raw data and wiki pages, so excluding them keeps commits clean. The wiki pages themselves ARE committed (they're the main artifact).
8. **Verify git is initialized**: run `git status`. If not a git repo, write to BLOCKERS.md and STOP (the user said they initialized git; if missing, something is wrong with the environment).
9. **First commit**: run `git add -A` then verify `.env` is NOT in the staged files (run `git diff --cached --name-only | grep -F .env` — must be empty). Then `git commit -m "phase0: bootstrap directory structure and config templates"`.

**Exit**: structure exists, dependencies declared, git has one commit. Write `checkpoints/phase0_done`.

**STOP here and wait for user.** Tell the user in chat:
> "Bootstrap complete. I need you to do two things:
> 1. Copy `.env.example` to `.env` and fill in `DEEPSEEK_API_KEY` and `SILICONFLOW_API_KEY`.
> 2. Run `pip install -r requirements.txt` in this directory.
> Then tell me to continue."

DO NOT proceed to Phase 1 until the user confirms.

---

### Phase 1: Data Acquisition

**Entry**: Phase 0 checkpoint exists, `.env` populated, dependencies installed.

**Actions**:

1. **Verify environment**: load `.env`, ping DeepSeek with a 1-token request, ping SiliconFlow with a single embedding. If either fails, write the failure to `BLOCKERS.md` and STOP.

2. **Download 红楼梦 120回全本**: this is your responsibility, NOT the user's. Strategy:
   - Primary source: search GitHub for "红楼梦 txt" repositories. Try in order:
     - `https://raw.githubusercontent.com/NaiboWang/Chinese-Classical-Novels/master/红楼梦.txt`
     - `https://raw.githubusercontent.com/javayhu/chinese-classics/main/红楼梦.txt`
     - GitHub API search: `https://api.github.com/search/code?q=红楼梦+filename:红楼梦.txt`
   - Secondary source: Project Gutenberg `https://www.gutenberg.org/cache/epub/24264/pg24264.txt` (this is Chinese, verify encoding)
   - Tertiary: any other reachable mirror

   If ALL fail, write to `BLOCKERS.md` with the URLs you tried and ask the user to provide the file at `raw/hongloumeng_full.txt`.

3. **Validate the downloaded text**:
   - File must be UTF-8 (re-encode if necessary, log original encoding)
   - Total length must be between 700,000 and 1,000,000 characters
   - Must contain string "第一回" and "第八十回" (we're using 前80回)
   - Must contain at least 5 of these character names: 贾宝玉, 林黛玉, 薛宝钗, 王熙凤, 贾母, 贾政, 史湘云, 妙玉

   If any validation fails, log to `BLOCKERS.md` and STOP.

4. **Split into chapters**: write a parser that splits on chapter markers (typically "第X回" where X is a Chinese numeral). Output `raw/chapters/001.txt` through `raw/chapters/080.txt`. **Use only 前80回 (chapters 1-80) for this experiment.** If the source has 120 chapters, discard 81-120.

5. **Write `raw/sources.csv`** with columns: `chapter_id, title, char_count, file_path`.

**Exit**: 80 chapter files exist, each between 5,000 and 20,000 characters. Write `checkpoints/phase1_done` with summary stats. Append progress to `PROGRESS.md`. Then `git add -A && git commit -m "phase1: acquired and split 红楼梦 前80回 into chapter files"`.

---

### Phase 2: Benchmark Generation

**Entry**: Phase 1 done.

**Actions**:

Generate exactly **100 questions** with this distribution:

| Tier | Count | Description | What it tests |
|---|---|---|---|
| Tier 1: Single-fact | 30 | Answer in a single chapter, single sentence | Both systems should ace |
| Tier 2: Single-source synthesis | 30 | Answer requires synthesizing within one chapter | RAG starts to struggle |
| Tier 3: Cross-source synthesis | 25 | Answer requires combining info from 2-5 chapters | LLM-Wiki should win |
| Tier 4: Conflict / contradiction | 15 | Answer requires recognizing inconsistencies or comparing portrayals across chapters | LLM-Wiki should dominate |

**Generation Protocol (CRITICAL — anti-cheat measures)**:

1. For each tier, generate questions in batches of 5. Per batch:
   - Sample relevant chapters (Tier 1: 1 chapter; Tier 2: 1 chapter; Tier 3: 2-5 chapters; Tier 4: 2-5 chapters with known thematic tension).
   - Send sampled chapter text to DeepSeek with a strict prompt (see below).
   - Receive JSON with question, ground_truth_answer, source_chapter_ids, and a confidence score.
   - Validate: question must be answerable from the cited chapters, ground truth must not exceed 200 characters.

2. **Strict generation prompt template** (use verbatim, substitute `{TIER_DESCRIPTION}` and `{CHAPTERS}`):

   ```
   你是一名严谨的红楼梦研究者。任务是基于提供的章节内容,生成5道高质量的中文问答题。

   题目类型: {TIER_DESCRIPTION}

   严格要求:
   1. 每道题的答案必须**完全**能从提供的章节内容中得到,不允许引入外部知识(包括续作、其他抄本、现代解读)。
   2. 答案不超过200字。
   3. 问题表述清晰、具体、无歧义。
   4. 必须能找到 ground truth 在原文中的精确依据(指出是哪一回的哪一段)。
   5. 输出严格的 JSON 格式,无任何额外文字。

   提供的章节内容:
   {CHAPTERS}

   输出格式:
   {
     "questions": [
       {
         "question": "...",
         "ground_truth": "...",
         "source_chapter_ids": [1, 3, 5],
         "source_evidence": "原文片段或概述",
         "tier": "...",
         "confidence": 0.0-1.0
       }
     ]
   }
   ```

3. **Self-validation**: after generation, send each question + ground truth back to DeepSeek in a SEPARATE call and ask: "Given only the cited chapters, is this answer accurate and complete? Reply YES or NO." Drop any question that fails. If you have fewer than 100 questions after validation, generate more in the under-filled tier.

4. **Write outputs**:
   - `benchmark/questions.json`: array of 100 question objects (without ground truth) — this is what gets fed to systems being tested.
   - `benchmark/ground_truth.json`: parallel array of 100 ground truth objects with answers and evidence.
   - `benchmark/generation_log.md`: human-readable log of how questions were generated, which chapters were used, dropouts, retries.

**Quality bar**: minimum confidence 0.8 after self-validation. Re-generate any question that doesn't meet this.

**Exit**: 100 questions exist, distribution matches. Write `checkpoints/phase2_done`. Then `git add -A && git commit -m "phase2: generated 100-question benchmark across 4 tiers"`.

---

### Phase 3: LLM-Wiki Ingest

**Entry**: Phase 2 done.

**Actions**:

1. **Write `CLAUDE.md` in the project root** (this is the wiki schema, used by the ingest agent to know how to write pages). The content is below — write it verbatim:

   ```markdown
   # 红楼梦 LLM-Wiki Schema

   This is a Chinese literature LLM-Wiki for 《红楼梦》 (Dream of the Red Chamber), first 80 chapters.

   ## Page Types

   ### 人物 (Characters) — `wiki/人物/<name>.md`
   Required sections:
   - `## 基本信息`: 姓名, 别名/字号, 身份, 家族关系
   - `## 出场章节`: list of chapter IDs where this character appears with brief context
   - `## 性格特征`: synthesized from multiple chapters, with citations `[第X回]`
   - `## 关键事件`: bullets, each linking to events `[[事件/...]]`
   - `## 与其他人物的关系`: links to other character pages `[[人物/...]]`
   - `## 内在矛盾或多面性`: explicit note when portrayals differ across chapters

   ### 地点 (Locations) — `wiki/地点/<name>.md`
   - `## 描述`
   - `## 关联人物`: links
   - `## 关联事件`: links
   - `## 出现章节`

   ### 事件 (Events) — `wiki/事件/<name>.md`
   - `## 时间`: chapter number(s)
   - `## 参与人物`: links
   - `## 发生地点`: links
   - `## 事件经过`: concise narrative with citations
   - `## 意义/影响`: link to related events

   ### 概念 (Concepts) — `wiki/概念/<name>.md`
   For abstract concepts like 判词, 金陵十二钗, 元宵, 太虚幻境.
   - `## 定义`
   - `## 原文出处`
   - `## 关联人物/事件`

   ### 综合 (Synthesis) — `wiki/综合/<topic>.md`
   Created in response to user queries that span multiple entities. Required sections:
   - `## 综合论点`
   - `## 支撑证据`: numbered list with `[第X回]` citations
   - `## 涉及实体`: links to other wiki pages

   ## Page Conventions

   1. **All wiki pages are Markdown with YAML frontmatter**:
      ```yaml
      ---
      type: 人物 | 地点 | 事件 | 概念 | 综合
      name: <canonical name>
      aliases: [<list of alternative names>]
      first_appearance: <chapter id>
      source_count: <number of source chapters cited>
      last_updated: <ISO timestamp>
      ---
      ```

   2. **Wiki-links use double brackets**: `[[人物/林黛玉]]`. Always use the canonical name + relative path.

   3. **Every factual claim cites a chapter**: `[第三回]` immediately after the claim.

   4. **Contradictions are explicit**: when ingesting a new source that contradicts existing content, do NOT overwrite. Add a `## 矛盾记录` section listing both versions with chapter citations.

   5. **Synthesis pages are created sparingly** — only when explicitly requested or when 3+ entity pages cluster around a common theme.

   ## Index and Log

   - `wiki/index.md` is updated after each ingest with new pages added.
   - `wiki/log.md` is append-only. Every ingest writes a line:
     `## [<ISO timestamp>] ingest | chapter 第X回 | pages touched: N`
   ```

2. **Run ingest** by iterating chapters 1 through 80 in order. For each chapter:

   - Read the chapter text from `raw/chapters/XXX.txt`.
   - Send to DeepSeek with the ingest prompt (below).
   - Receive a JSON action plan listing pages to create or update.
   - Apply the action plan: create/update Markdown files in `wiki/`.
   - Append to `wiki/log.md`.
   - Update `wiki/index.md` after every 10 chapters (not every chapter, to save tokens).
   - Write checkpoint `checkpoints/phase3_ch<XXX>.json` after each chapter.
   - **Git sub-commit every 10 chapters**: after chapters 10, 20, 30, ..., 80, run `git add -A && git commit -m "phase3: ingested chapters NN-MM"` (e.g., "phase3: ingested chapters 1-10"). Do NOT commit after every chapter (too noisy). Do NOT skip sub-commits (loss of rollback granularity).

3. **Ingest prompt template**:

   ```
   你是红楼梦 wiki 的维护者。任务是阅读一回内容,然后产出一个"页面操作计划"。

   当前 wiki 状态(已存在的页面列表):
   {EXISTING_PAGES_LIST}

   本次要 ingest 的章节内容:
   第{N}回:
   {CHAPTER_TEXT}

   严格要求:
   1. 识别出本回中的主要人物、地点、事件、概念。
   2. 对每个实体,决定是 CREATE 新页面还是 UPDATE 已有页面。
   3. UPDATE 时,如果新信息与已有内容矛盾,记录到该页面的 `## 矛盾记录` section,不覆盖。
   4. 不要对未在本回出现的实体做任何操作。
   5. 输出严格 JSON。

   输出格式:
   {
     "actions": [
       {
         "operation": "CREATE" | "UPDATE",
         "page_path": "人物/林黛玉.md",
         "page_type": "人物",
         "content_markdown": "完整 Markdown 内容(CREATE) 或 增量 patch(UPDATE)",
         "patch_strategy": "append_section" | "merge_section" | "add_contradiction",
         "reason": "为什么这么操作"
       }
     ]
   }
   ```

4. **Limits per chapter**:
   - Maximum 20 page operations per chapter (CREATE + UPDATE combined).
   - If model returns more, take top 20 by stated importance.
   - Maximum 30,000 input tokens per ingest call. If chapter + existing pages list exceeds this, truncate the existing pages list to just titles + frontmatter.

5. **Save raw ingest responses** to `wiki/.ingest_logs/ch<XXX>.json` for debuggability.

**Exit**: all 80 chapters ingested. `wiki/` has all expected page types. `wiki/index.md` is comprehensive. Write `checkpoints/phase3_done` with page counts per type. Then `git add -A && git commit -m "phase3: complete wiki ingest of 前80回 (N pages)"` where N is the total page count.

---

### Phase 4: RAG Baseline Build

**Entry**: Phase 3 done.

**Actions**:

This is the **vanilla RAG baseline** for comparison. Keep it simple — do NOT add bells and whistles. The point is to show the difference between a naive RAG and LLM-Wiki, not to engineer the best RAG.

1. **Chunking**:
   - Split each chapter into chunks of approximately 500 Chinese characters.
   - Use sliding window with 100-character overlap.
   - Each chunk gets metadata: `{chunk_id, chapter_id, position, char_count}`.
   - Save all chunks to `rag_baseline/chunks.jsonl`.

2. **Embedding**:
   - Embed each chunk with `BAAI/bge-m3` via SiliconFlow.
   - Batch size 16. Retry on failure with exponential backoff.
   - Store in ChromaDB at `rag_baseline/chroma_db/`.

3. **Verification**:
   - Number of chunks should be approximately 1500-2500.
   - Test retrieval with one query "林黛玉的性格是怎样的" and confirm top-5 returns relevant chunks.
   - Log results to `rag_baseline/README.md`.

**Exit**: ChromaDB populated, retrieval works. Write `checkpoints/phase4_done`. Then `git add -A && git commit -m "phase4: built RAG baseline (N chunks indexed)"`. Note: ChromaDB binary files are excluded by `.gitignore` — only the chunk metadata (`chunks.jsonl`) and code/README are committed.

---

### Phase 5: Answer Generation — Both Systems

**Entry**: Phases 3 and 4 done.

**Actions**:

Answer all 100 questions with BOTH systems. **Use exactly the same prompt structure for both** — only the retrieval mechanism differs.

#### 5.1 RAG Baseline Answer Pipeline

For each question in `benchmark/questions.json`:

1. Embed the question with BGE-M3.
2. Retrieve top-5 chunks from ChromaDB.
3. Construct prompt:
   ```
   你是红楼梦研究者。根据以下原文片段回答问题。如果片段不足以回答,如实说"原文未提供足够信息"。

   原文片段:
   [片段1, 来自第X回]
   ...
   [片段5, 来自第Y回]

   问题: {QUESTION}

   答案(不超过200字):
   ```
4. Call DeepSeek with `temperature=0.0`, `max_tokens=400`.
5. Record: answer, retrieved_chunk_ids, latency_ms, tokens_used.

Output: `results/rag_answers.json` as array of `{question_id, question, answer, retrieved_chunk_ids, latency_ms, input_tokens, output_tokens}`.

#### 5.2 LLM-Wiki Answer Pipeline

For each question:

1. **Wiki search**: this is more complex than RAG retrieval. The wiki has structured pages. Implementation:
   - First, extract candidate entities from the question (people names, locations, concepts) using a simple LLM call.
   - For each candidate entity, look up its wiki page.
   - Additionally, do BGE-M3 vector search over wiki page frontmatter + first 500 chars of each page (build this index once at start of phase 5).
   - Combine results: dedupe by page path, take top-5 pages.

2. Construct prompt:
   ```
   你是红楼梦研究者。根据以下结构化 wiki 页面回答问题。如果页面不足以回答,如实说"wiki 未提供足够信息"。

   Wiki 页面:
   --- 页面: 人物/林黛玉.md ---
   {FULL_PAGE_CONTENT}
   --- 页面: 事件/葬花.md ---
   {FULL_PAGE_CONTENT}
   ...

   问题: {QUESTION}

   答案(不超过200字):
   ```

3. Call DeepSeek with `temperature=0.0`, `max_tokens=400`.
4. Record: answer, retrieved_page_paths, latency_ms, tokens_used.

Output: `results/wiki_answers.json` as array of `{question_id, question, answer, retrieved_page_paths, latency_ms, input_tokens, output_tokens}`.

#### 5.3 Concurrency

Process questions sequentially (not in parallel) to keep API usage predictable and stay within rate limits. ~3 seconds per question × 100 questions × 2 systems = ~10 minutes per system. Acceptable.

#### 5.4 Validation

- Both answer files must have exactly 100 entries.
- No entry may have an empty answer (re-run failed ones with up to 3 retries).
- `results/stats.json` must contain aggregate stats: total tokens per system, total latency, average answer length.

**Exit**: both answer files exist with 100 entries each. Write `checkpoints/phase5_done`. Then `git add -A && git commit -m "phase5: generated answers from both systems on 100-question benchmark"`.

---

### Phase 6: Handoff to Agent 2

**Entry**: Phase 5 done.

**Actions**:

1. Write `HANDOFF.md` at the project root. Content:

   ```markdown
   # Handoff to Evaluation Agent (Agent 2)

   ## What was done
   - 红楼梦 前80回 ingested as LLM-Wiki with schema in `CLAUDE.md`.
   - Same 80 chapters chunked + embedded as RAG baseline.
   - 100 benchmark questions across 4 tiers in `benchmark/questions.json`.
   - Ground truth in `benchmark/ground_truth.json`.
   - LLM-Wiki answers in `results/wiki_answers.json`.
   - RAG baseline answers in `results/rag_answers.json`.

   ## What you need to do
   1. Read `EVALUATION_INSTRUCTIONS.md` (provided separately by the user).
   2. Score every answer in both files against ground truth.
   3. Compute aggregate metrics broken down by tier.
   4. Generate the final comparison report.

   ## Critical constraints for evaluation
   - You MUST use a DIFFERENT model from the one that generated answers (deepseek-chat). Recommended: claude-opus-4-7 or gpt-5.
   - You MUST score blind to system source — randomize order, hide which system produced which answer until aggregation.
   - You MUST NOT modify any file in `wiki/`, `rag_baseline/`, `results/`, `benchmark/` except to append to logs.
   - Output your evaluation to `evaluation/` directory.

   ## Files Agent 2 should produce
   - `evaluation/scores.json`: per-question scores for both systems.
   - `evaluation/final_report.md`: aggregate comparison, per-tier breakdown, notable observations.
   ```

2. Write final `README.md` at project root summarizing what's in each directory and how to inspect results.

3. Update `MANIFEST.json` `phases_completed` to include all phases.

4. Update `PROGRESS.md` with completion timestamp and a one-paragraph summary.

5. Print final status to chat:
   > "All phases complete. Answer files generated. Awaiting Agent 2 for evaluation. See `HANDOFF.md`."

6. **Final commit**: `git add -A && git commit -m "phase6: handoff package ready for Agent 2 evaluation"`.

DO NOT score answers yourself. DO NOT speculate on which system performed better.

---

## 4. Error Handling and Recovery

### 4.1 API Failures

Wrap all API calls in `tenacity.retry` with:
- 3 retries
- exponential backoff (initial 2s, max 60s)
- retry on: network errors, 429, 500, 502, 503, 504
- do NOT retry on: 400, 401, 403 (these are config errors — STOP and write to BLOCKERS.md)

### 4.2 Resume from Checkpoint

On startup, the script must:
1. Read `checkpoints/` directory.
2. Determine the last completed phase.
3. Resume from the next phase.
4. Within a phase, check for sub-checkpoints (e.g. `phase3_ch045.json`) and resume from there.

### 4.3 Budget Tripwire

After every API call, update `usage.json`. Estimate cost using:
- DeepSeek-V3: $0.27 per 1M input tokens, $1.10 per 1M output tokens
- SiliconFlow BGE-M3: free tier (assume 0 cost, log token counts only)

If `estimated_cost_usd` exceeds **$15**, STOP and write to BLOCKERS.md:
```
BUDGET CAP HIT
Estimated cost: $X.XX
Last completed phase: phaseN
Awaiting user authorization to continue.
```

### 4.4 Anomaly Logs

Anything unexpected (empty model response, truncated JSON, invalid character in output, surprising page count) gets logged to `PROGRESS.md` with timestamp. Continue if recoverable, BLOCKER if not.

### 4.5 Git Commit Protocol

The user has initialized a git repo for this project specifically to enable phase-level rollback. Treat git as a safety net, not a feature to extend.

#### What you DO

- Commit at **every phase boundary** (after each phase's exit condition is met).
- Commit at **sub-checkpoints during Phase 3** (every 10 chapters), since Phase 3 is the longest phase.
- Use the **commit message format**: `phase{N}: <short description>` — this lets the user run `git log --oneline` and immediately see phase progression, and `git revert <hash>` or `git reset --hard <hash>` to roll back cleanly.
- Run `git add -A` to stage all changes, then `git commit -m "..."`. Do not use `git add` with specific paths — staging all changes preserves the "phase snapshot" property of each commit.
- **Before EVERY `git add`, verify `.env` is not being staged**:
  ```bash
  git diff --cached --name-only | grep -F ".env" && echo "DANGER: .env is staged, ABORT" || echo "safe"
  ```
  If `.env` appears, abort immediately, write to BLOCKERS.md, do not commit.

#### What you do NOT do

- **NEVER `git push`.** The user has not specified a remote, and committing to remote is out of scope.
- **NEVER `git reset --hard`** or `git reset` with destructive flags. The user controls rollbacks, not you.
- **NEVER `git rebase`, `git rebase -i`, `git commit --amend`, or any history-rewriting operation.** Commits are immutable once made.
- **NEVER force-push** (`git push -f`, `git push --force`).
- **NEVER create branches** (`git checkout -b`, `git switch -c`). Work only on the default branch.
- **NEVER merge** or `git cherry-pick`. You don't have multiple branches, so this shouldn't come up — listed for completeness.
- **NEVER modify `.git/` directly** (the directory).
- **NEVER `git config --global`** or change git identity. If commit fails because git user.name/user.email is unset, write to BLOCKERS.md and ask the user to configure it.

#### When a commit fails

If `git commit` returns non-zero (e.g., "nothing to commit", "user not configured", merge conflict from external changes), do NOT improvise. Log the exact error to `PROGRESS.md` and `BLOCKERS.md`, and continue with the next phase ONLY if the failure is "nothing to commit" (harmless). Any other failure: STOP and wait for user.

#### Rationale for the user

By following this protocol, the user gets:
- Clean `git log --oneline` showing exactly which phase produced which state
- Ability to `git diff phase3..phase5` to see what an entire phase changed
- Ability to roll back to any phase with `git reset --hard <hash>` (their decision, not yours)
- Guaranteed `.env` never enters version control
- No surprise rewrites of history

---

## 5. Things You Must NOT Do

This is the explicit "don't" list. Violating any item means re-running.

1. **Do NOT score answers.** That is Agent 2's job. You may not write evaluation logic or quality assessments.
2. **Do NOT modify the schema (`CLAUDE.md`) after Phase 3 begins.** If you find it's wrong, write to BLOCKERS.md.
3. **Do NOT use a different model for wiki-query vs rag-query.** They must be identical.
4. **Do NOT give the RAG baseline access to wiki pages.** Its inputs are chunks only.
5. **Do NOT give the wiki system access to raw chunks.** Its inputs are wiki pages only.
6. **Do NOT regenerate benchmark questions after Phase 2 is complete**, even if some look weak. Note weak ones in `PROGRESS.md`.
7. **Do NOT parallelize across phases.** Phase order is strict.
8. **Do NOT delete any file in `raw/`, `wiki/`, `rag_baseline/`, `benchmark/`, `results/` once written.** Append, don't overwrite (except for `index.md` and `log.md` which are intentionally mutable).
9. **Do NOT ask the user "should I do X" if X is specified in this document.** Re-read the relevant section first. Only escalate to BLOCKERS.md if genuinely ambiguous.
10. **Do NOT write a "conclusion" or "winner" section anywhere.** That's Agent 2's output.
11. **Do NOT `git push`, `git reset --hard`, `git rebase`, `git commit --amend`, or any history-rewriting operation.** Only `git add` and `git commit`. See Section 4.5.
12. **Do NOT stage `.env`** under any circumstance. Verify before every commit.
13. **Do NOT create git branches** or work on anything other than the default branch.

---

## 6. Quick Reference: Phase Dependency Graph

```
Phase 0 (Bootstrap)
    ↓ user provides .env + installs deps
Phase 1 (Data Acquisition)
    ↓
Phase 2 (Benchmark Generation)
    ↓
Phase 3 (Wiki Ingest)          ← longest phase (~3-5 hours)
    ↓
Phase 4 (RAG Baseline Build)
    ↓
Phase 5 (Answer Generation)
    ↓
Phase 6 (Handoff to Agent 2)
```

Total estimated runtime: 5-8 hours of compute, plus user setup time.
Total estimated cost: $5-12 USD (well under the $15 cap).

---

## 7. Final Reminder

Read this document fully before starting. Then:
1. Begin Phase 0.
2. STOP and ask the user for `.env` setup.
3. After user confirms, proceed through Phases 1-6 sequentially.
4. STOP at end of Phase 6 and notify user.

If at any point you are uncertain, the answer is: **stop, write to BLOCKERS.md, wait for human input.** Do not invent.

You have one job: produce clean, comparable answer files from two systems on the same benchmark. Everything else is scaffolding for that.

Begin.
