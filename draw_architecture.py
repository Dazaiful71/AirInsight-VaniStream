"""Render the AirInsight architecture diagram (16:9, one slide) to PNG + PDF.

Usage:  python draw_architecture.py
Output: AirInsight_Architecture.png, AirInsight_Architecture.pdf
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 160, 90
fig = plt.figure(figsize=(16, 9))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")

INK, MUTE = "#111827", "#6B7280"
COL = dict(ext="#FDE68A", cap="#BFDBFE", file="#E5E7EB", nlp="#C7D2FE", gate="#FEF3C7",
           store="#BBF7D0", rag="#FBCFE8", serve="#FED7AA", off="#DDD6FE")
N = {}  # node registry: key -> (x, y, w, h)


def group(x, y, w, h, title, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                fc="white", ec=color, lw=2.2, zorder=1))
    ax.add_patch(FancyBboxPatch((x, y + h - 3.3), w, 3.3, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=color, ec=color, lw=0, zorder=2))
    ax.text(x + 1.5, y + h - 1.65, title, ha="left", va="center", fontsize=8.5,
            fontweight="bold", color=INK, zorder=3)


def node(key, x, y, w, h, text, color, cyl=False, fs=6.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0,rounding_size={1.5 if cyl else 0.6}",
                                fc=color, ec=INK, lw=1.0, zorder=4))
    if cyl:
        ax.plot([x + 0.7, x + w - 0.7], [y + h - 1.3] * 2, color=INK, lw=0.6, zorder=5)
    ax.text(x + w / 2, y + h / 2 - (0.4 if cyl else 0), text, ha="center", va="center",
            fontsize=fs, color=INK, zorder=6, linespacing=1.2)
    N[key] = (x, y, w, h)


def edge(key, side, f=0.5):
    x, y, w, h = N[key]
    return {"l": (x, y + h * f), "r": (x + w, y + h * f),
            "t": (x + w * f, y + h), "b": (x + w * f, y)}[side]


def label(p, text, rot=0, fs=5.8):
    ax.text(p[0], p[1], text, fontsize=fs, ha="center", va="center", color=MUTE, style="italic",
            rotation=rot, zorder=9, bbox=dict(fc="white", ec="none", pad=0.5))


def link(pts, text=None, at=None, dashed=False, both=False, rot=0):
    """Polyline through pts, arrowhead(s) on the end(s)."""
    ls = (0, (3, 2)) if dashed else "-"
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=1.3, linestyle=ls, zorder=7,
                solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=9, lw=1.3,
                                 color=INK, linestyle=ls, zorder=7, shrinkA=0, shrinkB=0))
    if both:
        ax.add_patch(FancyArrowPatch(pts[1], pts[0], arrowstyle="-|>", mutation_scale=9, lw=1.3,
                                     color=INK, zorder=7, shrinkA=0, shrinkB=0))
    if text:
        label(at, text, rot)


# ---------------------------------------------------------------- title
ax.text(80, 87.4, "AirInsight / VaniStream  -  System Architecture", ha="center", va="center",
        fontsize=17, fontweight="bold", color=INK)
ax.text(80, 84.6, "All India Radio broadcast capture, NLP indexing and two-tier RAG chatbot",
        ha="center", va="center", fontsize=9, color=MUTE)

# ================================================================ BAND A: INGEST
group(3, 50.5, 22, 29.5, "1  Sources", COL["ext"])
node("live", 5, 66, 18, 8, "Live radio\nIcecast MP3 / HLS", COL["ext"])
node("web", 5, 51.5, 18, 7, "newsonair.gov.in\narchive bulletins", COL["ext"])

group(31, 50.5, 37, 29.5, "2  Capture + ASR", COL["cap"])
node("lsm", 33, 60, 33, 14.5,
     "live_stream_ingest.py\nLiveStreamManager (bg thread)\nffmpeg -> 16 kHz PCM\n30 s chunk / 5 s overlap\nfaster-whisper + VAD\nstrip_overlap stitching", COL["cap"])
node("scr", 33, 51.5, 33, 7,
     "air_bulletins_scraper.py (CLI)\nrobots.txt, jittered delay,\nSHA-256, optional Whisper", COL["cap"])

group(74, 50.5, 30, 29.5, "3  Files  (output/)", COL["file"])
node("ing", 76, 68.8, 26, 7,
     "ingest_pipeline.py (batch)\nreads metadata.csv, skips\nprocessed, dedup_report.json", COL["file"])
node("files", 76, 52.5, 26, 11,
     "audio/DATE/*.mp3\ntext/DATE/*.txt\nmetadata.csv", COL["file"], cyl=True)

group(110, 50.5, 43, 29.5, "4  NLP  (nlp_pipeline.py)", COL["nlp"])
node("seg", 113, 70.2, 37, 4.6, "Sentence split  (NLTK punkt_tab)", COL["nlp"])
node("emb", 113, 64.0, 37, 4.6, "Embed  (all-MiniLM-L6-v2, 384-d)", COL["nlp"])
node("mmr", 113, 57.8, 37, 4.6, "MMR novelty gate: cosine >= 0.85 -> duplicate, dropped", COL["gate"])
node("cls", 113, 51.6, 37, 4.6, "Genre x10: zero-shot / fast / fine-tuned", COL["nlp"])

# ================================================================ BAND B: SERVE / RAG / STORE
group(3, 14, 22, 32.5, "7  Serve", COL["serve"])
node("api", 5, 31, 18, 11,
     "chatbot_api.py\nFastAPI :8000\n/chat /timeline /audio\n/stats /dedup /health\n/stream/*", COL["serve"])
node("ui", 5, 17, 18, 10,
     "Web SPA (inline HTML)\nchat, timeline,\naudio player,\nstream status", COL["serve"])

group(42, 14, 56, 32.5, "6  Two-tier RAG  (rag_engine.py)", COL["rag"])
node("qp", 45, 37.5, 50, 4.2, "Parse query: date range (anchor = MAX(date) in DB) + genre keywords", COL["rag"], fs=6.1)
node("pre", 45, 32.3, 50, 4.2, "Tier 1: metadata_prefilter  (SQLite date + genre -> faiss_ids)", COL["rag"], fs=6.1)
node("ss", 45, 27.1, 50, 4.2, "Tier 2: embed query + FAISS search restricted to those ids", COL["rag"], fs=6.1)
node("rel", 45, 21.9, 50, 4.2, "Relevance filter: score >= max(0.20, 0.65 x top)", COL["rag"], fs=6.1)
node("gem", 45, 15.3, 24, 4.6, "Gemini 1.5 Flash\n(probed once, last 3 turns)", COL["ext"], fs=6.1)
node("ext", 71, 15.3, 24, 4.6, "Extractive fallback\n(no key / API error)", COL["rag"], fs=6.1)

group(110, 14, 43, 32.5, "5  Store  (vector_store.py)", COL["store"])
node("sql", 113, 30, 37, 9.5,
     "news_store.db  (SQLite)\nsegments: faiss_id, text, genre, date,\nhour, source_file, audio_start/end", COL["store"], cyl=True)
node("faiss", 113, 17, 37, 9,
     "faiss_index.bin  (FAISS)\nIndexFlatIP, 384-d unit vectors\n(cosine via inner product)", COL["store"], cyl=True)

# ================================================================ OFFLINE STRIP
group(3, 1.5, 150, 10, "Offline classifier training  (optional)", COL["off"])
node("bld", 5, 2.8, 35, 4.8, "build_genre_training_data.py\nsilver labels via zero-shot", COL["off"], fs=6.1)
node("csv", 46, 2.8, 30, 4.8, "genre_training_data.csv\nhuman-filled true_genre", COL["off"], cyl=True, fs=6.1)
node("trn", 82, 2.8, 30, 4.8, "train_genre_classifier.py\nDistilBERT fine-tune", COL["off"], fs=6.1)
node("mdl", 118, 2.8, 16, 4.8, "models/\nair-genre-classifier", COL["off"], cyl=True, fs=5.6)
node("evl", 139, 2.8, 12, 4.8, "eval_genre.py\nheld-out", COL["off"], fs=5.8)

# ================================================================ ARROWS: ingest band
link([edge("live", "r"), (33, 70)])
link([edge("web", "r"), (33, 55)])
link([(66, 61), (76, 61)], "mp3 + txt + csv", (71, 62.7))
link([(66, 55), (76, 55)])
link([edge("files", "t", 0.5), edge("ing", "b", 0.5)])
link([(102, 72.3), (113, 72.3)], "batch", (107.5, 74))
# real-time path: LSM -> over the top of the Files column -> Sentence split
link([(60, 74.5), (60, 82), (146, 82), (146, 74.8)], "real-time chunks", (100, 82))
link([edge("seg", "b", 0.5), edge("emb", "t", 0.5)])
link([edge("emb", "b", 0.5), edge("mmr", "t", 0.5)])
link([edge("mmr", "b", 0.5), edge("cls", "t", 0.5)], "novel", (134, 56.5))

# ================================================================ ARROWS: cross band
link([(131, 51.6), (131, 39.5)], "add_segments", (131, 48.6))
link([(150, 21.5), (155.5, 21.5), (155.5, 60.1), (150, 60.1)],
     "existing vectors (dedup)", (155.5, 40), dashed=True, rot=90)
link([(126, 2.8), (126, 0.8), (158, 0.8), (158, 53.9), (150, 53.9)],
     "fine-tuned weights", (158, 25), dashed=True, rot=90)
link([(18, 42), (18, 48.5), (89, 48.5), (89, 52.5)], "GET /audio/{faiss_id}", (50, 48.5), dashed=True)
link([(23, 42), (23, 47), (29, 47), (29, 67), (33, 67)], "start / stop", (29, 44.5), rot=90)

# ================================================================ ARROWS: serve / rag / store
link([edge("ui", "t"), edge("api", "b")], both=True)
link([(23, 39.6), (45, 39.6)], "query / answer", (34, 41.3), both=True)
link([edge("qp", "b", 0.3), edge("pre", "t", 0.3)])
link([edge("pre", "b", 0.3), edge("ss", "t", 0.3)])
link([edge("ss", "b", 0.3), edge("rel", "t", 0.3)])
link([edge("rel", "b", 0.3), edge("gem", "t", 0.5)], "LIVE", (55, 20.9))
link([edge("rel", "b", 0.7), edge("ext", "t", 0.5)], "else", (84, 20.9))
link([(95, 34.4), (113, 34.4)], "ids", (104, 36), both=True)
link([(95, 29.2), (113, 22.5)], "vectors", (104, 27.2), both=True)

# ================================================================ ARROWS: offline
link([(115, 14), (115, 12.8), (38, 12.8), (38, 7.6)], "reads segments + transcripts", (77, 12.8))
link([edge("bld", "r"), edge("csv", "l")])
link([edge("csv", "r"), edge("trn", "l")])
link([edge("trn", "r"), edge("mdl", "l")])
link([edge("mdl", "r"), edge("evl", "l")])

fig.savefig("AirInsight_Architecture.png", dpi=200)
fig.savefig("AirInsight_Architecture.pdf")
print("saved AirInsight_Architecture.png / .pdf")
