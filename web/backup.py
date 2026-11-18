"""Write a consistent backup of the app SQLite database."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3


def backup(source, destination):
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as origin:
        destination.touch(mode=0o600, exist_ok=False)
        try:
            with closing(sqlite3.connect(destination)) as copy:
                origin.backup(copy)
                if copy.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise RuntimeError("El respaldo no pasó la comprobación de integridad.")
        except (OSError, sqlite3.Error, RuntimeError):
            destination.unlink(missing_ok=True)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    backup(Path(os.environ.get("CORTE_DB", "corte-sk2.sqlite3")), args.destination)
