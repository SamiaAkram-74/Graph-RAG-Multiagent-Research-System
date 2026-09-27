"""
Entity extractor — uses LLM to extract entities and relationships from
document text for the knowledge graph.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from src.core.llm import LLMClient, get_llm


_EXTRACTION_PROMPT = """\
You are an expert at extracting structured knowledge from text.
Extract entities and relationships from the following text.

Entity types: Person, Organization, Disease, Technology, Method, Dataset,
              Concept, Variable, Research_Finding, Location, Chemical, Drug

Relationship types: causes, affects, improves, associated_with, depends_on,
                   developed_by, compared_with, used_for, treats, part_of,
                   increases, decreases, discovered_by

Return valid JSON:
{
  "entities": [
    {"name": "Entity Name", "type": "Concept", "description": "brief description"}
  ],
  "relationships": [
    {"source": "Entity A", "relationship": "causes", "target": "Entity B"}
  ]
}

Be precise. Extract only entities and relationships explicitly mentioned in the text.
"""


class EntityExtractor:
    """Extracts entities and relationships from text using LLM."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or get_llm()

    def extract(self, text: str, source: str = "unknown") -> dict[str, list[dict]]:
        """Extract entities and relationships from a text chunk."""
        if not text.strip():
            return {"entities": [], "relationships": []}

        # Truncate to avoid token limits
        text_input = text[:3000]
        prompt = f"{_EXTRACTION_PROMPT}\n\n---TEXT---\n{text_input}\n---END---"

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You are a knowledge graph extraction assistant.",
                temperature=0.0,
            )
            result = self._parse_response(response)
            # Attach source to each entity and relationship
            for entity in result.get("entities", []):
                entity["source"] = source
            for rel in result.get("relationships", []):
                rel["source_doc"] = source
            return result
        except Exception as e:
            logger.error(f"Entity extraction failed for '{source}': {e}")
            return {"entities": [], "relationships": []}

    def extract_batch(
        self, chunks: list[dict[str, str]]
    ) -> list[dict[str, list[dict]]]:
        """Extract from multiple text chunks."""
        results = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            source = chunk.get("source", f"chunk_{i}")
            result = self.extract(text, source)
            results.append(result)
            if (i + 1) % 10 == 0:
                logger.info(f"Entity extraction: {i+1}/{len(chunks)} chunks processed")
        return results

    def _parse_response(self, raw: str) -> dict[str, list[dict]]:
        """Parse LLM JSON response with fallback."""
        try:
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            text = json_match.group(1).strip() if json_match else raw.strip()
            data = json.loads(text)
            return {
                "entities": data.get("entities", []),
                "relationships": data.get("relationships", []),
            }
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Entity extraction response not valid JSON")
            return {"entities": [], "relationships": []}
