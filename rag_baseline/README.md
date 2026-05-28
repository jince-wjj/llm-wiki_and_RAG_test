# RAG Baseline

This directory holds the **vanilla** RAG baseline used for comparison
against the LLM-Wiki paradigm.

## Configuration

- Chunk size: 500 Chinese characters (sliding window)
- Overlap: 100 characters between adjacent chunks
- Embedding model: `BAAI/bge-m3` via SiliconFlow
- Vector store: ChromaDB persistent at `rag_baseline/chroma_db/`
- Collection: `hongloumeng_chunks` (cosine distance)
- Total chunks indexed: **1573**

## Files

- `chunks.jsonl` — all chunks with metadata (committed)
- `chroma_db/` — binary index (gitignored; regenerable from chunks.jsonl)
- `README.md` — this file

## Smoke test

Query: `林黛玉的性格是怎样的`

Top-5 chunks retrieved (by cosine distance):

- `ch029_p006400` (第29回): ，又是羞愧，便颤颤兢兢的
说道：“我要安心咒你，我也天诛地灭．何苦来！我知道，
昨日张道士说亲，你怕阻了你的好姻缘，你心里生气，来拿
我煞性子。”原来那宝玉自幼...
- `ch031_p000800` (第31回): 天性喜散不喜聚．他想的也有个道理，他说，"人
有聚就有散，聚时欢喜，到散时岂不冷清？既清冷则伤感，
所以不如倒是不聚的好．比如那花开时令人爱慕，谢时则增
惆怅，...
- `ch020_p004400` (第20回): "说著，
便赌气回房去了．
　　宝玉忙跟了来，问道：“好好的又生气了？就是我说错了，
你到底也还坐在那里，和别人说笑一会子． 又来自己纳闷。”
林黛玉道：“你管...
- `ch032_p003200` (第32回): 他拭面上的汗．宝玉瞅了半天，方说道"你放
心"三个字．林黛玉听了，怔了半天，方说道：“我有什么不
放心的？我不明白这话．你倒说说怎么放心不放心？"宝玉叹
了一口...
- `ch003_p006800` (第3回): ．纵然生得好皮囊，腹内
　　原来草莽．潦倒不通世务，愚顽怕读文章．行为偏僻
　　性乖张，那管世人诽谤！
　　富贵不知乐业，贫穷难耐凄凉．可怜辜负好韶光，于国于家...
