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
