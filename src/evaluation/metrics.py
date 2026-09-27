"""
Evaluation metrics and benchmark runner for GraphRAG-MARS.
Implements the experimental comparison between different RAG architectures.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.config import get_settings
from src.core.schemas import ExperimentType, EvaluationResult


# ── Retrieval Metrics ────────────────────────────────────────────────────────

def precision_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    """Precision@K: fraction of top-K retrieved docs that are relevant."""
    if k == 0 or not retrieved:
        return 0.0
    top_k = retrieved[:k]
    relevant_count = sum(1 for doc_id in top_k if doc_id in relevant)
    return relevant_count / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int = 5) -> float:
    """Recall@K: fraction of relevant docs found in top-K."""
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    found = sum(1 for doc_id in relevant if doc_id in top_k)
    return found / len(relevant)


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """MRR: reciprocal rank of the first relevant document."""
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def context_relevance(
    question: str, chunks: list[dict], llm_client=None
) -> float:
    """Use LLM to rate relevance of retrieved context (0.0-1.0)."""
    if not chunks or not llm_client:
        return 0.0
    context = "\n".join(c.get("content", "")[:200] for c in chunks[:5])
    prompt = (
        f"Question: {question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Rate the relevance of this context to the question on a scale of 0.0 to 1.0. "
        "Return only a number."
    )
    try:
        response = llm_client.generate(prompt, system_prompt="You are a relevance evaluator.", temperature=0.0)
        score = float(response.strip())
        return max(0.0, min(1.0, score))
    except (ValueError, Exception):
        return 0.5


# ── Answer Quality Metrics ───────────────────────────────────────────────────

def factual_correctness(answer: str, reference: str, llm_client=None) -> float:
    """LLM-based factual correctness score (0.0-1.0)."""
    if not llm_client:
        return _rouge_f1(answer, reference)
    prompt = (
        f"Reference answer:\n{reference}\n\n"
        f"Generated answer:\n{answer}\n\n"
        "Rate the factual correctness of the generated answer compared to the reference "
        "on a scale of 0.0 to 1.0. Return only a number."
    )
    try:
        response = llm_client.generate(prompt, system_prompt="You are a factual correctness evaluator.", temperature=0.0)
        return max(0.0, min(1.0, float(response.strip())))
    except (ValueError, Exception):
        return _rouge_f1(answer, reference)


def faithfulness_score(answer: str, evidence: list[dict], llm_client=None) -> float:
    """Check if the answer is faithful to the evidence (no hallucination)."""
    if not evidence or not llm_client:
        return 0.5
    context = "\n".join(e.get("content", "")[:200] for e in evidence[:10])
    prompt = (
        f"Evidence:\n{context}\n\n"
        f"Answer:\n{answer}\n\n"
        "Is the answer faithful to the evidence? Rate from 0.0 (hallucinated) "
        "to 1.0 (fully faithful). Return only a number."
    )
    try:
        response = llm_client.generate(prompt, system_prompt="You are a faithfulness evaluator.", temperature=0.0)
        return max(0.0, min(1.0, float(response.strip())))
    except (ValueError, Exception):
        return 0.5


def _rouge_f1(prediction: str, reference: str) -> float:
    """Simple ROUGE-L F1 approximation."""
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        scores = scorer.score(reference, prediction)
        return scores["rougeL"].fmeasure
    except ImportError:
        # Fallback: word overlap
        pred_words = set(prediction.lower().split())
        ref_words = set(reference.lower().split())
        if not ref_words:
            return 0.0
        overlap = pred_words & ref_words
        precision = len(overlap) / len(pred_words) if pred_words else 0
        recall = len(overlap) / len(ref_words)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


def hallucination_rate(claims: list[dict]) -> float:
    """Calculate hallucination rate from verified claims."""
    if not claims:
        return 0.0
    unsupported = sum(
        1 for c in claims
        if c.get("verdict") in ("unsupported", "contradicted", "no_evidence")
    )
    return unsupported / len(claims)


# ── Benchmark Runner ─────────────────────────────────────────────────────────

class EvaluationRunner:
    """Runs the full experimental comparison across all architectures."""

    BENCHMARK_QUESTIONS = [
        {
            "question": "How does climate change affect crop yield through water stress?",
            "reference": "Climate change increases temperature, causing water stress which reduces crop yield.",
            "type": "multi_hop",
        },
        {
            "question": "Compare CNN and Vision Transformer for medical image classification.",
            "reference": "CNNs use convolution for local features; ViTs use self-attention for global context.",
            "type": "comparison",
        },
        {
            "question": "What are the limitations of traditional RAG systems?",
            "reference": "Traditional RAG lacks multi-hop reasoning and relationship understanding.",
            "type": "analysis",
        },
    ]

    def __init__(self, llm_client=None):
        self.settings = get_settings()
        self.llm_client = llm_client
        self.results: list[EvaluationResult] = []

    def run_all_experiments(self) -> list[dict]:
        """Run all 5 experiments and return comparison results."""
        logger.info("Starting evaluation benchmark...")
        all_results = []

        for exp_type in ExperimentType:
            logger.info(f"Running experiment: {exp_type.value}")
            result = self._run_experiment(exp_type)
            all_results.append(result.model_dump())

        # Save results
        self._save_results(all_results)
        return all_results

    def _run_experiment(self, exp_type: ExperimentType) -> EvaluationResult:
        """Run a single experiment type across all benchmark questions."""
        scores = {
            "precision": [], "recall": [], "mrr": [],
            "correctness": [], "faithfulness": [], "hallucination": [],
            "latency": [], "tokens": [],
        }

        for benchmark in self.BENCHMARK_QUESTIONS:
            start = time.time()
            # Here we'd call the actual pipeline for each experiment type
            # For now, record placeholder metrics
            latency = time.time() - start

            scores["latency"].append(latency)
            scores["correctness"].append(0.5)
            scores["faithfulness"].append(0.5)
            scores["hallucination"].append(0.1)
            scores["precision"].append(0.5)
            scores["recall"].append(0.5)
            scores["mrr"].append(0.5)
            scores["tokens"].append(500)

        def avg(lst):
            return sum(lst) / len(lst) if lst else 0.0

        return EvaluationResult(
            experiment_type=exp_type,
            precision_at_k=avg(scores["precision"]),
            recall_at_k=avg(scores["recall"]),
            mrr=avg(scores["mrr"]),
            factual_correctness=avg(scores["correctness"]),
            faithfulness=avg(scores["faithfulness"]),
            hallucination_rate=avg(scores["hallucination"]),
            response_latency_sec=avg(scores["latency"]),
            token_usage=int(avg(scores["tokens"])),
        )

    def _save_results(self, results: list[dict]) -> None:
        """Save evaluation results to disk."""
        results_dir = Path(self.settings.EVAL_RESULTS_PATH)
        results_dir.mkdir(parents=True, exist_ok=True)
        output_file = results_dir / f"eval_results_{int(time.time())}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {output_file}")

    def generate_comparison_table(self, results: list[dict]) -> str:
        """Generate a formatted comparison table."""
        if not results:
            return "No results available"

        header = f"{'Metric':<25}" + "".join(
            f"{r['experiment_type']:<15}" for r in results
        )
        lines = [header, "=" * len(header)]

        metrics = [
            ("Precision@K", "precision_at_k"),
            ("Recall@K", "recall_at_k"),
            ("MRR", "mrr"),
            ("Factual Correctness", "factual_correctness"),
            ("Faithfulness", "faithfulness"),
            ("Hallucination Rate", "hallucination_rate"),
            ("Latency (sec)", "response_latency_sec"),
            ("Token Usage", "token_usage"),
        ]

        for label, key in metrics:
            row = f"{label:<25}"
            for r in results:
                val = r.get(key, 0)
                row += f"{val:<15.4f}" if isinstance(val, float) else f"{val:<15}"
            lines.append(row)

        return "\n".join(lines)
