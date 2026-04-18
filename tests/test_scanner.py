from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from sanik_photo.database import PhotoDatabase
from sanik_photo.duplicate_finder import (
    find_exact_duplicate_groups,
    find_similar_photo_groups,
    hamming_distance,
)
from sanik_photo.scanner import scan_folder
from sanik_photo.models import PhotoRecord
from sanik_photo.image_export import resize_photos
from sanik_photo.organizer import caption_for_photo, suggested_organization_path
from sanik_photo.taste_model import load_taste_model, train_taste_model
from sanik_photo.top_picks import select_top_picks

try:
    from PIL import Image
except ImportError:
    Image = None


class ScannerTest(unittest.TestCase):
    def test_database_migrates_existing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "old.sqlite3"
            connection = sqlite3.connect(db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE photos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        path TEXT NOT NULL UNIQUE,
                        filename TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        modified_at REAL NOT NULL,
                        sha256 TEXT NOT NULL,
                        scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                connection.commit()
            finally:
                connection.close()

            db = PhotoDatabase(db_path)
            try:
                columns = {
                    row["name"]
                    for row in db.connection.execute("PRAGMA table_info(photos)").fetchall()
                }
            finally:
                db.close()

            self.assertIn("width", columns)
            self.assertIn("height", columns)
            self.assertIn("perceptual_hash", columns)

    def test_scan_and_find_exact_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.jpg").write_bytes(b"same image bytes")
            (root / "b.jpg").write_bytes(b"same image bytes")
            (root / "note.txt").write_text("ignore me")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                count = db.upsert_photos(scan_folder(root))
                groups = find_exact_duplicate_groups(db)
            finally:
                db.close()

            self.assertEqual(count, 2)
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0].items), 2)
            self.assertEqual(groups[0].items[0].suggested_action, "keep")

    def test_folder_scope_can_clear_one_library(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "a.jpg").write_bytes(b"first")
            (second / "b.jpg").write_bytes(b"second")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(first))
                db.upsert_photos(scan_folder(second))
                self.assertEqual(len(db.list_library_roots()), 2)

                cleared = db.clear_library(str(first.resolve()))
                remaining = db.list_photos(limit=10)
            finally:
                db.close()

            self.assertEqual(cleared, 1)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].library_root, str(second.resolve()))

    def test_people_tags_caption_and_suggested_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            event = root / "Birthday Party"
            event.mkdir()
            (event / "a.jpg").write_bytes(b"image")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(root))
                photo = db.list_photos(limit=1)[0]
                db.add_people_to_photo(int(photo.id), ["Deepak", "Anya"])
                people = db.people_for_photo(int(photo.id))
                caption = caption_for_photo(photo, people)
                suggested_path = suggested_organization_path(photo, people)
                db.save_photo_note(int(photo.id), caption, suggested_path)
                saved_caption, saved_path = db.note_for_photo(int(photo.id))
            finally:
                db.close()

            self.assertEqual(people, ["Anya", "Deepak"])
            self.assertIn("with Anya and Deepak", saved_caption)
            self.assertIn("People-Anya-Deepak", saved_path)
            self.assertIn("Birthday-Party", saved_path)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_top_picks_take_one_from_similar_group(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (240, 160), "white")
            for x in range(240):
                for y in range(160):
                    image.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
            image.save(root / "large.jpg", quality=95)
            image.resize((120, 80)).save(root / "small.jpg", quality=80)
            Image.new("RGB", (160, 160), "black").save(root / "other.jpg")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(root))
                picks = select_top_picks(db, count=2, library_root=str(root.resolve()))
            finally:
                db.close()

            picked_names = {photo.filename for photo in picks}
            self.assertEqual(len(picks), 2)
            self.assertEqual(len({"large.jpg", "small.jpg"} & picked_names), 1)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_top_picks_use_user_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            Image.new("RGB", (160, 160), "white").save(root / "first.jpg")
            Image.new("RGB", (160, 160), "gray").save(root / "second.jpg")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(root))
                photos = {photo.filename: photo for photo in db.list_photos(limit=10)}
                db.set_photo_rating(int(photos["second.jpg"].id), 1)
                picks = select_top_picks(db, count=1, library_root=str(root.resolve()))
            finally:
                db.close()

            self.assertEqual(picks[0].filename, "second.jpg")

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_taste_model_trains_from_likes_and_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            colors = ("white", "lightgray", "black", "dimgray")
            for index, color in enumerate(colors):
                Image.new("RGB", (160 + index * 20, 160), color).save(root / f"{index}.jpg")

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(root))
                photos = {photo.filename: photo for photo in db.list_photos(limit=10)}
                db.set_photo_rating(int(photos["0.jpg"].id), 1)
                db.set_photo_rating(int(photos["1.jpg"].id), 1)
                db.set_photo_rating(int(photos["2.jpg"].id), -1)
                db.set_photo_rating(int(photos["3.jpg"].id), -1)

                result = train_taste_model(db)
                model = load_taste_model(db)
                picks = select_top_picks(db, count=1, library_root=str(root.resolve()))
            finally:
                db.close()

            self.assertTrue(result.trained)
            self.assertIsNotNone(model)
            self.assertIn(picks[0].filename, {"0.jpg", "1.jpg"})

    def test_taste_model_requires_enough_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = PhotoDatabase(Path(temp_dir) / "test.sqlite3")
            try:
                result = train_taste_model(db)
            finally:
                db.close()

            self.assertFalse(result.trained)
            self.assertIn("2 liked and 2 rejected", result.message)

    def test_top_picks_expand_for_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db = PhotoDatabase(root / "test.sqlite3")
            try:
                for index, score in enumerate((0.95, 0.90, 0.40)):
                    db.upsert_photo(
                        PhotoRecord(
                            id=None,
                            library_root=str(root.resolve()),
                            path=str(root / f"{index}.jpg"),
                            filename=f"{index}.jpg",
                            extension=".jpg",
                            file_size=100 + index,
                            modified_at=float(index),
                            sha256=f"hash-{index}",
                            quality_score=score,
                            sharpness_score=score,
                            lighting_score=score,
                            composition_score=score,
                            expression_score=score,
                            people_score=score,
                            scenery_score=score,
                        )
                    )
                picks = select_top_picks(
                    db,
                    count=1,
                    score_threshold=0.75,
                    library_root=str(root.resolve()),
                )
            finally:
                db.close()

            self.assertEqual([photo.filename for photo in picks], ["0.jpg", "1.jpg"])

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_resize_photos_writes_smaller_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.jpg"
            output = root / "out"
            Image.new("RGB", (800, 600), "navy").save(source)
            photo = PhotoRecord(
                id=1,
                library_root=str(root),
                path=str(source),
                filename=source.name,
                extension=".jpg",
                file_size=source.stat().st_size,
                modified_at=source.stat().st_mtime,
                sha256="resize-test",
            )

            count = resize_photos([photo], output, max_width=200, max_height=200)
            resized = list(output.glob("*.jpg"))

            self.assertEqual(count, 1)
            self.assertEqual(len(resized), 1)
            with Image.open(resized[0]) as image:
                self.assertLessEqual(max(image.size), 200)

    def test_hamming_distance(self) -> None:
        self.assertEqual(hamming_distance("ff", "ff"), 0)
        self.assertEqual(hamming_distance("ff", "00"), 8)

    @unittest.skipIf(Image is None, "Pillow is not installed")
    def test_scan_and_find_resized_similar_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (240, 160), "white")
            for x in range(240):
                for y in range(160):
                    image.putpixel((x, y), (x % 255, y % 255, (x + y) % 255))
            image.save(root / "large.jpg", quality=95)
            image.resize((120, 80)).save(root / "small.jpg", quality=80)

            db = PhotoDatabase(root / "test.sqlite3")
            try:
                db.upsert_photos(scan_folder(root))
                exact_groups = find_exact_duplicate_groups(db)
                similar_groups = find_similar_photo_groups(db)
            finally:
                db.close()

            self.assertEqual(len(exact_groups), 0)
            self.assertEqual(len(similar_groups), 1)
            self.assertEqual(len(similar_groups[0].items), 2)
            self.assertEqual(similar_groups[0].items[0].suggested_action, "keep")
            self.assertIsNotNone(similar_groups[0].items[0].quality_score)


if __name__ == "__main__":
    unittest.main()
