"""TypeDB data loader."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from ..config import settings
from ..extractors.base import ExtractedEntity, ExtractedRelation, ExtractionResult
from ..transformers.entity_resolver import ResolvedEntity
from ..transformers.typedb_mapper import TypeDBMapper

try:
    from typedb.driver import TypeDB, SessionType, TransactionType
    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False


class TypeDBLoader:
    """Load data into TypeDB knowledge graph."""

    def __init__(self):
        self.driver = None
        self.mapper = TypeDBMapper()
        self.logger = logger.bind(component="typedb_loader")

    def connect(self) -> bool:
        """Connect to TypeDB server."""
        if not TYPEDB_AVAILABLE:
            self.logger.error("typedb-driver not installed")
            return False

        try:
            self.driver = TypeDB.core_driver(settings.typedb_address)
            self.logger.info(f"Connected to TypeDB at {settings.typedb_address}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to TypeDB: {e}")
            return False

    def disconnect(self) -> None:
        """Close TypeDB connection."""
        if self.driver:
            self.driver.close()
            self.logger.info("Disconnected from TypeDB")

    def setup_database(self, schema_path: Optional[Path] = None) -> bool:
        """Create database and load schema."""
        if not self.driver:
            self.logger.error("Not connected to TypeDB")
            return False

        try:
            # Create database if it doesn't exist
            databases = self.driver.databases.all()
            db_names = [db.name for db in databases]

            if settings.typedb_database not in db_names:
                self.driver.databases.create(settings.typedb_database)
                self.logger.info(f"Created database: {settings.typedb_database}")

            # Load schema
            if schema_path and schema_path.exists():
                schema_content = schema_path.read_text()

                with self.driver.session(
                    settings.typedb_database, SessionType.SCHEMA
                ) as session:
                    with session.transaction(TransactionType.WRITE) as tx:
                        tx.query.define(schema_content)
                        tx.commit()

                self.logger.info(f"Loaded schema from {schema_path}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to setup database: {e}")
            return False

    def load_entities(
        self, entities: List[ExtractedEntity], batch_size: int = 50
    ) -> int:
        """Load extracted entities into TypeDB."""
        if not self.driver:
            self.logger.error("Not connected to TypeDB")
            return 0

        loaded = 0

        try:
            with self.driver.session(
                settings.typedb_database, SessionType.DATA
            ) as session:
                # Process in batches
                for i in range(0, len(entities), batch_size):
                    batch = entities[i : i + batch_size]

                    with session.transaction(TransactionType.WRITE) as tx:
                        for entity in batch:
                            try:
                                query = self.mapper.entity_to_insert(entity)
                                tx.query.insert(query)
                                loaded += 1
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to insert entity {entity.external_id}: {e}"
                                )

                        tx.commit()

                    self.logger.debug(
                        f"Loaded batch {i // batch_size + 1}, total: {loaded}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to load entities: {e}")

        self.logger.info(f"Loaded {loaded} entities")
        return loaded

    def load_resolved_entities(
        self, resolved: List[ResolvedEntity], batch_size: int = 50
    ) -> int:
        """Load resolved/merged entities into TypeDB."""
        if not self.driver:
            self.logger.error("Not connected to TypeDB")
            return 0

        loaded = 0

        try:
            with self.driver.session(
                settings.typedb_database, SessionType.DATA
            ) as session:
                for i in range(0, len(resolved), batch_size):
                    batch = resolved[i : i + batch_size]

                    with session.transaction(TransactionType.WRITE) as tx:
                        for entity in batch:
                            try:
                                query = self.mapper.resolved_entity_to_insert(entity)
                                tx.query.insert(query)
                                loaded += 1
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to insert resolved entity {entity.canonical_id}: {e}"
                                )

                        tx.commit()

        except Exception as e:
            self.logger.error(f"Failed to load resolved entities: {e}")

        self.logger.info(f"Loaded {loaded} resolved entities")
        return loaded

    def load_relations(
        self, relations: List[ExtractedRelation], batch_size: int = 50
    ) -> int:
        """Load extracted relations into TypeDB."""
        if not self.driver:
            self.logger.error("Not connected to TypeDB")
            return 0

        loaded = 0

        try:
            with self.driver.session(
                settings.typedb_database, SessionType.DATA
            ) as session:
                for i in range(0, len(relations), batch_size):
                    batch = relations[i : i + batch_size]

                    with session.transaction(TransactionType.WRITE) as tx:
                        for relation in batch:
                            try:
                                query = self.mapper.relation_to_insert(relation)
                                tx.query.insert(query)
                                loaded += 1
                            except Exception as e:
                                self.logger.warning(
                                    f"Failed to insert relation {relation.relation_type}: {e}"
                                )

                        tx.commit()

        except Exception as e:
            self.logger.error(f"Failed to load relations: {e}")

        self.logger.info(f"Loaded {loaded} relations")
        return loaded

    def load_extraction_result(self, result: ExtractionResult) -> dict:
        """Load a complete extraction result."""
        stats = {
            "entities_loaded": 0,
            "relations_loaded": 0,
            "errors": [],
        }

        if result.errors:
            stats["errors"].extend(result.errors)

        # Load entities first
        if result.entities:
            stats["entities_loaded"] = self.load_entities(result.entities)

        # Then load relations
        if result.relations:
            stats["relations_loaded"] = self.load_relations(result.relations)

        return stats

    def query(self, typeql: str) -> List[dict]:
        """Execute a TypeQL query and return results."""
        if not self.driver:
            self.logger.error("Not connected to TypeDB")
            return []

        results = []

        try:
            with self.driver.session(
                settings.typedb_database, SessionType.DATA
            ) as session:
                with session.transaction(TransactionType.READ) as tx:
                    answer = tx.query.get(typeql)

                    for concept_map in answer:
                        result = {}
                        for var in concept_map.variables():
                            concept = concept_map.get(var)
                            result[var] = self._concept_to_dict(concept)
                        results.append(result)

        except Exception as e:
            self.logger.error(f"Query failed: {e}")

        return results

    def _concept_to_dict(self, concept) -> dict:
        """Convert a TypeDB concept to a dictionary."""
        result = {"type": str(concept.get_type().get_label())}

        if concept.is_entity():
            result["id"] = concept.get_iid()
            # Get attributes
            result["attributes"] = {}
            for attr in concept.get_has():
                attr_type = str(attr.get_type().get_label())
                result["attributes"][attr_type] = attr.get_value()

        elif concept.is_attribute():
            result["value"] = concept.get_value()

        elif concept.is_relation():
            result["id"] = concept.get_iid()
            result["players"] = {}
            for role_type, players in concept.get_players_by_role_type().items():
                role_name = str(role_type.get_label())
                result["players"][role_name] = [
                    self._concept_to_dict(p) for p in players
                ]

        return result

    def get_stats(self) -> dict:
        """Get statistics about the knowledge graph."""
        stats = {}

        try:
            # Count entities by type
            entity_types = [
                "teacher",
                "student",
                "class-assignment",
                "attendance",
                "coaching-record",
                "demo-assessment",
                "interview-assessment",
                "student-report",
                "educational-app",
            ]

            for entity_type in entity_types:
                query = f"match $e isa {entity_type}; get $e; count;"
                result = self.query(query)
                if result:
                    stats[entity_type] = result[0].get("count", 0)

        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")

        return stats
