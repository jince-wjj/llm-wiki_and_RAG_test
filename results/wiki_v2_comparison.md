# Wiki v2 Comparison Report

Before/after the alias-fragmentation fix. v2 was produced by: (1) merging 10 fragmented character pairs (3 known + 7 discovered) into their canonical full-name pages, (2) dropping and rebuilding the BGE-M3 wiki vector index over the resulting 438-page corpus, and (3) re-running the wiki query phase on all 100 benchmark questions with **unchanged** prompt, answer model (`deepseek-chat` / DeepSeek-V3), `max_tokens=400`, `temperature=0.0`, and `top-k=5`.

`results/wiki_answers.json` (v1) is preserved unmodified; v2 is in `results/wiki_answers_v2.json`. RAG side untouched.

**TL;DR / status: `NEEDS_USER_REVIEW`.** The merge itself is correct and lossless, but it did **not** produce the expected clean reduction in refusals — it is roughly net-neutral (~5 reproducible reversals vs ~3 reproducible new regressions). The new regressions stem from two pre-existing, out-of-scope retrieval-layer limitations (a confusable `甄宝玉` distractor and a 4000-char page truncation). See §6.

## 1. Merge Summary

| Dupe | Canonical | Dupe (B) | Canon before (B) | Canon after (B) | Ch inserted | Ch deduped | Supplements |
|---|---|---:|---:|---:|---:|---:|---:|
| `黛玉` | `林黛玉` | 767 | 23794 | 24300 | 1 | 1 | 0 |
| `宝玉` | `贾宝玉` | 7930 | 45291 | 47865 | 3 | 9 | 1 |
| `宝钗` | `薛宝钗` | 5996 | 20082 | 22109 | 7 | 8 | 0 |
| `元春` | `贾元春` | 397 | 2098 | 2451 | 1 | 0 | 0 |
| `宝琴` | `薛宝琴` | 1946 | 1252 | 3118 | 4 | 0 | 0 |
| `岫烟` | `邢岫烟` | 1374 | 1175 | 2510 | 4 | 0 | 0 |
| `惜春` | `贾惜春` | 3563 | 2714 | 4992 | 12 | 2 | 0 |
| `探春` | `贾探春` | 9074 | 5551 | 10641 | 17 | 8 | 0 |
| `旺儿` | `来旺儿` | 1774 | 294 | 2024 | 5 | 0 | 0 |
| `迎春` | `贾迎春` | 4109 | 3531 | 4827 | 6 | 7 | 0 |

**10 pairs merged** = 3 known (黛玉/宝玉/宝钗) + 7 discovered via the Step-1 substring scan.

Merge policy: dupe chapter-blocks were merged into the canonical page in ascending chapter order. Per-chapter content already present verbatim in the canonical was **deduped** (column *Ch deduped*); content for a chapter present in both but with *different* bullets was kept as a labelled supplement block (column *Supplements*); chapters only in the dupe were **inserted** (column *Ch inserted*). No information was deleted. Each canonical's `aliases` now includes the short name; `source_count` was summed.

### Discovered but NOT merged (false positives — distinct entities)

These substring matches cleared the >200-byte gate but name different people (relative/spouse/servant pages, or 贾宝玉 vs 甄宝玉). Per the conservative-merge rule they were left untouched:

| Shorter | Longer | Reason |
|---|---|---|
| `吴新登` | `吴新登家的` | 管家吴新登 vs 其妻（不同人物） |
| `宝玉` | `甄宝玉` | 贾宝玉 vs 甄宝玉（江南甄家之子，不同人物） |
| `尤氏` | `尤氏母亲` | 尤氏 vs 其母（不同人物） |
| `彩霞` | `彩霞之母` | 丫鬟彩霞 vs 其母（不同人物） |
| `旺儿` | `旺儿媳妇` | 来旺儿 vs 其妻（不同人物） |
| `春燕` | `春燕姑妈` | 小丫头春燕 vs 其姑妈（不同人物） |
| `李纨` | `李纨寡婶` | 李纨 vs 其寡婶（不同人物） |
| `林之孝` | `林之孝家的` | 林之孝 vs 其妻（不同人物） |
| `贾芸` | `贾芸母亲` | 贾芸 vs 其母（不同人物） |
| `贾蓉` | `贾蓉之妻` | 贾蓉 vs 其妻秦可卿（不同人物） |
| `赖大` | `赖大家的` | 赖大 vs 其妻（不同人物） |
| `赖大` | `赖大母亲` | 赖大 vs 赖嬷嬷（不同人物） |
| `金文翔` | `金文翔媳妇` | 金文翔 vs 其妻（不同人物） |
| `金荣` | `金荣母亲胡氏` | 金荣 vs 其母胡氏（不同人物） |
| `鲍二` | `鲍二家的` | 鲍二 vs 其妻（不同人物） |

## 2. Retrieval Shift

Counts of how often each entity's page(s) appeared in the top-5 retrieved set across the 100 questions. In v1 the entity was split across canonical + dupe; *v1 either* is the deduped union of the two (the true v1 reach), *v1 both* is questions that wasted two of their five slots on the same entity. v2 has a single unified page.

| Canonical | Alias | v1 canon | v1 dupe | v1 either | v1 both | v2 canon |
|---|---|---:|---:|---:|---:|---:|
| `林黛玉` | `黛玉` | 17 | 19 | 21 | 15 | 22 |
| `贾宝玉` | `宝玉` | 40 | 41 | 42 | 39 | 43 |
| `薛宝钗` | `宝钗` | 10 | 11 | 11 | 10 | 11 |
| `贾元春` | `元春` | 3 | 3 | 3 | 3 | 3 |
| `薛宝琴` | `宝琴` | 2 | 2 | 3 | 1 | 2 |
| `邢岫烟` | `岫烟` | 1 | 1 | 1 | 1 | 1 |
| `贾惜春` | `惜春` | 0 | 1 | 1 | 0 | 0 |
| `贾探春` | `探春` | 2 | 2 | 3 | 1 | 2 |
| `来旺儿` | `旺儿` | 1 | 0 | 1 | 0 | 1 |
| `贾迎春` | `迎春` | 1 | 2 | 2 | 1 | 1 |

In v1, **71 (question × entity)** slots were wasted on a duplicate page of an entity already retrieved — those slots are now freed for other pages, which is the mechanism behind the answer changes below.

## 3. Per-Question Diff — 12 Sanity-Check Questions

Verdict is **form only** — whether v2 is more substantive / covers more ground / flips a refusal. Correctness is the evaluator's call, not judged here.

### Q21 [Tier 1] — **NEUTRAL**

**Q:** 贾雨村为了讨好贾赦，陷害了谁？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面信息，贾雨村为了讨好贾赦，陷害了石呆子。页面“人物/贾雨村.md”第48回更新记载：“平儿骂贾雨村设局讹诈石呆子拖欠官银，抄没扇子，导致石呆子生死不明”。同时，“事件/贾琏挨打.md”也提到“贾赦因石呆子扇子事，责怪贾琏无能”。因此，贾雨村设局讹诈石呆子，抄没其扇子，以讨好贾赦。 | 根据wiki页面信息，贾雨村为了讨好贾赦，陷害了石呆子。页面“人物/贾雨村.md”第48回更新记载：“平儿骂贾雨村设局讹诈石呆子拖欠官银，抄没扇子，导致石呆子生死不明”。同时，“事件/贾琏挨打.md”也提到贾赦因石呆子扇子事责怪贾琏，导致贾琏挨打。因此，贾雨村设局讹诈石呆子，抄没其扇子，以讨好贾赦。 |
| **Length** | 148 chars | 150 chars |
| **Retrieved** | `人物/贾雨村.md`, `人物/贾赦.md`, `事件/贾琏挨打.md`, `人物/贾琏.md`, `人物/娇杏.md` | `人物/贾雨村.md`, `人物/贾赦.md`, `事件/贾琏挨打.md`, `人物/贾琏.md`, `人物/娇杏.md` |

### Q4 [Tier 1] — **NEUTRAL**

**Q:** 薛家母子进京后住在荣国府的哪个院子？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据 wiki 页面信息，薛家母子（薛姨妈、薛蟠、薛宝钗）进京后住在荣国府的梨香院。页面“地点/梨香院”明确记载：“薛姨妈一家进京后，贾政请他们住于此。”[第4回] 梨香院位于荣国府东北角，有十余间房屋，前厅后舍俱全，另有一门通街，方便出入。 | 根据 wiki 页面信息，薛家母子（薛姨妈、薛蟠、薛宝钗）进京后住在荣国府的梨香院。页面“地点/梨香院”明确记载：“薛姨妈一家进京后，贾政请他们住于此。”[第4回] 梨香院位于荣国府东北角，约有十余间房屋，前厅后舍俱全，另有一门通街，方便出入。 |
| **Length** | 121 chars | 122 chars |
| **Retrieved** | `事件/刘姥姥一进荣国府.md`, `地点/梨香院.md`, `人物/薛姨妈.md`, `人物/贾母.md`, `人物/薛宝琴.md` | `事件/刘姥姥一进荣国府.md`, `地点/梨香院.md`, `人物/薛姨妈.md`, `人物/贾母.md`, `人物/薛宝琴.md` |

### Q1 [Tier 1] — **NO_CHANGE**

**Q:** 贾珠的妻子是谁？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据 wiki 页面“人物/李纨.md”中的基本信息，贾珠的妻子是李纨。页面明确记载：“贾珠之妻，贾母称‘珠大嫂子’。”[第3回] | 根据 wiki 页面“人物/李纨.md”中的基本信息，贾珠的妻子是李纨。页面明确记载：“贾珠之妻，贾母称‘珠大嫂子’。”[第3回] |
| **Length** | 65 chars | 65 chars |
| **Retrieved** | `人物/贾珠.md`, `人物/王夫人.md`, `人物/贾母.md`, `人物/贾敏.md`, `人物/李纨.md` | `人物/贾珠.md`, `人物/王夫人.md`, `人物/贾母.md`, `人物/贾敏.md`, `人物/李纨.md` |

### Q54 [Tier 2] — **NO_CHANGE**

**Q:** 柳湘莲在梦中见到尤三姐时，尤三姐说了什么来表明自己的去向？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面记载，尤三姐死后魂魄来见柳湘莲，自称“奉警幻之命前往太虚幻境修注情鬼”，并与柳湘莲诀别。 | 根据wiki页面记载，尤三姐死后魂魄来见柳湘莲，自称“奉警幻之命前往太虚幻境修注情鬼”，并与柳湘莲诀别。 |
| **Length** | 52 chars | 52 chars |
| **Retrieved** | `人物/柳湘莲.md`, `事件/柳湘莲出家.md`, `人物/尤三姐.md`, `事件/尤三姐思嫁柳二郎.md`, `事件/尤三姐自刎.md` | `人物/柳湘莲.md`, `事件/柳湘莲出家.md`, `人物/尤三姐.md`, `事件/尤三姐思嫁柳二郎.md`, `事件/尤三姐自刎.md` |

### Q39 [Tier 2] — **NEUTRAL**

**Q:** 在第四十五回中，凤姐儿如何处理周瑞家的儿子醉酒闹事一事？赖嬷嬷为何建议不要撵他？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面《人物/凤姐.md》第45回更新，凤姐处理周瑞家的儿子醉酒闹事时，最初决定撵他出去。赖嬷嬷建议不要撵他，改为打四十棍，理由是“撵了出去，叫他怎么见人？他老子娘也是老脸面”，并劝凤姐“得饶人处且饶人”。凤姐最终听从了赖嬷嬷的建议，改为打四十棍。 | 根据wiki页面《人物/凤姐.md》和《人物/周瑞家的.md》第45回记载，凤姐因周瑞家的儿子醉酒骂人，要撵他出去。赖嬷嬷劝凤姐改为打四十棍，不要撵他，因为赖嬷嬷是贾府老仆人，孙子赖尚荣刚选为州县官，她感谢主子恩典，并认为撵人过于严厉，建议宽厚处理，以体现主子恩德。凤姐答应了赖嬷嬷的请求。 |
| **Length** | 129 chars | 145 chars |
| **Retrieved** | `人物/凤姐.md`, `人物/王熙凤.md`, `人物/周瑞家的.md`, `人物/赖嬷嬷.md`, `人物/赖大家的.md` | `人物/凤姐.md`, `人物/王熙凤.md`, `人物/周瑞家的.md`, `人物/赖嬷嬷.md`, `人物/赖大家的.md` |

### Q38 [Tier 2] — **NEUTRAL**

**Q:** 在第四十五回中，黛玉在风雨夜作《秋窗风雨夕》后，宝玉来访，黛玉为何在说“渔婆”后脸红？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据提供的wiki页面，未包含第四十五回的相关内容。页面中关于黛玉和宝玉的信息仅更新至第八十回，且未提及《秋窗风雨夕》及“渔婆”情节。因此，wiki未提供足够信息来回答此问题。 | 根据提供的wiki页面，未包含第四十五回的相关内容。页面仅更新至第三十回，因此无法回答黛玉在第四十五回中为何在说“渔婆”后脸红。wiki未提供足够信息。 |
| **Length** | 88 chars | 76 chars |
| **Retrieved** | `人物/黛玉.md`, `人物/林黛玉.md`, `事件/黛玉葬花.md`, `人物/宝玉.md`, `人物/贾宝玉.md` | `人物/林黛玉.md`, `事件/黛玉葬花.md`, `事件/慈姨妈爱语慰痴颦.md`, `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md` |

### Q68 [Tier 3] — **NEUTRAL**

**Q:** 香菱学诗过程中，黛玉和宝钗对她的态度有何不同？请结合第48回中的描写说明。

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据第48回描写，黛玉对香菱学诗持积极鼓励态度：香菱拜黛玉为师，黛玉教她作诗方法，推荐王维、杜甫、李白等诗集，并认真评点香菱的诗作，如评第一首“措词不雅”。宝钗则相对冷静旁观：香菱苦志学诗时，宝钗评其第二首诗“不象吟月，句句是月色”，指出问题但未主动指导；香菱随宝钗进园住，宝钗虽同意她同住，但未像黛玉那样亲自教学。总体而言，黛玉热情教导，宝钗则保持距离。 | 根据第48回描写，黛玉和宝钗对香菱学诗的态度明显不同。黛玉积极指导香菱，收她为徒，教她作诗方法，推荐王维、杜甫、李白等诗集，并认真评点香菱的诗作，如评第一首“措词不雅”，鼓励她继续努力。宝钗则相对旁观，虽允许香菱同住蘅芜苑，但未主动教学，仅在第48回中评香菱第二首诗“不象吟月，句句是月色”，带有批评意味，未像黛玉那样悉心引导。总体而言，黛玉热情支持，宝钗较为冷淡。 |
| **Length** | 178 chars | 183 chars |
| **Retrieved** | `人物/香菱.md`, `事件/美香菱屈受贪夫棒.md`, `事件/香菱学诗.md`, `人物/黛玉.md`, `人物/林黛玉.md` | `人物/香菱.md`, `事件/美香菱屈受贪夫棒.md`, `事件/香菱学诗.md`, `人物/林黛玉.md`, `事件/黛玉葬花.md` |

### Q65 [Tier 3] — **REGRESSED**

**Q:** 在芦雪庵联诗中，凤姐起句“一夜北风紧”后，众人如何评价这句诗？这一评价与第18回中元春对宝玉题咏的态度有何相似之处？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面信息，芦雪庵联句中凤姐起句“一夜北风紧”后，众人如何评价这句诗，以及第18回中元春对宝玉题咏的态度，均未在提供的页面中明确记载。wiki页面仅提到李纨起三句后联句，但未记录具体诗句及评价；第18回中凤姐的活动也未涉及元春对宝玉题咏的评价。因此，wiki未提供足够信息来回答此问题。 | 根据wiki页面信息，芦雪庵联句中凤姐起句“一夜北风紧”后，众人如何评价这一句，以及第18回中元春对宝玉题咏的态度，均未在提供的页面中明确记载。因此，wiki未提供足够信息来回答此问题。 |
| **Length** | 148 chars | 93 chars |
| **Retrieved** | `地点/芦雪庵.md`, `事件/芦雪庵联句.md`, `人物/凤姐.md`, `人物/王熙凤.md`, `事件/凤姐泼醋.md` | `地点/芦雪庵.md`, `事件/芦雪庵联句.md`, `人物/凤姐.md`, `人物/王熙凤.md`, `事件/凤姐泼醋.md` |

### Q84 [Tier 3] — **REGRESSED**

**Q:** 薛蟠从江南带回的土仪中，宝钗如何分配？林黛玉收到后有何反应？

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据 wiki 页面记载，薛蟠从江南带回的土仪中，宝钗将礼物一分分配妥当，送给各人，其中黛玉的比别人加厚一倍（第67回）。但页面未提供林黛玉收到后的具体反应，因此无法回答此部分。 | 根据 wiki 页面，薛蟠从江南带回的土仪中，宝钗如何分配以及林黛玉收到后的反应，wiki 未提供足够信息。页面仅提到薛蟠带回两箱子东西，一箱绸缎绫锦洋货，一箱笔墨纸砚等物，内有虎丘泥人小像，并听从母亲和宝钗建议下帖请伙计吃酒，但未说明宝钗如何分配这些物品，也未提及林黛玉收到后的反应。 |
| **Length** | 89 chars | 143 chars |
| **Retrieved** | `人物/薛蟠.md`, `事件/薛蟠外出经商.md`, `事件/薛蟠娶夏金桂.md`, `人物/宝钗.md`, `人物/薛宝钗.md` | `人物/薛蟠.md`, `事件/薛蟠外出经商.md`, `事件/薛蟠娶夏金桂.md`, `人物/薛宝钗.md`, `事件/宝钗借扇机带双敲.md` |

### Q87 [Tier 4] — **NEUTRAL**

**Q:** 第41回中，妙玉将成窑茶杯给刘姥姥用后嫌脏不要，而宝玉建议送给刘姥姥，妙玉同意但强调“幸而那杯子是我没吃过的，若我使过，我就砸碎了也不能给他”。这与第44回中，贾母对贾琏偷情一事的态度“什么要紧的事！小孩子们年轻，馋嘴猫儿似的，那里保得住不这么著”形成对比。请分析妙玉的洁癖与贾母的宽容之间的矛盾。

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面，第41回中妙玉因刘姥姥用过成窑杯而嫌脏不要，强调“幸而那杯子是我没吃过的，若我使过，我就砸碎了也不能给他”，体现其极端洁癖与孤傲性格。而第44回贾母对贾琏偷情的态度“什么要紧的事！小孩子们年轻，馋嘴猫儿似的，那里保得住不这么著”，显示其宽容与务实。两者矛盾源于身份与立场：妙玉是带发修行的尼姑，追求精神纯净；贾母是家族长辈，注重家庭和谐与体面。这种对比反映了《红楼梦》中不同阶层与性格的价值观冲突。 | 根据wiki页面信息，第41回中妙玉因刘姥姥用过成窑杯而嫌脏不要，并强调“若我使过，我就砸碎了也不能给他”，体现其极端洁癖和孤傲性格。而第44回贾母对贾琏偷情一事的态度“什么要紧的事！小孩子们年轻，馋嘴猫儿似的，那里保得住不这么著”，显示其宽容大度。两者矛盾源于身份与处境差异：妙玉是带发修行的尼姑，出身仕宦，因多病入空门，洁癖反映其精神洁癖与对世俗的疏离；贾母是荣国府最高长辈，历经家族兴衰，宽容体现其持家智慧与对人性弱点的理解。这种对比凸显了《红楼梦》中不同阶层与性格人物的处世哲学差异。 |
| **Length** | 208 chars | 246 chars |
| **Retrieved** | `人物/妙玉.md`, `人物/刘姥姥.md`, `事件/刘姥姥一进荣国府.md`, `人物/宝玉.md`, `人物/贾宝玉.md` | `人物/妙玉.md`, `人物/刘姥姥.md`, `事件/刘姥姥一进荣国府.md`, `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md` |

### Q96 [Tier 4] — **NEUTRAL**

**Q:** 在第十三回中，秦可卿托梦给凤姐，建议‘趁今日富贵，将祖茔附近多置田庄房舍’，以备将来败落。然而在第十六回中，凤姐却利用贾琏外出之机，私下收受老尼净虚的银子，干预官司，导致张金哥和守备之子双双自杀。请问，凤姐的行为是否与秦可卿的劝诫相矛盾？请结合两回内容说明。

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据wiki页面，秦可卿在第十三回托梦凤姐，建议“趁今日富贵，将祖茔附近多置田庄房舍”，以备将来败落，体现居安思危的远见。然而，第十六回记载凤姐收受老尼净虚三千两银子，干预张金哥退婚官司，导致两人自杀，并“自此凤姐胆识愈壮，恣意作为”。凤姐的行为与秦可卿的劝诫相矛盾：秦可卿劝其未雨绸缪、保全家族，凤姐却贪图私利、滥用权力，加剧家族风险，违背了托梦的警示。 | 根据wiki页面，秦可卿在第十三回托梦凤姐，建议“趁今日富贵，将祖茔附近多置田庄房舍”，以备将来败落。然而在第十六回中，凤姐收受老尼净虚三千两银子，干预官司，导致张金哥和守备之子自杀。凤姐的行为与秦可卿的劝诫相矛盾：秦可卿劝其未雨绸缪、保全家族，而凤姐却贪图私利、恣意作为，加剧家族风险。wiki记载凤姐自此“胆识愈壮，恣意作为”，显示她未听从劝诫，反而更趋贪婪。 |
| **Length** | 178 chars | 182 chars |
| **Retrieved** | `人物/秦可卿.md`, `事件/秦可卿之死.md`, `人物/凤姐.md`, `人物/王熙凤.md`, `事件/凤姐泼醋.md` | `人物/秦可卿.md`, `事件/秦可卿之死.md`, `人物/凤姐.md`, `人物/王熙凤.md`, `事件/凤姐泼醋.md` |

### Q97 [Tier 4] — **NEUTRAL**

**Q:** 第四十九回中，宝钗对香菱和湘云谈诗表示不满，说‘一个女孩儿家，只管拿著诗作正经事讲起来，叫有学问的人听了，反笑话说不守本分的’；而在第三十七回中，宝钗自己却积极参与诗社，并给宝玉起号‘富贵闲人’。请对比宝钗在两回中对‘作诗’态度的差异，并分析是否矛盾。

| | v1 | v2 |
|---|---|---|
| **Answer** | 根据提供的wiki页面，第四十九回中宝钗确实笑称“呆香菱之心苦，疯湘云之话多”，但页面未记录宝钗说“一个女孩儿家，只管拿著诗作正经事讲起来，叫有学问的人听了，反笑话说不守本分的”这句话。第三十七回内容未在页面中收录。因此，wiki未提供足够信息来对比宝钗在两回中对“作诗”态度的差异，也无法分析是否矛盾。 | 根据提供的wiki页面，第四十九回中宝钗对香菱和湘云谈诗表示不满，称“呆香菱之心苦，疯湘云之话多”，但未直接引用“不守本分”等语。第三十七回中宝钗积极参与诗社并给宝玉起号“富贵闲人”的信息也未在页面中提及。因此，wiki未提供足够信息来对比宝钗在两回中对“作诗”态度的差异或分析是否矛盾。 |
| **Length** | 152 chars | 144 chars |
| **Retrieved** | `人物/宝钗.md`, `人物/薛宝钗.md`, `事件/宝钗借扇机带双敲.md`, `人物/香菱.md`, `事件/美香菱屈受贪夫棒.md` | `人物/薛宝钗.md`, `事件/宝钗借扇机带双敲.md`, `事件/薛宝钗羞笼红麝串.md`, `人物/香菱.md`, `事件/美香菱屈受贪夫棒.md` |

**Sanity totals:** IMPROVED=0, REGRESSED=2, NEUTRAL=8, NO_CHANGE=2

## 4. Full-Set Diff Stats (100 questions)

- **Substantively different (v2 ≠ v1, whitespace-normalized):** 82 / 100
- **Refusals reversed** (v1 said “wiki 未提供足够信息”, v2 answered): **6**  → Q[5, 24, 30, 40, 85, 94]
- **Refusals introduced** (v1 answered, v2 refused): **5**  → Q[48, 59, 64, 84, 91]
- **Total refusals:** v1 = 35, v2 = 34
- **Mean answer-length change:** +3.3 chars (v2 − v1)

> ⚠️ The raw `diff` count (82/100) is dominated by **generation nondeterminism**, not by the merge: of the 38 questions whose retrieved page-set was *identical* between v1 and v2, 26 (68%) still produced different answer text. DeepSeek-V3 is not deterministic at `temperature=0`. Answer **text** therefore cannot be attributed to the merge; the **refusal-status** and **retrieval** metrics are far more stable (see §6).

## 5. Cost (extra spend for this task)

- **Embeddings** (BGE-M3 via SiliconFlow, free tier): 438 page vectors re-embedded on index rebuild + one query vector per question. Logged but **$0**.
- **DeepSeek wiki_query calls:** 415 (entity-extraction + answer + embedding calls; includes the stop/resume index rebuild and a few retries).
- **DeepSeek tokens:** 1,065,921 input + 16,017 output.
- **Additional spend: $0.2649** (phase delta) — matches overall delta $0.2649.
- Pre-task total: $1.8207 → post-task total: $2.0856.
- Budget cap for this task was $1.00 extra → **26% of cap used.**

## 6. Root-Cause Analysis & Nondeterminism Diagnostics

Because answer text is noisy at `temperature=0`, the only trustworthy quality signal is whether an answer **refuses** (“wiki 未提供足够信息”). Two controlled probes were run (diagnostic only — they do not touch the official v2 results):

- **v2-frozen probe** (`results/wiki_v2_diag_v2probe.json`): hold each question's v2 retrieved page-set fixed, re-call the answer model 3×.
- **v1-reconstructed probe** (`results/wiki_v2_diag_v1probe.json`): rebuild each question's *pre-merge* 5-page context from the `HEAD~1` git state (recovering the deleted dupe pages), re-call 3×.

**Refusal noise floor:** across the 14 probed edge questions, only **2** flipped refusal status across identical-input reps — so the refusal metric is mostly stable (unlike the 68% text churn).

### The 5 "introduced" refusals, adjudicated

| Q | v1 reconstructed (refuse/3) | v2 frozen (refuse/3) | Adjudication |
|---|---:|---:|---|
| Q48 | 2/3 | 3/3 | Borderline — v1 was already fragile (2/3 refuse); merge pushed it to 3/3. |
| Q59 | 0/3 | 3/3 | **Genuine regression** — v1 reliably answered, v2 reliably refuses (distractor). |
| Q64 | 3/3 | 3/3 | **Noise** — v1 also refuses 3/3 on rerun; original v1 answer was the lucky 1/3. |
| Q84 | 0/3 | 2/3 | **Genuine regression** — v1 reliably answered, v2 mostly refuses (truncation). |
| Q91 | 0/3 | 3/3 | **Genuine regression** — v1 reliably answered, v2 reliably refuses (distractor). |

So the headline **"5 refusals introduced" overstates the harm**: ~**3 genuine reproducible regressions** (Q59, Q84, Q91), 1 borderline (Q48), 1 pure noise (Q64).

### Two structural mechanisms behind the regressions

1. **Confusable-distractor displacement (Q59, Q91, and the 宝玉 cluster).** In v1, a 宝玉 question retrieved *both* `人物/宝玉.md` and `人物/贾宝玉.md`. Removing the dupe frees a top-5 slot, which BGE-M3 vector search then fills with the *visually/semantically confusable* `人物/甄宝玉.md` — a **different character** (the Zhen-family Bao-yu). The consolidated canonical page is still retrieved, but the added distractor measurably pushes the model toward refusal.
2. **Page-truncation burial (Q84).** `src/wiki_query.py::format_page_block` truncates each page to the first **4000 chars** before sending it to the model. v1's small `宝钗.md` dupe (~3000 chars) fit entirely, so its 第67回 content was visible. After merging, 第67回 sits at char ~9017 of the 10330-char `薛宝钗.md` and is **truncated away** — the consolidated page paradoxically exposes *less* of the late-chapter content than the small dupe did. This affects late-chapter questions on the three large merged pages (`贾宝玉` 21k, `林黛玉` 11k, `薛宝钗` 10k chars).

Both mechanisms are properties of the **pre-existing retrieval/formatting layer**, which the brief froze (top-k=5, no prompt/param changes, 4000-char block truncation is a retrieval parameter). They were therefore **left unchanged** — this report documents them rather than fixing them.

### Net assessment

- **Retrieval** (clean signal): the merge ended 100% of duplicate-page double-retrieval; 71 wasted (question×entity) slots were reclaimed.
- **Refusals** (stable signal): ~5 reproducible reversals vs ~3 reproducible new regressions → roughly **net-neutral**, not the clean win the brief anticipated.
- **Answer text** (noisy signal): not interpretable due to temp=0 nondeterminism.

The fix was executed exactly as specified and lost no information on disk, but it did not by itself resolve the refusal problem. Closing the gap would require addressing the two mechanisms above (e.g. excluding `甄宝玉` as a distractor / per-page chapter-aware chunking instead of a flat 4000-char head) — both **out of scope** here because they change frozen retrieval parameters. Flagged for evaluator/user decision.
