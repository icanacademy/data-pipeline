"""
Vector Store Service for Semantic Search

Uses ChromaDB for vector storage and sentence-transformers for embeddings.
Enables semantic/meaning-based search across all ICAN data.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from loguru import logger


class VectorStore:
    """Vector store for semantic search across ICAN data."""

    def __init__(self, persist_dir: Optional[str] = None):
        """Initialize the vector store."""
        self.persist_dir = persist_dir or str(Path.home() / ".ican-data-center" / "vector_db")
        self.model_name = "all-MiniLM-L6-v2"  # Fast, good quality, 384 dimensions
        self.model: Optional[SentenceTransformer] = None
        self.client: Optional[chromadb.Client] = None
        self.collection = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize the embedding model and ChromaDB client."""
        try:
            logger.info("Initializing vector store...")

            # Load embedding model
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)

            # Initialize ChromaDB with persistence
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_dir)

            # Get or create the main collection
            self.collection = self.client.get_or_create_collection(
                name="ican_entities",
                metadata={"description": "ICAN Data Center entities for semantic search"}
            )

            self._initialized = True
            logger.info(f"Vector store initialized. Collection has {self.collection.count()} documents.")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            return False

    def is_ready(self) -> bool:
        """Check if vector store is ready."""
        return self._initialized and self.model is not None and self.collection is not None

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if not self.model:
            raise RuntimeError("Vector store not initialized")
        return self.model.encode(text).tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not self.model:
            raise RuntimeError("Vector store not initialized")
        return self.model.encode(texts).tolist()

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> int:
        """Add documents to the vector store."""
        if not self.is_ready():
            raise RuntimeError("Vector store not initialized")

        # Generate embeddings
        embeddings = self.embed_texts(documents)

        # Add to collection
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        return len(documents)

    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across all indexed documents.

        Args:
            query: Search query (natural language)
            n_results: Number of results to return
            filter_type: Optional filter by entity type (teacher, student, app, etc.)

        Returns:
            List of search results with metadata and similarity scores
        """
        if not self.is_ready():
            return []

        # Build where filter if type specified
        where_filter = {"type": filter_type} if filter_type else None

        # Search
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 / (1 + distance)  # Convert to 0-1 similarity

                formatted.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "similarity": round(similarity, 4),
                    "distance": round(distance, 4)
                })

        return formatted

    def clear(self):
        """Clear all documents from the collection."""
        if self.client and self.collection:
            self.client.delete_collection("ican_entities")
            self.collection = self.client.get_or_create_collection(
                name="ican_entities",
                metadata={"description": "ICAN Data Center entities for semantic search"}
            )
            logger.info("Vector store cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        if not self.is_ready():
            return {"status": "not_initialized", "count": 0}

        return {
            "status": "ready",
            "count": self.collection.count(),
            "model": self.model_name,
            "persist_dir": self.persist_dir
        }

    def index_all_data(self) -> Dict[str, int]:
        """
        Index all data from connected databases for semantic search.
        Returns counts of indexed items by type.
        """
        if not self.is_ready():
            raise RuntimeError("Vector store not initialized")

        from ..extractors import PostgreSQLExtractor

        counts = {
            "teachers": 0,
            "students": 0,
            "employees": 0,
            "apps": 0,
            "interviews": 0,
            "assessments": 0,
            "coaching": 0
        }

        documents = []
        metadatas = []
        ids = []

        try:
            # Index teachers from PostgreSQL
            extractor = PostgreSQLExtractor()
            if extractor.connect():
                extractor.cursor.execute("""
                    SELECT DISTINCT ON (name) id, name, is_active
                    FROM teachers WHERE name IS NOT NULL
                    ORDER BY name, created_at DESC
                """)
                for row in extractor.cursor.fetchall():
                    doc_id = f"teacher_{row['id']}"
                    text = f"Teacher: {row['name']}"
                    documents.append(text)
                    metadatas.append({
                        "type": "teacher",
                        "name": row["name"],
                        "pg_id": row["id"],
                        "url": f"/view/teacher/{row['id']}"
                    })
                    ids.append(doc_id)
                    counts["teachers"] += 1

                # Index students
                extractor.cursor.execute("""
                    SELECT DISTINCT ON (name) id, name, student_id, grade, school
                    FROM students WHERE name IS NOT NULL
                    ORDER BY name, created_at DESC
                """)
                for row in extractor.cursor.fetchall():
                    doc_id = f"student_{row['id']}"
                    parts = [f"Student: {row['name']}"]
                    if row.get("grade"):
                        parts.append(f"Grade {row['grade']}")
                    if row.get("school"):
                        parts.append(row["school"])
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "student",
                        "name": row["name"],
                        "pg_id": row["id"],
                        "grade": row.get("grade") or "",
                        "school": row.get("school") or "",
                        "url": f"/view/student/{row['id']}"
                    })
                    ids.append(doc_id)
                    counts["students"] += 1

                extractor.disconnect()

            # Index employees from coaching database
            coaching_db = Path.home() / "academy-coaching-app" / "coaching.db"
            if coaching_db.exists():
                conn = sqlite3.connect(str(coaching_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, first_name, last_name, email, position
                    FROM employees WHERE first_name IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"employee_{row[0]}"
                    name = f"{row[1]} {row[2]}"
                    parts = [f"Employee: {name}"]
                    if row[4]:
                        parts.append(f"Position: {row[4]}")
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "employee",
                        "name": name,
                        "email": row[3] or "",
                        "position": row[4] or "",
                        "source": "coaching"
                    })
                    ids.append(doc_id)
                    counts["employees"] += 1

                # Index coaching records
                cursor.execute("""
                    SELECT cr.id, e.first_name, e.last_name, cr.issue_description, cr.created_at
                    FROM coaching_records cr
                    JOIN employees e ON cr.employee_id = e.id
                    WHERE cr.issue_description IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"coaching_{row[0]}"
                    name = f"{row[1]} {row[2]}"
                    text = f"Coaching record for {name}: {row[3][:200] if row[3] else ''}"

                    documents.append(text)
                    metadatas.append({
                        "type": "coaching",
                        "employee": name,
                        "date": str(row[4]) if row[4] else "",
                        "source": "coaching"
                    })
                    ids.append(doc_id)
                    counts["coaching"] += 1

                conn.close()

            # Index apps from marketplace
            marketplace_db = Path.home() / "ican-app-marketplace" / "marketplace.db"
            if marketplace_db.exists():
                conn = sqlite3.connect(str(marketplace_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, category, teacher_name, student_levels
                    FROM apps WHERE title IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"app_{row[0]}"
                    parts = [f"App: {row[1]}"]
                    if row[2]:
                        parts.append(row[2][:300])
                    if row[3]:
                        parts.append(f"Category: {row[3]}")
                    if row[5]:
                        parts.append(f"Levels: {row[5]}")
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "app",
                        "name": row[1],
                        "description": row[2][:100] if row[2] else "",
                        "category": row[3] or "",
                        "teacher": row[4] or "",
                        "source": "marketplace"
                    })
                    ids.append(doc_id)
                    counts["apps"] += 1

                conn.close()

            # Index interviews
            interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
            if interviews_db.exists():
                conn = sqlite3.connect(str(interviews_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, student_name, interviewer, interview_type, date, report_text
                    FROM interviews WHERE student_name IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"interview_{row[0]}"
                    parts = [f"Interview: {row[1]}"]
                    if row[2]:
                        parts.append(f"Interviewer: {row[2]}")
                    if row[3]:
                        parts.append(f"Type: {row[3]}")
                    if row[5]:
                        parts.append(row[5][:200])
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "interview",
                        "name": row[1],
                        "interviewer": row[2] or "",
                        "interview_type": row[3] or "",
                        "date": row[4] or "",
                        "source": "interviews"
                    })
                    ids.append(doc_id)
                    counts["interviews"] += 1

                conn.close()

            # Index demo assessments
            demo_db = Path.home() / "ican-demo-assessment" / "demo_assessments.db"
            if demo_db.exists():
                conn = sqlite3.connect(str(demo_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, applicant_name, assessor_name, topic, final_result,
                           additional_comments, ai_feedback
                    FROM assessments WHERE applicant_name IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"assessment_{row[0]}"
                    parts = [f"Demo Assessment: {row[1]}"]
                    if row[2]:
                        parts.append(f"Assessor: {row[2]}")
                    if row[3]:
                        parts.append(f"Topic: {row[3]}")
                    if row[4]:
                        parts.append(f"Result: {row[4]}")
                    if row[5]:
                        parts.append(row[5][:150])
                    if row[6]:
                        parts.append(f"AI Feedback: {row[6][:150]}")
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "assessment",
                        "name": row[1],
                        "assessor": row[2] or "",
                        "topic": row[3] or "",
                        "result": row[4] or "",
                        "source": "demo_assessments"
                    })
                    ids.append(doc_id)
                    counts["assessments"] += 1

                conn.close()

            # Index level tests from student_analytics
            level_tests_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "student_analytics.db"
            if level_tests_db.exists():
                conn = sqlite3.connect(str(level_tests_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, student_name, student_id, grade, test_level,
                           grammar_score, grammar_total, reading_score, reading_total,
                           vocabulary_score, vocabulary_total, total_score, total_possible,
                           ai_recommendation
                    FROM level_tests WHERE student_name IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"level_test_{row[0]}"
                    parts = [f"Level Test: {row[1]}"]
                    if row[3]:
                        parts.append(f"Grade: {row[3]}")
                    if row[4]:
                        parts.append(f"Level: {row[4]}")
                    if row[11] and row[12]:
                        parts.append(f"Score: {row[11]}/{row[12]}")
                    if row[13]:
                        parts.append(f"AI Recommendation: {row[13][:200]}")
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "level_test",
                        "name": row[1],
                        "student_id": row[2] or "",
                        "grade": row[3] or "",
                        "test_level": row[4] or "",
                        "total_score": row[11],
                        "source": "student_analytics"
                    })
                    ids.append(doc_id)
                    counts["level_tests"] = counts.get("level_tests", 0) + 1

                conn.close()

            # Index classes from ican_classes
            classes_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "ican_classes.db"
            if classes_db.exists():
                conn = sqlite3.connect(str(classes_db))
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.name, c.description, c.min_grade_level, c.max_grade_level,
                           c.skills_focus, c.learning_objectives, cc.name as category
                    FROM classes c
                    LEFT JOIN class_categories cc ON c.category_id = cc.id
                    WHERE c.name IS NOT NULL
                """)
                for row in cursor.fetchall():
                    doc_id = f"class_{row[0]}"
                    parts = [f"Class: {row[1]}"]
                    if row[2]:
                        parts.append(row[2][:200])
                    if row[3] and row[4]:
                        parts.append(f"Grades: {row[3]} to {row[4]}")
                    if row[7]:
                        parts.append(f"Category: {row[7]}")
                    if row[5]:
                        parts.append(f"Skills: {row[5][:100]}")
                    text = " - ".join(parts)

                    documents.append(text)
                    metadatas.append({
                        "type": "class",
                        "name": row[1],
                        "description": row[2][:100] if row[2] else "",
                        "grade_range": f"{row[3]} - {row[4]}" if row[3] and row[4] else "",
                        "category": row[7] or "",
                        "source": "ican_classes"
                    })
                    ids.append(doc_id)
                    counts["classes"] = counts.get("classes", 0) + 1

                conn.close()

            # Clear existing and add new documents
            if documents:
                logger.info(f"Indexing {len(documents)} documents...")
                self.clear()

                # Add in batches of 100
                batch_size = 100
                for i in range(0, len(documents), batch_size):
                    batch_docs = documents[i:i + batch_size]
                    batch_meta = metadatas[i:i + batch_size]
                    batch_ids = ids[i:i + batch_size]
                    self.add_documents(batch_docs, batch_meta, batch_ids)
                    logger.info(f"Indexed batch {i // batch_size + 1}/{(len(documents) + batch_size - 1) // batch_size}")

            logger.info(f"Indexing complete: {counts}")
            return counts

        except Exception as e:
            logger.error(f"Error indexing data: {e}")
            raise


# Global instance
vector_store = VectorStore()
