# References used in paper/draft.md

Only the 11 references below are used. Each entry holds the details given by the authors and nothing more: no page numbers, dataset sizes or results beyond what is written here. Entries marked "abstract-level only, not read in full" must be read before they are cited for anything beyond their one-line description. The in-text key is (Author, Year); the year of an arXiv-only item is taken from the arXiv number and is therefore inferred.

---

## 1. Shrutilipi
- **Key:** (Bhogale et al., 2022)
- **Title:** Effectiveness of Mining Audio and Text Pairs from Public Data for Improving ASR Systems for Low-Resource Languages
- **Authors:** Bhogale, Raman, Javed, Doddapaneni, Kunchukuttan, Kumar, Khapra
- **Venue / ID:** arXiv 2208.12666
- **Description:** A resource built by mining audio and text pairs from public data, including the All India Radio archives, where PDF transcripts are aligned to bulletin audio; it covers over 6,400 hours across 12 Indian languages and was built for training speech recognition systems.
- **Where we use it:** Related Work, paragraph on Indian broadcast archives, to say how our English-only pilot differs in purpose.

## 2. Rodier and Carter
- **Key:** (Rodier and Carter, 2020)
- **Title:** Online Near-Duplicate Detection of News Articles
- **Authors:** Rodier and Carter
- **Venue / ID:** LREC 2020 (ACL Anthology)
- **Description:** Flags near-duplicate news articles online by finding the most likely original, adapting shingling for this purpose.
- **Where we use it:** Related Work, paragraph on near-duplicate and novelty detection; background for the novelty gate (Section 4.3).
- **Status:** abstract-level only, not read in full

## 3. Lee
- **Key:** (Lee, 2015)
- **Title:** Online Sentence Novelty Scoring for Topical Document Streams
- **Authors:** Lee
- **Venue / ID:** EMNLP 2015 (ACL Anthology D15-1067)
- **Description:** Addresses sentence-level novelty detection in streams of documents.
- **Where we use it:** Related Work, paragraph on near-duplicate and novelty detection; background for the sentence-level novelty gate (Section 4.3).
- **Status:** abstract-level only, not read in full

## 4. Tumre, Patil, Kumar
- **Key:** (Tumre et al., 2025)
- **Title:** Improved Near-Duplicate Detection for Aggregated and Paywalled News-Feeds
- **Authors:** Tumre, Patil, Kumar
- **Venue / ID:** NAACL 2025 Industry track (2025.naacl-industry.73)
- **Description:** Combines embeddings with community detection to find near-duplicates among short news snippets.
- **Where we use it:** Related Work, paragraph on near-duplicate and novelty detection.
- **Status:** abstract-level only, not read in full

## 5. Fu, Ch'ng, Aickelin, Zhang
- **Key:** (Fu et al., 2015)
- **Title:** An improved system for sentence-level novelty detection in textual streams
- **Authors:** Fu, Ch'ng, Aickelin, Zhang
- **Venue / ID:** ICSSC 2015
- **Description:** A system for novelty detection in text streams that uses incremental TF-IDF together with locality-sensitive hashing.
- **Where we use it:** Related Work, paragraph on near-duplicate and novelty detection.
- **Status:** abstract-level only, not read in full

## 6. Whisper
- **Key:** (Radford et al., 2022)
- **Title:** Robust Speech Recognition via Large-Scale Weak Supervision
- **Authors:** Radford et al.
- **Venue / ID:** arXiv 2212.04356
- **Description:** Presents the Whisper speech recognition models, trained with large-scale weak supervision (as the title says).
- **Where we use it:** Related Work (ASR paragraph) and Section 3.5; the pipeline transcribes with Whisper models through the faster-whisper implementation.
- **Status:** abstract-level only, not read in full

## 7. Sentence-BERT
- **Key:** (Reimers and Gurevych, 2019)
- **Title:** Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks
- **Authors:** Reimers and Gurevych
- **Venue / ID:** arXiv 1908.10084
- **Description:** Presents a way to compute sentence embeddings with siamese BERT networks (as the title says).
- **Where we use it:** Related Work (embeddings paragraph); background for sentence embeddings in Section 4.2.
- **Status:** abstract-level only, not read in full

## 8. Retrieval-augmented generation
- **Key:** (Lewis et al., 2020)
- **Title:** Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
- **Authors:** Lewis et al.
- **Venue / ID:** arXiv 2005.11401
- **Description:** Presents retrieval-augmented generation for knowledge-intensive NLP tasks (as the title says).
- **Where we use it:** Related Work (retrieval and RAG paragraph); background for the two-tier retrieval and answer generation (Section 4.5).
- **Status:** abstract-level only, not read in full

## 9. Zero-shot text classification as entailment
- **Key:** (Yin et al., 2019)
- **Title:** Benchmarking Zero-shot Text Classification: Datasets, Evaluation and Entailment Approach
- **Authors:** Yin, Hay, Roth
- **Venue / ID:** EMNLP-IJCNLP 2019 (D19-1404), arXiv 1909.00161
- **Description:** Formulates zero-shot text classification as textual entailment.
- **Where we use it:** Related Work (zero-shot classification); background for the zero-shot genre backends (Section 4.4).
- **Status:** abstract-level only, not read in full

## 10. BART
- **Key:** (Lewis et al., 2019)
- **Title:** BART: Denoising Sequence-to-Sequence Pre-training for Natural Language Generation, Translation, and Comprehension
- **Authors:** Lewis et al.
- **Venue / ID:** arXiv 1910.13461
- **Description:** Presents BART, a denoising sequence-to-sequence pre-training approach (as the title says). The checkpoint we use, facebook/bart-large-mnli, is a model named after it; this entry does not say anything about how that checkpoint was fine-tuned.
- **Where we use it:** Related Work (zero-shot classification); the BART zero-shot genre backend (Section 4.4).
- **Status:** abstract-level only, not read in full

## 11a. FAISS (UNVERIFIED)
- **Key:** (Johnson et al., 2017) - UNVERIFIED
- **Title:** Billion-scale similarity search with GPUs
- **Authors:** Johnson, Douze, Jegou
- **Venue / ID:** arXiv 1702.08734
- **Status:** **UNVERIFIED**, from memory, check before citing; abstract-level only, not read in full
- **Description:** Given as the reference for the FAISS similarity-search library; nothing more is recorded here.
- **Where we use it:** Related Work (retrieval paragraph) and Section 4.5, where the project uses a flat inner-product FAISS index.

## 11b. MiniLM (UNVERIFIED)
- **Key:** (Wang et al., 2020) - UNVERIFIED
- **Title, other authors, venue, ID:** not given; **UNVERIFIED**, from memory, to be looked up and checked before citing
- **Status:** **UNVERIFIED**; abstract-level only, not read in full
- **Description:** Given as the reference for the MiniLM family of models; nothing more is recorded here.
- **Where we use it:** Related Work (embeddings paragraph) and Section 4.2, where the project uses an embedding model named all-MiniLM-L6-v2 (it is not established here that this reference describes that exact checkpoint).
