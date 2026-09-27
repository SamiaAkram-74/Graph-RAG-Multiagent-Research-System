"""
Streamlit frontend for GraphRAG-MARS — ResearchGraph AI.
Provides an interactive web UI for document ingestion, querying,
and viewing research reports.
"""

import streamlit as st
import requests
import json

# ── Configuration ────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8080/api"

st.set_page_config(
    page_title="ResearchGraph AI — GraphRAG-MARS",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 ResearchGraph AI")
st.markdown("*Graph RAG + Multi-Agent Research System*")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Configuration")
    experiment_type = st.selectbox(
        "Experiment Type",
        ["multi_agent", "hybrid_rag", "graph_rag", "vector_rag", "baseline_llm"],
        index=0,
    )
    include_web = st.checkbox("Include Web Search", value=True)
    max_results = st.slider("Max Results", 1, 20, 10)

    st.divider()
    st.header("📊 System Status")
    try:
        status = requests.get(f"{API_BASE}/status", timeout=5).json()
        st.success("System Online")
        st.metric("Vector Docs", status.get("vector_store", {}).get("document_count", 0))
        kg = status.get("knowledge_graph", {})
        st.metric("Graph Entities", kg.get("total_entities", 0))
        st.metric("Graph Relations", kg.get("total_relationships", 0))
    except Exception:
        st.error("System Offline")

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_query, tab_ingest, tab_graph, tab_eval = st.tabs([
    "🔍 Research Query",
    "📄 Document Ingestion",
    "🕸️ Knowledge Graph",
    "📈 Evaluation",
])

# ── Tab 1: Research Query ────────────────────────────────────────────────────

with tab_query:
    question = st.text_area(
        "Enter your research question:",
        placeholder="e.g., Compare CNN, Vision Transformer, and hybrid models for medical image classification.",
        height=100,
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        run_query = st.button("🚀 Run Research", type="primary", use_container_width=True)

    if run_query and question:
        with st.spinner("Running multi-agent research pipeline..."):
            # Show pipeline progress
            progress_steps = [
                "Planning...",
                "Vector retrieval...",
                "Graph retrieval...",
                "Web research...",
                "Reasoning...",
                "Fact checking...",
                "Generating report...",
            ]
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                response = requests.post(
                    f"{API_BASE}/query",
                    json={
                        "question": question,
                        "experiment_type": experiment_type,
                        "include_web_search": include_web,
                        "max_results": max_results,
                    },
                    timeout=300,
                )
                progress_bar.progress(100)
                status_text.text("✅ Complete!")
                if response.ok:
                    try:
                        result = response.json()
                    except ValueError:
                        st.error(
                            f"Backend returned invalid JSON.\n\n"
                            f"Status code: {response.status_code}\n\n"
                            f"Response: {response.text[:1000]}") 
                        result = None
                else:
                    st.error(
                        f"Backend request failed.\n\n"
                        f"Status code: {response.status_code}\n\n"
                        f"Response: {response.text[:1000]}"
                    )
                    result = None
            except Exception as e:
                st.error(f"Error: {e}")
                result = None

        if result:
            st.divider()

            # Executive Summary
            st.subheader("📋 Executive Summary")
            st.markdown(result.get("executive_summary", "No summary available"))

            # Findings
            st.subheader("🔎 Findings")
            for finding in result.get("findings", []):
                with st.expander(f"📌 {finding.get('title', 'Finding')}"):
                    st.markdown(finding.get("content", ""))

            # Evidence
            col_ev, col_gr = st.columns(2)
            with col_ev:
                st.metric("Evidence Chunks", result.get("evidence_count", 0))
            with col_gr:
                st.metric("Graph Relations", result.get("graph_relations_count", 0))

            # Verified Claims
            st.subheader("✅ Verified Claims")
            claims = result.get("verified_claims", [])
            if claims:
                for claim in claims:
                    verdict = claim.get("verdict", "unknown")
                    icon = "✅" if verdict == "supported" else "⚠️" if verdict == "partially_supported" else "❌"
                    st.markdown(f"{icon} **{claim.get('text', '')}** — *{verdict}*")
            else:
                st.info("No claims verified")

            # Limitations
            st.subheader("⚠️ Limitations")
            for lim in result.get("limitations", []):
                st.markdown(f"- {lim}")

            # References
            st.subheader("📚 References")
            for i, ref in enumerate(result.get("references", []), 1):
                title = ref.get("title", "")
                url = ref.get("url", "")
                if url:
                    st.markdown(f"[{i}] [{title}]({url})")
                else:
                    st.markdown(f"[{i}] {title}")

            # Metadata
            st.caption(
                f"Report ID: {result.get('report_id', '')} | "
                f"Experiment: {result.get('experiment_type', '')} | "
                f"Latency: {result.get('latency_sec', 0)}s"
            )

# ── Tab 2: Document Ingestion ───────────────────────────────────────────────

with tab_ingest:
    st.header("📄 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload research papers, PDFs, or text files:",
        accept_multiple_files=True,
        type=["pdf", "txt", "md", "docx", "csv"],
    )

    if uploaded_files and st.button("📤 Upload & Ingest"):
        for file in uploaded_files:
            with st.spinner(f"Processing {file.name}..."):
                try:
                    files = {"file": (file.name, file.getvalue(), file.type)}
                    resp = requests.post(
                        f"{API_BASE}/documents/ingest",
                        files=files,
                        timeout=120,
                    )
                    if resp.ok:
                        data = resp.json()
                        st.success(
                            f"✅ {file.name}: {data.get('chunks', 0)} chunks, "
                            f"{data.get('indexed', 0)} indexed"
                        )
                    else:
                        st.error(f"❌ Failed to ingest {file.name}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.header("📁 Ingest from Directory")
    dir_path = st.text_input("Directory path:", placeholder="/path/to/documents")
    if dir_path and st.button("📂 Ingest Directory"):
        try:
            resp = requests.post(
                f"{API_BASE}/documents/ingest-directory",
                data={"dir_path": dir_path},
                timeout=300,
            )
            if resp.ok:
                st.success(f"✅ {resp.json().get('message', 'Done')}")
            else:
                st.error("Ingestion failed")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Tab 3: Knowledge Graph ───────────────────────────────────────────────────

with tab_graph:
    st.header("🕸️ Knowledge Graph")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 View Graph Summary"):
            try:
                resp = requests.get(f"{API_BASE}/graph/summary", timeout=10)
                if resp.ok:
                    summary = resp.json()
                    st.metric("Entities", summary.get("total_entities", 0))
                    st.metric("Relationships", summary.get("total_relationships", 0))

                    st.subheader("Sample Entities")
                    for entity in summary.get("sample_entities", []):
                        st.markdown(
                            f"- **{entity.get('name', '')}** ({entity.get('type', '')})"
                        )

                    st.subheader("Sample Relationships")
                    for rel in summary.get("sample_relationships", []):
                        st.markdown(
                            f"- {rel.get('source', '?')} → "
                            f"*{rel.get('relationship', '?')}* → "
                            f"{rel.get('target', '?')}"
                        )
                else:
                    st.error("Failed to fetch graph summary")
            except Exception as e:
                st.error(f"Error: {e}")

    with col2:
        st.subheader("🏗️ Build Knowledge Graph")
        kg_dir = st.text_input("Documents directory:", key="kg_dir")
        if kg_dir and st.button("🔨 Build Graph"):
            with st.spinner("Building knowledge graph (this may take a while)..."):
                try:
                    resp = requests.post(
                        f"{API_BASE}/graph/build",
                        data={"dir_path": kg_dir},
                        timeout=600,
                    )
                    if resp.ok:
                        data = resp.json()
                        st.success(
                            f"✅ Entities: {data.get('entities', 0)}, "
                            f"Relationships: {data.get('relationships', 0)}"
                        )
                    else:
                        st.error("Graph build failed")
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 4: Evaluation ───────────────────────────────────────────────────────

with tab_eval:
    st.header("📈 Evaluation & Benchmarks")
    st.markdown(
        "Run experiments to compare different architectures:\n"
        "- **Baseline LLM**: Direct LLM answer\n"
        "- **Vector RAG**: Semantic search + LLM\n"
        "- **Graph RAG**: Knowledge graph + LLM\n"
        "- **Hybrid RAG**: Vector + Graph + LLM\n"
        "- **Multi-Agent**: Full pipeline with planning, reasoning, fact-checking"
    )

    if st.button("🧪 Run All Experiments", type="primary"):
        with st.spinner("Running evaluation benchmarks (this may take several minutes)..."):
            try:
                resp = requests.post(f"{API_BASE}/evaluate/run", timeout=600)
                if resp.ok:
                    results = resp.json().get("results", [])
                    st.success("✅ Evaluation complete!")

                    # Display comparison table
                    import pandas as pd
                    if results:
                        df = pd.DataFrame(results)
                        df = df.set_index("experiment_type")
                        st.dataframe(df, use_container_width=True)

                    # Display key findings
                    st.subheader("📊 Key Metrics Comparison")
                    for r in results:
                        with st.expander(f"📌 {r.get('experiment_type', '').upper()}"):
                            cols = st.columns(4)
                            cols[0].metric("Precision@K", f"{r.get('precision_at_k', 0):.3f}")
                            cols[1].metric("Faithfulness", f"{r.get('faithfulness', 0):.3f}")
                            cols[2].metric("Hallucination", f"{r.get('hallucination_rate', 0):.3f}")
                            cols[3].metric("Latency", f"{r.get('response_latency_sec', 0):.2f}s")
                else:
                    st.error("Evaluation failed")
            except Exception as e:
                st.error(f"Error: {e}")
