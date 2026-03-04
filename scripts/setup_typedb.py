#!/usr/bin/env python3
"""Initialize TypeDB database and load schema."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.loaders import TypeDBLoader


def main():
    """Set up TypeDB database."""
    print("Setting up TypeDB database...")

    loader = TypeDBLoader()

    if not loader.connect():
        print("Failed to connect to TypeDB.")
        print(f"Make sure TypeDB is running at {settings.typedb_address}")
        print("\nTo start TypeDB with Docker:")
        print("  docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest")
        return False

    schema_path = Path(__file__).parent.parent / "schema" / "ican_schema.tql"

    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        return False

    if loader.setup_database(schema_path):
        print(f"Database '{settings.typedb_database}' created successfully!")
        print("Schema loaded.")
        loader.disconnect()
        return True
    else:
        print("Failed to set up database.")
        loader.disconnect()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
