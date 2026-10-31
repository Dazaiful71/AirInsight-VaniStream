import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header on pages 2+
        if self._pageNumber > 1:
            self.drawString(54, 755, "AirInsight — All India Radio Intelligence System | Technical Architecture")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        # Footer on all pages
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        
        self.drawString(54, 32, "AIRINSIGHT INTELLIGENCE PLATFORM — TECHNICAL ARCHITECTURE SPECIFICATION")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_pdf(filename="AirInsight_System_Architecture.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=23,
        leading=27,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=10,
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#64748B"),
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=9,
        spaceAfter=3,
        keepWithNext=True,
    )

    h3_style = ParagraphStyle(
        'Heading3_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2.5,
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.8,
        leading=9.2,
        textColor=colors.HexColor("#E2E8F0"),
    )

    diagram_style = ParagraphStyle(
        'Diagram_Custom',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=6.6,
        leading=8.8,
        textColor=colors.HexColor("#0F172A"),
    )

    tbl_header = ParagraphStyle(
        'TblHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#FFFFFF"),
    )

    tbl_cell = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.8,
        textColor=colors.HexColor("#1E293B"),
    )

    tbl_cell_bold = ParagraphStyle(
        'TblCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.2,
        leading=9.8,
        textColor=colors.HexColor("#0F172A"),
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E3A8A"),
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("AirInsight — Technical Architecture", title_style))
    story.append(Paragraph("System Architecture Specification & Component Blueprint for All India Radio Intelligence", subtitle_style))
    
    meta_text = "<b>Status:</b> Production Ready &nbsp;|&nbsp; <b>Domain:</b> Broadcast Radio ASR & RAG &nbsp;|&nbsp; <b>Vector Dim:</b> 384 (all-MiniLM-L6-v2) &nbsp;|&nbsp; <b>LLM:</b> Gemini 1.5 Flash"
    story.append(Paragraph(meta_text, meta_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceBefore=6, spaceAfter=10))

    # Executive Summary Box
    summary_html = """<b>Executive Architecture Summary:</b> AirInsight is an end-to-end broadcast intelligence platform for All India Radio (AIR). 
    It integrates dual audio capture (AJAX archive scraping and real-time Icecast/HLS streaming), Whisper automatic speech recognition with voice activity detection, 
    streaming MMR novelty deduplication, multi-backend news genre classification (zero-shot NLI and fine-tuned DistilBERT), a dual-store vector index 
    (FAISS IndexFlatIP + SQLite relational metadata store), and a context-aware Retrieval-Augmented Generation (RAG) synthesis engine featuring Google Gemini 1.5 Flash 
    with deterministic extractive fallback."""
    
    summary_table = Table(
        [[Paragraph(summary_html, callout_style)]],
        colWidths=[504]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#93C5FD")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 9),
        ('RIGHTPADDING', (0,0), (-1,-1), 9),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Section 1: Architecture Diagram
    story.append(Paragraph("1. High-Level Architecture & Tier Diagram", h1_style))
    story.append(Paragraph("The system is organized into five operational tiers operating across batch and continuous real-time execution pipelines:", body_style))

    ascii_diagram = """+-----------------------------------------------------------------------------------------------+
|                               1. INGESTION & AUDIO CAPTURE TIER                               |
|  * Archival Scraper (air_bulletins_scraper.py): AJAX crawl, UA rotation, robots.txt, politeness |
|  * Live Stream Ingest (live_stream_ingest.py): Icecast / HLS -> FFmpeg 16kHz PCM audio stream  |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|                                2. ASR & AUDIO PROCESSING TIER                                 |
|  * Archival Bulletins: faster-whisper (int8) / openai-whisper transcription                   |
|  * Real-Time Stream: 30s rolling chunk + 5s overlap, Silero VAD, strip_overlap stitching      |
|  * Audio Fingerprinting & Provenance: SHA-256 hash, audio_start & audio_end timecode mapping  |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|                           3. NLP INTELLIGENCE & NOVELTY GATE TIER                             |
|  * Sentence Tokenization: NLTK punkt_tab (UTF-8 BOM stripping)                                |
|  * Dense Embedding: all-MiniLM-L6-v2 (384-dimensional unit-normalized float32 vectors)        |
|  * Streaming MMR Novelty Filter: Cosine threshold >= 0.85 -> Duplicate Log (dedup_report.json)|
|  * 10-Genre Classification: Zero-Shot BART / Fast MiniLM / Domain Fine-Tuned DistilBERT      |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|                                4. DUAL STORAGE & PERSISTENCE                                  |
|  * FAISS IndexFlatIP (faiss_index.bin): 384-dim inner product search (unit vector cosine)     |
|  * SQLite DB (news_store.db): Relational metadata, date, hour, genre, source_file, timestamps|
|  * File Archive: output/audio/<date>/*.mp3, output/text/<date>/*.txt, output/metadata.csv     |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
|                                  5. TWO-TIER RAG & SERVING                                    |
|  * REST API (FastAPI @ port 8000): /chat, /timeline, /stats, /health, /dedup, /stream/*       |
|  * Query Parser: Relative date parsing with Dynamic Corpus Date Anchoring (MAX(date))         |
|  * Retrieval: Tier 1 SQLite Metadata Prefilter -> Tier 2 FAISS Vector Search                 |
|  * Relevance Gate: Adaptive thresholding (score >= max(0.20, top * 0.65))                    |
|  * Synthesis: Google Gemini 1.5 Flash grounded prompt (fallback: high-fidelity extractive)   |
|  * User Interface: Responsive dark-mode SPA, live radio player bar, deduplication audit pill  |
+-----------------------------------------------------------------------------------------------+"""

    diag_table = Table([[Paragraph(f"<pre>{ascii_diagram}</pre>", diagram_style)]], colWidths=[504])
    diag_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(diag_table)
    story.append(Spacer(1, 10))

    # Tiers Summary Table
    tiers_data = [
        [Paragraph("Tier", tbl_header), Paragraph("Component", tbl_header), Paragraph("Key Technologies", tbl_header), Paragraph("Operational Responsibility", tbl_header)],
        [Paragraph("<b>Tier 1: Ingestion</b>", tbl_cell_bold), Paragraph("Scraper & Stream Manager", tbl_cell), Paragraph("Requests, BeautifulSoup, FFmpeg, Threading", tbl_cell), Paragraph("Pulls archival MP3s via AJAX; decodes live Icecast/HLS streams to 16kHz mono PCM.", tbl_cell)],
        [Paragraph("<b>Tier 2: ASR</b>", tbl_cell_bold), Paragraph("Speech Recognition", tbl_cell), Paragraph("faster-whisper (int8), Silero VAD, OpenAI Whisper", tbl_cell), Paragraph("Converts audio chunks to text; performs overlap stitching (strip_overlap) & word alignment.", tbl_cell)],
        [Paragraph("<b>Tier 3: NLP</b>", tbl_cell_bold), Paragraph("Novelty & Classification", tbl_cell), Paragraph("NLTK punkt_tab, all-MiniLM-L6-v2, BART/DistilBERT", tbl_cell), Paragraph("Sentence tokenization, 384-dim dense embeddings, MMR novelty filter (cosine >= 0.85), 10-genre classification.", tbl_cell)],
        [Paragraph("<b>Tier 4: Storage</b>", tbl_cell_bold), Paragraph("Dual-Store Persistence", tbl_cell), Paragraph("FAISS IndexFlatIP, SQLite (news_store.db)", tbl_cell), Paragraph("Stores unit-normalized vector embeddings alongside rich relational metadata & audio offsets.", tbl_cell)],
        [Paragraph("<b>Tier 5: Serving</b>", tbl_cell_bold), Paragraph("Two-Tier RAG & API", tbl_cell), Paragraph("FastAPI, Gemini 1.5 Flash, Vanilla JS UI", tbl_cell), Paragraph("Two-tier prefilter retrieval, timeline aggregation, audio streaming endpoint, responsive Web UI.", tbl_cell)],
    ]
    t_tiers = Table(tiers_data, colWidths=[74, 95, 125, 210])
    t_tiers.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_tiers)
    story.append(Spacer(1, 12))

    # Section 2: Ingestion & Audio Capture
    story.append(Paragraph("2. Ingestion & Audio Capture Tier", h1_style))
    
    story.append(Paragraph("2.1 Archival Scraper (air_bulletins_scraper.py)", h2_style))
    story.append(Paragraph("The archival ingestion module interacts with the All India Radio official CMS portal (<code>newsonair.gov.in</code>). Key mechanisms include:", body_style))
    story.append(Paragraph("• <b>Robots.txt & Compliance:</b> Automatically inspects <code>robots.txt</code> via <code>urllib.robotparser.RobotFileParser</code> before initiating scrape runs.", bullet_style))
    story.append(Paragraph("• <b>Politeness Delays & UA Rotation:</b> Randomizes delays between 1.0s and 3.0s per request with jitter; rotates modern desktop user agents.", bullet_style))
    story.append(Paragraph("• <b>AJAX Pagination Engine:</b> Dispatches POST requests to <code>/wp-admin/admin-ajax.php</code> with actions <code>get_listen_news_categories</code> and <code>filter_bulletins_audio</code>.", bullet_style))
    story.append(Paragraph("• <b>Streaming CSV Checkpointing:</b> Appends bulletin metadata rows immediately upon downloading each file, recording title, broadcast date, category, URL, SHA-256 fingerprint, and file paths.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph("2.2 Real-Time Stream Ingestion (live_stream_ingest.py)", h2_style))
    story.append(Paragraph("The live stream engine enables continuous monitoring and zero-latency indexing of active radio broadcasts:", body_style))
    story.append(Paragraph("• <b>FFmpeg Subprocess Pipeline:</b> Spawns a resilient decoding pipeline with reconnect flags (<code>-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5</code>), outputting raw 16kHz mono 16-bit PCM bytes (32,000 bytes/sec).", bullet_style))
    story.append(Paragraph("• <b>Rolling Sliding Window:</b> Buffers audio in configurable windows (default 30s chunk with 5s overlap). Each chunk is converted to MP3 and transcribed on the fly.", bullet_style))
    story.append(Paragraph("• <b>Overlap Text Stitching (strip_overlap):</b> Analyzes character-level overlaps between consecutive chunks (up to 2,000 characters) to remove redundant boundary sentences before insertion.", bullet_style))
    story.append(Paragraph("• <b>Timestamp Alignment:</b> Aggregates Whisper segment timecodes to assign audio start and end timestamps (<code>audio_start</code>, <code>audio_end</code>) to every sentence.", bullet_style))
    story.append(Paragraph("• <b>In-Memory Dedup Cache:</b> Maintains synchronized embedding arrays in memory to prevent expensive database roundtrips during streaming ingestion.", bullet_style))

    story.append(Spacer(1, 12))

    # Section 3: NLP Intelligence & Novelty Deduplication
    story.append(Paragraph("3. NLP Intelligence & Novelty Deduplication Pipeline", h1_style))
    story.append(Paragraph("The NLP pipeline (<code>nlp_pipeline.py</code>) processes transcripts through four sequential phases:", body_style))

    story.append(Paragraph("Phase 1: Sentence Tokenization & Normalization", h3_style))
    story.append(Paragraph("Transcripts undergo UTF-8 BOM stripping (<code>\\ufeff</code>) and sentence boundary detection using NLTK's pre-trained <code>punkt_tab</code> tokenizer. Whitespace is normalized and fragments below semantic thresholds are purged.", body_style))

    story.append(Paragraph("Phase 2: Dense Semantic Embedding", h3_style))
    story.append(Paragraph("Sentences are embedded into 384-dimensional dense vectors using <code>all-MiniLM-L6-v2</code> (SentenceTransformers). Vectors are L2-normalized to unit length: <code>v_norm = v / ||v||</code>, enabling cosine similarity computation via simple inner products.", body_style))

    story.append(Paragraph("Phase 3: Streaming MMR Novelty Gate", h3_style))
    story.append(Paragraph("Broadcast news exhibits high repetition across hourly bulletins. To optimize storage and search relevance, AirInsight employs a streaming Maximal Marginal Relevance (MMR) novelty gate:", body_style))
    
    formula_html = "<b>Novelty Condition:</b> A candidate sentence <i>s_i</i> is accepted into the index if and only if:<br/>" \
                   "&nbsp;&nbsp;&nbsp;&nbsp;<b>max</b><sub>v &isin; P</sub> ( <b>u</b><sub>s_i</sub> &middot; <b>v</b> ) &lt; &tau;<sub>MMR</sub> &nbsp;&nbsp;&nbsp;&nbsp;(where &tau;<sub>MMR</sub> = 0.85 and P is the pool of existing + processed vectors)"
    f_tbl = Table([[Paragraph(formula_html, callout_style)]], colWidths=[504])
    f_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#94A3B8")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(f_tbl)
    story.append(Spacer(1, 4))
    story.append(Paragraph("Duplicates exceeding 0.85 similarity are rejected and recorded with similarity scores and matching parent segments in <code>dedup_report.json</code>, providing an audit trail of corpus redundancy reduction (typically 35% - 45%).", body_style))

    story.append(Paragraph("Phase 4: Multi-Backend News Genre Classification", h3_style))
    story.append(Paragraph("Accepted novel sentences are classified into one of 10 standard AIR news taxonomy genres: <i>Politics, Economy, Science & Technology, Sports, International, Defence & Security, Health, Environment, Society & Culture, Other</i>.", body_style))
    
    genres_tbl_data = [
        [Paragraph("Backend", tbl_header), Paragraph("Underlying Architecture", tbl_header), Paragraph("Characteristics & Fallback Behavior", tbl_header)],
        [Paragraph("<b>zero-shot (Default)</b>", tbl_cell_bold), Paragraph("facebook/bart-large-mnli", tbl_cell), Paragraph("Highest zero-shot classification quality. Processes hypothesis entailment over 10 candidate labels.", tbl_cell)],
        [Paragraph("<b>fast</b>", tbl_cell_bold), Paragraph("cross-encoder/nli-MiniLM2-L6-H768", tbl_cell), Paragraph("Lightweight, high-throughput transformer. 4x faster inference with minimal accuracy penalty.", tbl_cell)],
        [Paragraph("<b>finetuned</b>", tbl_cell_bold), Paragraph("DistilBERT (Domain Adapted)", tbl_cell), Paragraph("Fine-tuned on AIR corpus (<code>models/air-genre-classifier</code>). Falls back gracefully to fast zero-shot if weights missing.", tbl_cell)],
    ]
    t_genres = Table(genres_tbl_data, colWidths=[110, 154, 240])
    t_genres.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_genres)

    story.append(Spacer(1, 12))

    # Section 4: Dual Storage & Persistence Tier
    story.append(Paragraph("4. Storage & Retrieval Architecture (vector_store.py)", h1_style))
    story.append(Paragraph("AirInsight implements a dual-store paradigm separating high-dimensional vector search from relational metadata queries:", body_style))

    story.append(Paragraph("4.1 FAISS Vector Store (faiss_index.bin)", h2_style))
    story.append(Paragraph("• <b>Index Type:</b> <code>faiss.IndexFlatIP</code> operating on 384-dimensional L2-normalized float32 vectors.", bullet_style))
    story.append(Paragraph("• <b>Search Mechanics:</b> Computes exact inner products equivalent to cosine similarity. Supports constrained subset search using <code>faiss.IDSelectorArray</code> for metadata-filtered candidate lists.", bullet_style))

    story.append(Paragraph("4.2 SQLite Metadata Store (news_store.db)", h2_style))
    story.append(Paragraph("Relational metadata is managed in SQLite with the following production schema:", body_style))

    schema_sql = """CREATE TABLE segments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    faiss_id         INTEGER UNIQUE,         -- 1:1 foreign reference to FAISS vector slot
    text             TEXT NOT NULL,          -- Clean sentence transcript segment
    genre            TEXT,                   -- Classified news category (e.g. Politics)
    genre_confidence REAL,                   -- Model posterior probability (0.0 - 1.0)
    date             TEXT,                   -- Broadcast date (YYYY-MM-DD)
    hour             INTEGER,                -- Broadcast hour integer (e.g. 800, 1300)
    source_file      TEXT,                   -- Relative path to source transcript text file
    indexed_at       TEXT,                   -- UTC ISO-8601 indexing timestamp
    audio_start      REAL,                   -- Starting offset in seconds within source audio
    audio_end        REAL                    -- Ending offset in seconds within source audio
);"""
    
    schema_tbl = Table([[Paragraph(f"<pre>{schema_sql}</pre>", code_style)]], colWidths=[504])
    schema_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1E293B")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#0F172A")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(schema_tbl)

    story.append(Spacer(1, 4))
    story.append(Paragraph("4.3 Audio Provenance Resolution", h2_style))
    story.append(Paragraph("Function <code>resolve_audio_path()</code> dynamically maps any segment's <code>source_file</code> to its parent MP3 broadcast on disk. It checks <code>output/metadata.csv</code> first, falling back to canonical path swapping (<code>text/*.txt -> audio/*.mp3</code>), ensuring 100% end-to-end citation auditability.", body_style))

    story.append(Spacer(1, 12))

    # Section 5: Two-Tier RAG Engine
    story.append(Paragraph("5. Two-Tier RAG Engine & Retrieval Pipeline (rag_engine.py)", h1_style))
    story.append(Paragraph("To eliminate hallucination and prevent semantic drift across dates and categories, AirInsight uses a strictly bounded two-tier retrieval architecture:", body_style))

    rag_steps = [
        [Paragraph("Step", tbl_header), Paragraph("Stage Name", tbl_header), Paragraph("Implementation Logic & Guardrails", tbl_header)],
        [Paragraph("<b>Step 1</b>", tbl_cell_bold), Paragraph("Query Analysis", tbl_cell), Paragraph("Parses relative dates (<i>yesterday, last week, last N days</i>) using <b>Corpus Date Anchoring</b> (<code>_get_corpus_anchor()</code>) bound to <code>MAX(date)</code> in SQLite. Extracts genre using word-boundary regex over <code>GENRE_KEYWORD_MAP</code>.", tbl_cell)],
        [Paragraph("<b>Step 2</b>", tbl_cell_bold), Paragraph("Tier 1: SQL Prefilter", tbl_cell), Paragraph("Executes <code>metadata_prefilter(date_from, date_to, genre)</code> in SQLite. Bounding candidate IDs before FAISS prevents out-of-scope semantic matches. If zero candidates exist, the query aborts with an informative message.", tbl_cell)],
        [Paragraph("<b>Step 3</b>", tbl_cell_bold), Paragraph("Tier 2: FAISS Search", tbl_cell), Paragraph("Encodes user query with <code>all-MiniLM-L6-v2</code>. Restricts search to prefiltered candidate IDs using <code>IDSelectorArray</code>, returning top-k cosine similarity matches.", tbl_cell)],
        [Paragraph("<b>Step 4</b>", tbl_cell_bold), Paragraph("Relevance Filtering", tbl_cell), Paragraph("Applies <code>_filter_by_relevance()</code>: Drops results below noise floor (0.05). For topical queries, rejects candidates if top score &lt; 0.20, and prunes distant tails using <code>threshold = max(0.20, top_score * 0.65)</code>.", tbl_cell)],
        [Paragraph("<b>Step 5</b>", tbl_cell_bold), Paragraph("RAG Synthesis", tbl_cell), Paragraph("Constructs grounded context. Probes <code>GEMINI_API_KEY</code>: if operational (<code>LIVE</code>), invokes <code>gemini-1.5-flash</code> with conversation history. Otherwise, invokes deterministic <b>Extractive Fallback</b>.", tbl_cell)],
    ]
    t_rag = Table(rag_steps, colWidths=[45, 115, 344])
    t_rag.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_rag)

    story.append(Spacer(1, 6))
    story.append(Paragraph("Timeline Query Engine (timeline_query):", h3_style))
    story.append(Paragraph("Supports story evolution tracking by querying segments across wide time windows, sorting retrieved items by <code>(date, hour)</code>, and grouping them chronologically into structured daily bulletins for the UI timeline visualization.", body_style))

    story.append(Spacer(1, 12))

    # Section 6: REST API & Web UI Layer
    story.append(Paragraph("6. REST API & User Interface Specification (chatbot_api.py)", h1_style))
    story.append(Paragraph("FastAPI serves as the asynchronous application server, hosting both programmatic endpoints and an integrated single-page dark-mode web application:", body_style))

    api_endpoints = [
        [Paragraph("HTTP Method & Path", tbl_header), Paragraph("Request Body / Parameters", tbl_header), Paragraph("Response Contract & Description", tbl_header)],
        [Paragraph("<b>POST /chat</b>", tbl_cell_bold), Paragraph("<code>ChatRequest(message, session_id)</code>", tbl_cell), Paragraph("Returns <code>ChatResponse(reply, sources, filters, session_id)</code> with multi-turn memory.", tbl_cell)],
        [Paragraph("<b>GET /timeline</b>", tbl_cell_bold), Paragraph("<code>?q=...&genre=...&date_from=...</code>", tbl_cell), Paragraph("Returns chronologically ordered segments grouped by date and broadcast hour.", tbl_cell)],
        [Paragraph("<b>GET /audio/{faiss_id}</b>", tbl_cell_bold), Paragraph("<code>faiss_id</code> (path integer)", tbl_cell), Paragraph("Streams MP3 bulletin with HTTP byte-range scrubbing and directory traversal checks.", tbl_cell)],
        [Paragraph("<b>POST /stream/start</b>", tbl_cell_bold), Paragraph("<code>StreamStartRequest(url, lang, chunk_s)</code>", tbl_cell), Paragraph("Launches real-time background radio transcription and FAISS indexing thread.", tbl_cell)],
        [Paragraph("<b>POST /stream/stop</b>", tbl_cell_bold), Paragraph("<code>StreamStopRequest(stream_id)</code>", tbl_cell), Paragraph("Flushes active audio buffer, terminates ffmpeg process cleanly, and halts ingest loop.", tbl_cell)],
        [Paragraph("<b>GET /stream/status</b>", tbl_cell_bold), Paragraph("None", tbl_cell), Paragraph("Returns running flag, stream URL, uptime, segments ingested, and last chunk timestamp.", tbl_cell)],
        [Paragraph("<b>GET /stats</b>", tbl_cell_bold), Paragraph("None", tbl_cell), Paragraph("Returns total segments, breakdown per genre, and earliest/latest broadcast dates.", tbl_cell)],
        [Paragraph("<b>GET /dedup</b>", tbl_cell_bold), Paragraph("None", tbl_cell), Paragraph("Returns deduplication reduction percentage and top rejected duplicate pairs.", tbl_cell)],
        [Paragraph("<b>GET /health</b>", tbl_cell_bold), Paragraph("None", tbl_cell), Paragraph("Returns system health and active generation mode (<code>LIVE</code> vs <code>FALLBACK</code>).", tbl_cell)],
        [Paragraph("<b>GET /</b>", tbl_cell_bold), Paragraph("None", tbl_cell), Paragraph("Serves single-page dark mode HTML/JS UI with live streaming modal and audio player bar.", tbl_cell)],
    ]
    t_api = Table(api_endpoints, colWidths=[120, 150, 234])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_api)

    story.append(Spacer(1, 12))

    # Section 7: Offline Training & Evaluation Harness
    story.append(Paragraph("7. Domain Fine-Tuning & Evaluation Harness", h1_style))
    story.append(Paragraph("AirInsight provides an integrated training and evaluation toolchain for fine-tuning transformer classifiers on broadcast radio vernacular:", body_style))
    story.append(Paragraph("• <b>Training Data Bootstrapping (build_genre_training_data.py):</b> Extracts segments from SQLite and transcripts; produces silver labels using zero-shot inference; enriches under-represented categories using synthetic domain templates (<code>GENRE_TEMPLATES</code>).", bullet_style))
    story.append(Paragraph("• <b>DistilBERT Fine-Tuner (train_genre_classifier.py):</b> Fine-tunes <code>distilbert-base-uncased</code> using stratified validation splits, class-balanced cross-entropy loss, and AdamW optimization. Best checkpoints are saved to <code>models/air-genre-classifier/</code>.", bullet_style))
    story.append(Paragraph("• <b>Evaluation & Leakage Prevention (eval_genre.py):</b> Samples held-out segments strictly excluded from training data; computes accuracy, per-class F1, and confusion matrices; produces comparative metrics between zero-shot and fine-tuned models.", bullet_style))

    story.append(Spacer(1, 12))

    # Section 8: File Layout & Directory Structure
    story.append(Paragraph("8. Project Directory & Artifact Topology", h1_style))
    
    dir_tree = """AirInsight-main/
├── air_bulletins_scraper.py      # Archive scraper for newsonair.gov.in
├── live_stream_ingest.py         # Real-time radio stream transcription & live ingestion
├── nlp_pipeline.py               # Tokenization, MiniLM embedding, MMR dedup, Genre classification
├── vector_store.py               # FAISS IndexFlatIP + SQLite metadata store
├── rag_engine.py                 # Date/genre parsing, two-tier retrieval, Gemini & fallback synthesis
├── ingest_pipeline.py            # Batch orchestrator for metadata.csv processing
├── chatbot_api.py                # FastAPI REST endpoints + Single Page Web UI
│
├── build_genre_training_data.py  # Silver label generation + synthetic augmentation
├── train_genre_classifier.py     # DistilBERT fine-tuning script
├── eval_genre.py                 # Evaluation harness (confusion matrix, F1, leakage prevention)
│
├── faiss_index.bin               # Persisted FAISS vector index (384-dim)
├── news_store.db                 # SQLite relational database (segments table)
├── dedup_report.json             # Deduplication audit report (reduction %, top dropped pairs)
├── processed_files.txt           # File tracking registry for incremental batch ingest
│
└── output/
    ├── metadata.csv              # Master catalog of audio bulletins and transcripts
    ├── audio/                    # Archived audio bulletins (output/audio/<date>/*.mp3)
    └── text/                     # Transcribed text bulletins (output/text/<date>/*.txt)"""

    tree_tbl = Table([[Paragraph(f"<pre>{dir_tree}</pre>", code_style)]], colWidths=[504])
    tree_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#0F172A")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#334155")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tree_tbl)

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    out_pdf = "AirInsight_System_Architecture.pdf"
    if len(sys.argv) > 1:
        out_pdf = sys.argv[1]
    build_pdf(out_pdf)
