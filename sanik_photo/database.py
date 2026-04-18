from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import DuplicateItem, PhotoRecord


APP_DIR = Path.home() / ".sanik_photo"
DEFAULT_DB_PATH = APP_DIR / "library.sqlite3"


class PhotoDatabase:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.connection.close()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_root TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                extension TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                modified_at REAL NOT NULL,
                sha256 TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                perceptual_hash TEXT,
                sharpness_score REAL,
                lighting_score REAL,
                composition_score REAL,
                expression_score REAL,
                people_score REAL,
                scenery_score REAL,
                face_count INTEGER,
                quality_score REAL,
                user_rating INTEGER,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS file_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER,
                action TEXT NOT NULL,
                source_path TEXT NOT NULL,
                target_path TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(photo_id) REFERENCES photos(id)
            );

            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS photo_people (
                photo_id INTEGER NOT NULL,
                person_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(photo_id, person_id),
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE,
                FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photo_notes (
                photo_id INTEGER PRIMARY KEY,
                caption TEXT,
                suggested_path TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photo_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._ensure_column("photos", "library_root", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("photos", "width", "INTEGER")
        self._ensure_column("photos", "height", "INTEGER")
        self._ensure_column("photos", "perceptual_hash", "TEXT")
        self._ensure_column("photos", "sharpness_score", "REAL")
        self._ensure_column("photos", "lighting_score", "REAL")
        self._ensure_column("photos", "composition_score", "REAL")
        self._ensure_column("photos", "expression_score", "REAL")
        self._ensure_column("photos", "people_score", "REAL")
        self._ensure_column("photos", "scenery_score", "REAL")
        self._ensure_column("photos", "face_count", "INTEGER")
        self._ensure_column("photos", "quality_score", "REAL")
        self._ensure_column("photos", "user_rating", "INTEGER")
        self._ensure_column("photos", "is_deleted", "INTEGER NOT NULL DEFAULT 0")
        self.connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_photos_sha256 ON photos(sha256);
            CREATE INDEX IF NOT EXISTS idx_photos_perceptual_hash ON photos(perceptual_hash);
            CREATE INDEX IF NOT EXISTS idx_photos_path ON photos(path);
            CREATE INDEX IF NOT EXISTS idx_photos_library_root ON photos(library_root);
            CREATE INDEX IF NOT EXISTS idx_photo_people_person_id ON photo_people(person_id);
            """
        )
        self.connection.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        rows = self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        if column not in {str(row["name"]) for row in rows}:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def upsert_photo(self, photo: PhotoRecord) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO photos(
                library_root, path, filename, extension, file_size, modified_at, sha256,
                width, height, perceptual_hash, sharpness_score, lighting_score,
                composition_score, expression_score, people_score, scenery_score,
                face_count, quality_score, user_rating, is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                library_root=excluded.library_root,
                filename=excluded.filename,
                extension=excluded.extension,
                file_size=excluded.file_size,
                modified_at=excluded.modified_at,
                sha256=excluded.sha256,
                width=excluded.width,
                height=excluded.height,
                perceptual_hash=excluded.perceptual_hash,
                sharpness_score=excluded.sharpness_score,
                lighting_score=excluded.lighting_score,
                composition_score=excluded.composition_score,
                expression_score=excluded.expression_score,
                people_score=excluded.people_score,
                scenery_score=excluded.scenery_score,
                face_count=excluded.face_count,
                quality_score=excluded.quality_score,
                user_rating=COALESCE(photos.user_rating, excluded.user_rating),
                is_deleted=0,
                scanned_at=CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                photo.library_root,
                photo.path,
                photo.filename,
                photo.extension,
                photo.file_size,
                photo.modified_at,
                photo.sha256,
                photo.width,
                photo.height,
                photo.perceptual_hash,
                photo.sharpness_score,
                photo.lighting_score,
                photo.composition_score,
                photo.expression_score,
                photo.people_score,
                photo.scenery_score,
                photo.face_count,
                photo.quality_score,
                photo.user_rating,
                1 if photo.is_deleted else 0,
            ),
        )
        row = cursor.fetchone()
        self.connection.commit()
        return int(row["id"])

    def upsert_photos(self, photos: Iterable[PhotoRecord]) -> int:
        count = 0
        for photo in photos:
            self.upsert_photo(photo)
            count += 1
        return count

    def list_photos(
        self,
        limit: int = 500,
        library_root: str | None = None,
        paths: set[str] | None = None,
    ) -> list[PhotoRecord]:
        where, params = self._scope_where(library_root=library_root, paths=paths)
        rows = self.connection.execute(
            f"""
            SELECT id, path, filename, extension, file_size, modified_at, sha256,
                   library_root, width, height, perceptual_hash, sharpness_score,
                   lighting_score, composition_score, expression_score, people_score,
                   scenery_score, face_count, quality_score, user_rating, is_deleted
            FROM photos
            {where}
            ORDER BY modified_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [self._photo_from_row(row) for row in rows]

    def duplicate_hashes(
        self,
        library_root: str | None = None,
        paths: set[str] | None = None,
    ) -> list[str]:
        where, params = self._scope_where(library_root=library_root, paths=paths)
        rows = self.connection.execute(
            f"""
            SELECT sha256
            FROM photos
            {where}
            GROUP BY sha256
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            """,
            params,
        ).fetchall()
        return [str(row["sha256"]) for row in rows]

    def duplicate_items_for_hash(
        self,
        sha256: str,
        library_root: str | None = None,
        paths: set[str] | None = None,
    ) -> list[DuplicateItem]:
        where, params = self._scope_where(
            library_root=library_root,
            paths=paths,
            extra_clause="sha256 = ?",
            extra_params=(sha256,),
        )
        rows = self.connection.execute(
            f"""
            SELECT id, library_root, path, filename, file_size, modified_at, sha256,
                   sharpness_score, lighting_score, composition_score,
                   expression_score, people_score, scenery_score, face_count,
                   quality_score, user_rating
            FROM photos
            {where}
            ORDER BY COALESCE(quality_score, -1) DESC, file_size DESC, modified_at ASC, path ASC
            """,
            params,
        ).fetchall()
        items: list[DuplicateItem] = []
        for index, row in enumerate(rows):
            items.append(
                DuplicateItem(
                    photo_id=int(row["id"]),
                    library_root=str(row["library_root"]),
                    path=str(row["path"]),
                    filename=str(row["filename"]),
                    file_size=int(row["file_size"]),
                    modified_at=float(row["modified_at"]),
                    sha256=str(row["sha256"]),
                    quality_score=float(row["quality_score"]) if row["quality_score"] is not None else None,
                    sharpness_score=float(row["sharpness_score"]) if row["sharpness_score"] is not None else None,
                    lighting_score=float(row["lighting_score"]) if row["lighting_score"] is not None else None,
                    composition_score=float(row["composition_score"]) if row["composition_score"] is not None else None,
                    expression_score=float(row["expression_score"]) if row["expression_score"] is not None else None,
                    people_score=float(row["people_score"]) if row["people_score"] is not None else None,
                    scenery_score=float(row["scenery_score"]) if row["scenery_score"] is not None else None,
                    face_count=int(row["face_count"]) if row["face_count"] is not None else None,
                    user_rating=int(row["user_rating"]) if row["user_rating"] is not None else None,
                    suggested_action="keep" if index == 0 else "review",
                )
            )
        return items

    def photos_with_perceptual_hash(
        self,
        library_root: str | None = None,
        paths: set[str] | None = None,
    ) -> list[PhotoRecord]:
        where, params = self._scope_where(
            library_root=library_root,
            paths=paths,
            extra_clause="perceptual_hash IS NOT NULL",
        )
        rows = self.connection.execute(
            f"""
            SELECT id, path, filename, extension, file_size, modified_at, sha256,
                   library_root, width, height, perceptual_hash, sharpness_score,
                   lighting_score, composition_score, expression_score, people_score,
                   scenery_score, face_count, quality_score, user_rating, is_deleted
            FROM photos
            {where}
            ORDER BY modified_at ASC, path ASC
            """,
            params,
        ).fetchall()
        return [self._photo_from_row(row) for row in rows]

    def list_library_roots(self) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT library_root
            FROM photos
            WHERE library_root != '' AND is_deleted = 0
            GROUP BY library_root
            ORDER BY library_root ASC
            """
        ).fetchall()
        return [str(row["library_root"]) for row in rows]

    def get_photo(self, photo_id: int) -> PhotoRecord | None:
        row = self.connection.execute(
            """
            SELECT id, path, filename, extension, file_size, modified_at, sha256,
                   library_root, width, height, perceptual_hash, sharpness_score,
                   lighting_score, composition_score, expression_score, people_score,
                   scenery_score, face_count, quality_score, user_rating, is_deleted
            FROM photos
            WHERE id = ? AND is_deleted = 0
            """,
            (photo_id,),
        ).fetchone()
        return self._photo_from_row(row) if row else None

    def get_photo_id_by_path(self, path: str) -> int | None:
        row = self.connection.execute("SELECT id FROM photos WHERE path = ? AND is_deleted = 0", (path,)).fetchone()
        return int(row["id"]) if row else None

    def add_people_to_photo(self, photo_id: int, names: list[str]) -> None:
        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue
            cursor = self.connection.execute(
                """
                INSERT INTO people(name)
                VALUES (?)
                ON CONFLICT(name) DO UPDATE SET name=excluded.name
                RETURNING id
                """,
                (name,),
            )
            person_id = int(cursor.fetchone()["id"])
            self.connection.execute(
                """
                INSERT OR IGNORE INTO photo_people(photo_id, person_id)
                VALUES (?, ?)
                """,
                (photo_id, person_id),
            )
        self.connection.commit()

    def people_for_photo(self, photo_id: int) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT people.name
            FROM people
            JOIN photo_people ON photo_people.person_id = people.id
            WHERE photo_people.photo_id = ?
            ORDER BY people.name ASC
            """,
            (photo_id,),
        ).fetchall()
        return [str(row["name"]) for row in rows]

    def save_photo_note(self, photo_id: int, caption: str, suggested_path: str) -> None:
        self.connection.execute(
            """
            INSERT INTO photo_notes(photo_id, caption, suggested_path, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(photo_id) DO UPDATE SET
                caption=excluded.caption,
                suggested_path=excluded.suggested_path,
                updated_at=CURRENT_TIMESTAMP
            """,
            (photo_id, caption, suggested_path),
        )
        self.connection.commit()

    def note_for_photo(self, photo_id: int) -> tuple[str, str]:
        row = self.connection.execute(
            """
            SELECT caption, suggested_path
            FROM photo_notes
            WHERE photo_id = ?
            """,
            (photo_id,),
        ).fetchone()
        if not row:
            return "", ""
        return str(row["caption"] or ""), str(row["suggested_path"] or "")

    def set_photo_rating(self, photo_id: int, rating: int, note: str | None = None) -> None:
        if rating not in {-1, 0, 1}:
            raise ValueError("rating must be -1, 0, or 1")
        self.connection.execute(
            "UPDATE photos SET user_rating = ? WHERE id = ?",
            (rating, photo_id),
        )
        self.connection.execute(
            """
            INSERT INTO photo_feedback(photo_id, rating, note)
            VALUES (?, ?, ?)
            """,
            (photo_id, rating, note),
        )
        self.connection.commit()

    def mark_photo_deleted(self, photo_id: int, target_path: str, note: str | None = None) -> None:
        photo = self.get_photo(photo_id)
        if photo is None:
            return
        target = Path(target_path)
        self.connection.execute(
            """
            UPDATE photos
            SET path = ?, filename = ?, user_rating = -1, is_deleted = 1
            WHERE id = ?
            """,
            (str(target), target.name, photo_id),
        )
        self.connection.execute(
            """
            INSERT INTO photo_feedback(photo_id, rating, note)
            VALUES (?, ?, ?)
            """,
            (photo_id, -1, note or "Deleted from app"),
        )
        self.connection.execute(
            """
            INSERT INTO file_actions(photo_id, action, source_path, target_path)
            VALUES (?, ?, ?, ?)
            """,
            (photo_id, "move_to_deleted", photo.path, str(target)),
        )
        self.connection.commit()

    def list_rated_photos(self) -> list[PhotoRecord]:
        rows = self.connection.execute(
            """
            SELECT id, path, filename, extension, file_size, modified_at, sha256,
                   library_root, width, height, perceptual_hash, sharpness_score,
                   lighting_score, composition_score, expression_score, people_score,
                   scenery_score, face_count, quality_score, user_rating, is_deleted
            FROM photos
            WHERE user_rating IS NOT NULL
            ORDER BY modified_at DESC
            """
        ).fetchall()
        return [self._photo_from_row(row) for row in rows]

    def save_setting(self, key: str, value: dict) -> None:
        self.connection.execute(
            """
            INSERT INTO app_settings(key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, json.dumps(value, sort_keys=True)),
        )
        self.connection.commit()

    def load_setting(self, key: str) -> dict | None:
        row = self.connection.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        return json.loads(str(row["value"]))

    def clear_library(self, library_root: str | None = None) -> int:
        if library_root:
            cursor = self.connection.execute("DELETE FROM photos WHERE library_root = ?", (library_root,))
        else:
            cursor = self.connection.execute("DELETE FROM photos")
        self.connection.commit()
        return int(cursor.rowcount)

    def remove_missing_files(self, library_root: str | None = None) -> int:
        photos = self.list_photos(limit=1_000_000, library_root=library_root)
        removed = 0
        for photo in photos:
            if Path(photo.path).exists():
                continue
            self.connection.execute("DELETE FROM photos WHERE id = ?", (photo.id,))
            self.connection.execute(
                """
                INSERT INTO file_actions(photo_id, action, source_path, target_path)
                VALUES (?, ?, ?, ?)
                """,
                (photo.id, "remove_missing_index_record", photo.path, None),
            )
            removed += 1
        self.connection.commit()
        return removed

    def log_file_action(
        self,
        photo_id: int | None,
        action: str,
        source_path: str,
        target_path: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO file_actions(photo_id, action, source_path, target_path)
            VALUES (?, ?, ?, ?)
            """,
            (photo_id, action, source_path, target_path),
        )
        self.connection.commit()

    @staticmethod
    def _scope_where(
        library_root: str | None = None,
        paths: set[str] | None = None,
        extra_clause: str | None = None,
        extra_params: tuple[object, ...] = (),
        include_deleted: bool = False,
    ) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = [] if include_deleted else ["is_deleted = 0"]
        params: list[object] = []
        if library_root:
            clauses.append("library_root = ?")
            params.append(library_root)
        if paths is not None:
            if not paths:
                clauses.append("0")
            else:
                placeholders = ", ".join("?" for _ in paths)
                clauses.append(f"path IN ({placeholders})")
                params.extend(sorted(paths))
        if extra_clause:
            clauses.append(extra_clause)
            params.extend(extra_params)
        if not clauses:
            return "", tuple(params)
        return "WHERE " + " AND ".join(clauses), tuple(params)

    @staticmethod
    def _photo_from_row(row: sqlite3.Row) -> PhotoRecord:
        return PhotoRecord(
            id=int(row["id"]),
            library_root=str(row["library_root"]),
            path=str(row["path"]),
            filename=str(row["filename"]),
            extension=str(row["extension"]),
            file_size=int(row["file_size"]),
            modified_at=float(row["modified_at"]),
            sha256=str(row["sha256"]),
            width=int(row["width"]) if row["width"] is not None else None,
            height=int(row["height"]) if row["height"] is not None else None,
            perceptual_hash=str(row["perceptual_hash"]) if row["perceptual_hash"] else None,
            sharpness_score=float(row["sharpness_score"]) if row["sharpness_score"] is not None else None,
            lighting_score=float(row["lighting_score"]) if row["lighting_score"] is not None else None,
            composition_score=float(row["composition_score"]) if row["composition_score"] is not None else None,
            expression_score=float(row["expression_score"]) if row["expression_score"] is not None else None,
            people_score=float(row["people_score"]) if row["people_score"] is not None else None,
            scenery_score=float(row["scenery_score"]) if row["scenery_score"] is not None else None,
            face_count=int(row["face_count"]) if row["face_count"] is not None else None,
            quality_score=float(row["quality_score"]) if row["quality_score"] is not None else None,
            user_rating=int(row["user_rating"]) if row["user_rating"] is not None else None,
            is_deleted=bool(row["is_deleted"]) if "is_deleted" in row.keys() else False,
        )
