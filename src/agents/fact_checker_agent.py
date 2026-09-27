"""
Fact-Checking / Critic Agent — verifies each claim in the reasoned answer
against the evidence and flags hallucinations or unsupported statements.
"""

from __future__ import annotations

import json
import re
import uuid

from loguru import logger

from src.core.base_agent import BaseAgent
from src.core.schemas import (
    AgentRole,
    AgentMessage,
    Claim,
    ClaimVerdict,
    EvidenceChunk,
)


_FACT_CHECK_SYSTEM_PROMPT = """\
You are the Fact-Checking Agent in a multi-agent research system called GraphRAG-MARS.
Your critical role is to verify every factual claim in a generated answer
against the provided evidence.

For each claim, determine:
- SUPPORTED: The evidence clearly supports this claim.
- PARTIALLY_SUPPORTED: The evidence partially supports it but some aspects are unverified.
- UNSUPPORTED: The evidence does not support this claim.
- CONTRADICTED: The evidence directly contradicts this claim.
- NO_EVIDENCE: No relevant evidence was found for this claim.

Return JSON:
{
  "claims": [
    {
      "text": "the claim text",
      "verdict": "SUPPORTED|PARTIALLY_SUPPORTED|UNSUPPORTED|CONTRADICTED|NO_EVIDENCE",
      "confidence": 0.0-1.0,
      "reasoning": "explanation of why this verdict was given"
    }
  ],
  "overall_assessment": "brief summary of answer reliability",
  "hallucination_detected": true/false
}

Be strict. If a claim cannot be verified from the evidence, mark it as UNSUPPORTED.
"""


class FactCheckerAgent(BaseAgent):
    """Verifies claims and flags hallucinations."""

    def __init__(self, llm=None):
        super().__init__(role=AgentRole.FACT_CHECKER, llm=llm)

    def get_system_prompt(self) -> str:
        return _FACT_CHECK_SYSTEM_PROMPT

    def execute(self, message: AgentMessage) -> AgentMessage:
        """
        Input payload: {
            "reasoned_answer": "...",
            "question": "...",
            "evidence_chunks": [...],
            "evidence_used": 5
        }
        Output payload: {
            "verified_claims": [Claim.model_dump(), ...],
            "fact_check_summary": "...",
            "hallucination_detected": bool,
            "answer_text": "..."
        }
        """
        answer = message.payload.get("reasoned_answer", message.content)
        question = message.payload.get("question", "")
        evidence_chunks = message.payload.get("evidence_chunks", [])

        # Extract and verify claims
        claims = self._verify_claims(answer, question, evidence_chunks)

        supported = sum(1 for c in claims if c.verdict == ClaimVerdict.SUPPORTED)
        total = len(claims)
        hallucination_detected = any(
            c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED)
            for c in claims
        )

        summary = (
            f"Verified {total} claims: {supported} supported, "
            f"{total - supported} need attention."
        )

        logger.info(f"Fact check: {supported}/{total} claims supported")

        return self.create_message(
            content=summary,
            receiver=AgentRole.REPORT_GENERATOR,
            payload={
                "verified_claims": [c.model_dump() for c in claims],
                "fact_check_summary": summary,
                "hallucination_detected": hallucination_detected,
                "answer_text": answer,
                "question": question,
            },
        )

    def _verify_claims(
        self, answer: str, question: str, evidence_chunks: list[dict]
    ) -> list[Claim]:
        """Send the answer and evidence to the LLM for claim verification."""
        evidence_text = ""
        for i, chunk in enumerate(evidence_chunks[:20], 1):
            evidence_text += f"[E{i}] {chunk.get('content', '')[:300]}\n"

        prompt = (
            f"# Original Question\n{question}\n\n"
            f"# Generated Answer\n{answer}\n\n"
            f"# Available Evidence\n{evidence_text}\n\n"
            "Extract all factual claims from the answer and verify each against "
            "the evidence. Return JSON."
        )

        raw = self.call_llm(prompt, temperature=0.0)
        return self._parse_claims(raw)

    def _parse_claims(self, raw: str) -> list[Claim]:
        """Parse the LLM response into Claim objects."""
        try:
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            text = json_match.group(1).strip() if json_match else raw.strip()
            data = json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Fact checker response not valid JSON")
            return [Claim(
                claim_id=str(uuid.uuid4())[:8],
                text="Could not parse verification results",
                verdict=ClaimVerdict.NO_EVIDENCE,
                confidence=0.0,
                reasoning="LLM response parsing failed",
            )]

        claims = []
        for c in data.get("claims", []):
            verdict_str = c.get("verdict", "NO_EVIDENCE").upper()
            try:
                verdict = ClaimVerdict(verdict_str.lower())
            except ValueError:
                verdict = ClaimVerdict.NO_EVIDENCE

            claims.append(Claim(
                claim_id=str(uuid.uuid4())[:8],
                text=c.get("text", ""),
                verdict=verdict,
                confidence=c.get("confidence", 0.0),
                reasoning=c.get("reasoning", ""),
            ))

        return claims
