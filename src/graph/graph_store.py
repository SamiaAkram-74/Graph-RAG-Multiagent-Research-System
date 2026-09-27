"""
Knowledge graph store — manages the graph database using Neo4j or
a fallback in-memory NetworkX graph.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from src.config import get_settings


class GraphStore:
    """Knowledge graph backed by Neo4j or NetworkX."""

    def __init__(self, use_neo4j: bool = True):
        self.settings = get_settings()
        self.use_neo4j = use_neo4j
        self._driver = None
        self._nx_graph = None

        if use_neo4j:
            self._init_neo4j()
        else:
            self._init_networkx()

    def _init_neo4j(self) -> None:
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self.settings.NEO4J_URI,
                auth=(self.settings.NEO4J_USER, self.settings.NEO4J_PASSWORD),
            )
            # Verify connection
            self._driver.verify_connectivity()
            logger.info("Neo4j connection established")
        except Exception as e:
            logger.warning(f"Neo4j unavailable ({e}), falling back to NetworkX")
            self.use_neo4j = False
            self._init_networkx()

    def _init_networkx(self) -> None:
        import networkx as nx
        self._nx_graph = nx.MultiDiGraph()
        logger.info("NetworkX graph initialised (in-memory)")

    def add_entities(self, entities: list[dict]) -> int:
        """Add entity nodes to the graph."""
        if not entities:
            return 0

        if self.use_neo4j:
            return self._add_entities_neo4j(entities)
        return self._add_entities_nx(entities)

    def add_relationships(self, relationships: list[dict]) -> int:
        """Add relationship edges to the graph."""
        if not relationships:
            return 0

        if self.use_neo4j:
            return self._add_relationships_neo4j(relationships)
        return self._add_relationships_nx(relationships)

    def query_entities(
        self,
        entities: list[str],
        hop_depth: int = 2,
        relationship_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query relationships around given entities."""
        if self.use_neo4j:
            return self._query_neo4j(entities, hop_depth, relationship_types, limit)
        return self._query_nx(entities, hop_depth, relationship_types, limit)

    def get_entity_context(
        self, entities: list[str], limit: int = 10
    ) -> list[dict]:
        """Get textual context stored on entity nodes."""
        if self.use_neo4j:
            return self._get_context_neo4j(entities, limit)
        return self._get_context_nx(entities, limit)

    def get_all_entities(self) -> list[dict]:
        """Get all entities in the graph."""
        if self.use_neo4j:
            with self._driver.session() as session:
                result = session.run("MATCH (n) RETURN n.name AS name, n.type AS type, labels(n) AS labels LIMIT 100")
                return [{"name": r["name"], "type": r["type"]} for r in result]
        return [
            {"name": node, "type": data.get("type", "unknown"), "description": data.get("description", "")}
            for node, data in self._nx_graph.nodes(data=True)
        ]

    def get_all_relationships(self) -> list[dict]:
        """Get all relationships in the graph."""
        if self.use_neo4j:
            with self._driver.session() as session:
                result = session.run(
                    "MATCH (a)-[r]->(b) RETURN a.name AS source, type(r) AS rel, "
                    "b.name AS target LIMIT 100"
                )
                return [{"source": r["source"], "relationship": r["rel"], "target": r["target"]} for r in result]
        return [
            {"source": u, "relationship": data.get("type", "related_to"), "target": v}
            for u, v, data in self._nx_graph.edges(data=True)
        ]

    def count(self) -> dict[str, int]:
        """Return entity and relationship counts."""
        if self.use_neo4j:
            try:
                with self._driver.session() as session:
                    entities = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                    rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                    return {"entities": entities, "relationships": rels}
            except Exception:
                return {"entities": 0, "relationships": 0}
        return {
            "entities": self._nx_graph.number_of_nodes(),
            "relationships": self._nx_graph.number_of_edges(),
        }

    def clear(self) -> None:
        """Clear all data from the graph."""
        if self.use_neo4j:
            with self._driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
        else:
            self._nx_graph.clear()

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    # ── Neo4j implementations ────────────────────────────────────────────

    def _add_entities_neo4j(self, entities: list[dict]) -> int:
        count = 0
        with self._driver.session() as session:
            for e in entities:
                name = e.get("name", "")
                etype = e.get("type", "Concept")
                desc = e.get("description", "")
                source = e.get("source", "")
                if not name:
                    continue
                session.run(
                    f"MERGE (n:{etype} {{name: $name}}) "
                    "SET n.description = $desc, n.source = $source",
                    name=name, desc=desc, source=source,
                )
                count += 1
        return count

    def _add_relationships_neo4j(self, relationships: list[dict]) -> int:
        count = 0
        with self._driver.session() as session:
            for r in relationships:
                source = r.get("source", "")
                target = r.get("target", "")
                rel_type = r.get("relationship", "related_to").upper().replace(" ", "_")
                source_doc = r.get("source_doc", "")
                if not source or not target:
                    continue
                session.run(
                    "MATCH (a {name: $source}), (b {name: $target}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    "SET r.source_doc = $source_doc",
                    source=source, target=target, source_doc=source_doc,
                )
                count += 1
        return count

    def _query_neo4j(
        self, entities: list[str], hop_depth: int,
        rel_types: list[str] | None, limit: int,
    ) -> list[dict]:
        results = []
        with self._driver.session() as session:
            for entity in entities:
                query = (
                    "MATCH (a {name: $entity})-[r*1.." + str(hop_depth) + "]->(b) "
                    "RETURN a.name AS source, "
                    "last(r).type AS relationship, "
                    "b.name AS target, "
                    "b.source AS source_doc "
                    f"LIMIT {limit}"
                )
                try:
                    for record in session.run(query, entity=entity):
                        results.append({
                            "source": record["source"],
                            "relationship": record["relationship"] or "related_to",
                            "target": record["target"],
                            "source_doc": record.get("source_doc"),
                        })
                except Exception as e:
                    logger.debug(f"Neo4j query error: {e}")
        return results

    def _get_context_neo4j(self, entities: list[str], limit: int) -> list[dict]:
        results = []
        with self._driver.session() as session:
            for entity in entities:
                r = session.run(
                    "MATCH (n {name: $entity}) "
                    "RETURN n.name AS name, n.description AS desc, n.source AS source "
                    f"LIMIT {limit}",
                    entity=entity,
                ).single()
                if r:
                    results.append({
                        "id": r["name"],
                        "content": r.get("desc") or r["name"],
                        "source": r.get("source", "knowledge_graph"),
                        "score": 0.8,
                    })
        return results

    # ── NetworkX implementations ─────────────────────────────────────────

    def _add_entities_nx(self, entities: list[dict]) -> int:
        count = 0
        for e in entities:
            name = e.get("name", "")
            if not name:
                continue
            self._nx_graph.add_node(
                name,
                type=e.get("type", "Concept"),
                description=e.get("description", ""),
                source=e.get("source", ""),
            )
            count += 1
        return count

    def _add_relationships_nx(self, relationships: list[dict]) -> int:
        count = 0
        for r in relationships:
            source = r.get("source", "")
            target = r.get("target", "")
            if not source or not target:
                continue
            self._nx_graph.add_edge(
                source, target,
                type=r.get("relationship", "related_to"),
                source_doc=r.get("source_doc", ""),
            )
            count += 1
        return count

    def _query_nx(
        self, entities: list[str], hop_depth: int,
        rel_types: list[str] | None, limit: int,
    ) -> list[dict]:
        import networkx as nx
        results = []
        for entity in entities:
            if entity not in self._nx_graph:
                continue
            # BFS up to hop_depth
            visited = set()
            frontier = {entity}
            for _ in range(hop_depth):
                next_frontier = set()
                for node in frontier:
                    for _, neighbor, data in self._nx_graph.out_edges(node, data=True):
                        if neighbor not in visited:
                            rel_type = data.get("type", "related_to")
                            if rel_types and rel_type not in rel_types:
                                continue
                            results.append({
                                "source": node,
                                "relationship": rel_type,
                                "target": neighbor,
                                "source_doc": data.get("source_doc"),
                            })
                            next_frontier.add(neighbor)
                            if len(results) >= limit:
                                return results
                visited.update(frontier)
                frontier = next_frontier
                if not frontier:
                    break
        return results[:limit]

    def _get_context_nx(self, entities: list[str], limit: int) -> list[dict]:
        results = []
        for entity in entities:
            if entity in self._nx_graph:
                data = self._nx_graph.nodes[entity]
                results.append({
                    "id": entity,
                    "content": data.get("description", entity),
                    "source": data.get("source", "knowledge_graph"),
                    "score": 0.8,
                })
        return results[:limit]
