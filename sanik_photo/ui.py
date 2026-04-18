from __future__ import annotations

import queue
import shutil
import threading
from datetime import datetime
import os
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, TOP, VERTICAL, W, X, filedialog, messagebox, simpledialog, ttk
import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from .database import PhotoDatabase
from .duplicate_finder import find_exact_duplicate_groups, find_similar_photo_groups
from .file_actions import move_review_duplicates, unique_target
from .models import DuplicateGroup
from .organizer import caption_for_photo, suggested_organization_path
from .scanner import scan_folder
from .taste_model import load_taste_model, train_taste_model
from .top_picks import DEFAULT_PICK_COUNT, DEFAULT_SCORE_THRESHOLD, select_top_picks


SANIK_LOGO_PATH = Path(
    r"C:\Users\deepa\OneDrive\Documents\Deepak Documents\Personal\Sanik Advising and Consulting"
    r"\Business Application etc\SANIK_logo.jpg"
)

COLORS = {
    "bg": "#f6f5f1",
    "surface": "#ffffff",
    "surface_alt": "#fbfaf7",
    "ink": "#071d33",
    "muted": "#5c6670",
    "line": "#d8d3c8",
    "gold": "#c8a13a",
    "gold_dark": "#9c7924",
    "selected": "#e9f1f6",
}


class PhotoManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sanik Photo Manager")
        self.geometry("1240x780")
        self.minsize(1040, 640)
        self.configure(bg=COLORS["bg"])

        self.database = PhotoDatabase()
        self.selected_folder = tk.StringVar(value="")
        self.view_mode = tk.StringVar(value="Selected folder")
        self.status = tk.StringVar(value="Choose a folder to begin.")
        self.people_text = tk.StringVar(value="")
        self.preference_text = tk.StringVar(value="")
        self.caption_text = tk.StringVar(value="")
        self.suggested_path_text = tk.StringVar(value="")
        self.selected_photo_path = tk.StringVar(value="")
        self.scan_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.duplicate_groups: list[DuplicateGroup] = []
        self.similar_groups: list[DuplicateGroup] = []
        self.current_scan_paths: set[str] = set()
        self.top_picks = []
        self.logo_image = None
        self.preview_image = None

        self._configure_style()
        self._build_ui()
        self._refresh_tables()
        self.after(150, self._poll_scan_queue)

    def destroy(self) -> None:
        self.database.close()
        super().destroy()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        self.option_add("*Font", "{Segoe UI} 10")
        self.option_add("*TCombobox*Listbox.font", "{Segoe UI} 10")

        style.configure(".", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 10))
        style.configure("Shell.TFrame", background=COLORS["bg"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("Header.TFrame", background=COLORS["surface"])
        style.configure("Toolbar.TFrame", background=COLORS["surface_alt"])
        style.configure("Details.TLabelframe", background=COLORS["surface"], bordercolor=COLORS["line"])
        style.configure("Details.TLabelframe.Label", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 10))
        style.configure("Brand.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", 22))
        style.configure("Subtle.TLabel", background=COLORS["surface"], foreground=COLORS["muted"])
        style.configure("Path.TLabel", background=COLORS["surface_alt"], foreground=COLORS["muted"])
        style.configure("Status.TLabel", background=COLORS["bg"], foreground=COLORS["muted"])
        style.configure("DetailTitle.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI Semibold", 9))
        style.configure("DetailValue.TLabel", background=COLORS["surface"], foreground=COLORS["ink"])

        style.configure("TButton", padding=(10, 7), relief="flat", borderwidth=1)
        style.map("TButton", background=[("active", "#ece8df")])
        style.configure("Accent.TButton", background=COLORS["ink"], foreground="#ffffff", bordercolor=COLORS["ink"])
        style.map("Accent.TButton", background=[("active", "#12314d")], foreground=[("active", "#ffffff")])
        style.configure("Gold.TButton", background=COLORS["gold"], foreground="#ffffff", bordercolor=COLORS["gold"])
        style.map("Gold.TButton", background=[("active", COLORS["gold_dark"])], foreground=[("active", "#ffffff")])

        style.configure("TCombobox", padding=(8, 5), fieldbackground="#ffffff", background="#ffffff")
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI Semibold", 10))
        style.map("TNotebook.Tab", background=[("selected", COLORS["surface"])], foreground=[("selected", COLORS["ink"])])
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["ink"],
            rowheight=28,
            bordercolor=COLORS["line"],
            borderwidth=1,
        )
        style.configure("Treeview.Heading", background="#eee9df", foreground=COLORS["ink"], font=("Segoe UI Semibold", 10), padding=(8, 7))
        style.map("Treeview", background=[("selected", COLORS["selected"])], foreground=[("selected", COLORS["ink"])])

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, padding=16, style="Shell.TFrame")
        shell.pack(fill=BOTH, expand=True)

        header = ttk.Frame(shell, padding=(14, 12), style="Header.TFrame")
        header.pack(fill=X)
        logo = self._load_logo()
        if logo is not None:
            ttk.Label(header, image=logo, background=COLORS["surface"]).pack(side=LEFT, padx=(0, 14))
        else:
            ttk.Label(header, text="SANIK", style="Brand.TLabel").pack(side=LEFT, padx=(0, 14))

        title_block = ttk.Frame(header, style="Header.TFrame")
        title_block.pack(side=LEFT, fill=X, expand=True)
        ttk.Label(title_block, text="Sanik Photo Manager", style="Brand.TLabel").pack(anchor=W)
        ttk.Label(
            title_block,
            text="Find duplicates, score standouts, tag people, and prepare album picks locally.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(2, 0))

        top = ttk.Frame(shell, padding=(12, 10), style="Toolbar.TFrame")
        top.pack(fill=X)

        ttk.Button(top, text="Choose Folder", command=self._choose_folder).pack(side=LEFT)
        ttk.Label(top, textvariable=self.selected_folder, anchor=W, style="Path.TLabel").pack(side=LEFT, fill=X, expand=True, padx=12)
        ttk.Button(top, text="Scan Library", command=self._start_scan, style="Accent.TButton").pack(side=RIGHT)

        actions = ttk.Frame(shell, padding=(12, 10), style="Toolbar.TFrame")
        actions.pack(fill=X, pady=(10, 6))
        ttk.Button(actions, text="Refresh", command=self._refresh_tables).pack(side=LEFT)
        ttk.Button(actions, text="Move Duplicates", command=self._move_review_duplicates).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Remove Missing", command=self._remove_missing).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Clear Folder", command=self._clear_selected_folder).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Clear All", command=self._clear_all_library).pack(side=LEFT, padx=(8, 16))
        ttk.Button(actions, text="Tag People", command=self._tag_selected_people, style="Gold.TButton").pack(side=LEFT)
        ttk.Button(actions, text="Caption", command=self._generate_selected_caption).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Top Picks", command=self._refresh_top_picks).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Export Picks", command=self._export_top_picks).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Train Model", command=self._train_taste_model).pack(side=LEFT, padx=(8, 0))
        ttk.Button(actions, text="Like", command=lambda: self._rate_selected_photo(1), style="Gold.TButton").pack(side=RIGHT)
        ttk.Button(actions, text="Maybe", command=lambda: self._rate_selected_photo(0)).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(actions, text="Reject", command=lambda: self._rate_selected_photo(-1)).pack(side=RIGHT, padx=(0, 8))

        filters = ttk.Frame(shell, padding=(12, 0), style="Shell.TFrame")
        filters.pack(fill=X, pady=(0, 8))
        ttk.Label(filters, text="View", style="Status.TLabel").pack(side=LEFT)
        view_selector = ttk.Combobox(
            filters,
            textvariable=self.view_mode,
            values=("Selected folder", "Last scan", "All indexed"),
            state="readonly",
            width=18,
        )
        view_selector.pack(side=LEFT, padx=8)
        view_selector.bind("<<ComboboxSelected>>", lambda _event: self._refresh_tables())

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill=BOTH, expand=True)

        self.photos_tree = self._make_tree(
            self.notebook,
            ("filename", "pref", "score", "sharp", "light", "comp", "smile", "size", "modified", "path"),
            ("Filename", "Pref", "Score", "Sharp", "Light", "Comp", "Smile", "Size", "Modified", "Path"),
        )
        self.notebook.add(self.photos_tree.master, text="Library")

        self.duplicates_tree = self._make_tree(
            self.notebook,
            ("group", "action", "pref", "score", "sharp", "light", "comp", "smile", "filename", "size", "path"),
            ("Group", "Suggestion", "Pref", "Score", "Sharp", "Light", "Comp", "Smile", "Filename", "Size", "Path"),
        )
        self.notebook.add(self.duplicates_tree.master, text="Exact Duplicates")

        self.similar_tree = self._make_tree(
            self.notebook,
            ("group", "action", "pref", "score", "sharp", "light", "comp", "smile", "filename", "size", "path"),
            ("Group", "Suggestion", "Pref", "Score", "Sharp", "Light", "Comp", "Smile", "Filename", "Size", "Path"),
        )
        self.notebook.add(self.similar_tree.master, text="Similar Photos")

        self.top_picks_tree = self._make_tree(
            self.notebook,
            ("rank", "pref", "score", "sharp", "light", "comp", "smile", "filename", "size", "path"),
            ("Rank", "Pref", "Score", "Sharp", "Light", "Comp", "Smile", "Filename", "Size", "Path"),
        )
        self.notebook.add(self.top_picks_tree.master, text="Top Picks")

        ttk.Label(shell, textvariable=self.status, style="Status.TLabel").pack(fill=X, pady=(8, 0))

        details = ttk.LabelFrame(shell, text="Selected Photo", padding=(10, 8), style="Details.TLabelframe")
        details.pack(fill=X, pady=(8, 0))
        preview_panel = ttk.Frame(details, style="Surface.TFrame")
        preview_panel.pack(side=LEFT, padx=(0, 14))
        self.preview_label = tk.Label(
            preview_panel,
            text="No preview",
            width=22,
            height=7,
            bg=COLORS["surface_alt"],
            fg=COLORS["muted"],
            relief="solid",
            bd=1,
        )
        self.preview_label.pack(side=TOP)
        ttk.Button(preview_panel, text="Open Image", command=self._open_selected_image).pack(fill=X, pady=(6, 0))

        detail_text = ttk.Frame(details, style="Surface.TFrame")
        detail_text.pack(side=LEFT, fill=X, expand=True)
        row_one = ttk.Frame(detail_text, style="Surface.TFrame")
        row_one.pack(fill=X)
        ttk.Label(row_one, text="People", style="DetailTitle.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Label(row_one, textvariable=self.people_text, style="DetailValue.TLabel").pack(side=LEFT, padx=(0, 18))
        ttk.Label(row_one, text="Pref", style="DetailTitle.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Label(row_one, textvariable=self.preference_text, style="DetailValue.TLabel").pack(side=LEFT, padx=(0, 18))
        ttk.Label(row_one, text="Path", style="DetailTitle.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Label(row_one, textvariable=self.selected_photo_path, style="DetailValue.TLabel").pack(side=LEFT, fill=X, expand=True)

        row_two = ttk.Frame(detail_text, style="Surface.TFrame")
        row_two.pack(fill=X, pady=(8, 0))
        ttk.Label(row_two, text="Caption", style="DetailTitle.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Label(row_two, textvariable=self.caption_text, style="DetailValue.TLabel").pack(side=LEFT, fill=X, expand=True)

        row_three = ttk.Frame(detail_text, style="Surface.TFrame")
        row_three.pack(fill=X, pady=(8, 0))
        ttk.Label(row_three, text="Suggested", style="DetailTitle.TLabel").pack(side=LEFT, padx=(0, 4))
        ttk.Label(row_three, textvariable=self.suggested_path_text, style="DetailValue.TLabel").pack(side=LEFT, fill=X, expand=True)

        self.photos_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_details())
        self.duplicates_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_details())
        self.similar_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_details())
        self.top_picks_tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selected_details())

    def _load_logo(self):
        if Image is None or ImageTk is None or not SANIK_LOGO_PATH.exists():
            return None
        image = Image.open(SANIK_LOGO_PATH)
        image = image.convert("RGB")
        image.thumbnail((210, 70))
        self.logo_image = ImageTk.PhotoImage(image)
        return self.logo_image

    def _make_tree(self, parent: ttk.Notebook, columns: tuple[str, ...], headings: tuple[str, ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        scroll = ttk.Scrollbar(frame, orient=VERTICAL)
        tree = ttk.Treeview(frame, columns=columns, show="headings", yscrollcommand=scroll.set)
        scroll.config(command=tree.yview)
        scroll.pack(side=RIGHT, fill="y")
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            width = 130
            if column == "path":
                width = 420
            elif column == "filename":
                width = 220
            elif column in {"pref", "score", "sharp", "light", "comp", "smile"}:
                width = 70
            elif column == "action":
                width = 110
            tree.column(column, width=width, anchor=W)
        return tree

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose photo folder")
        if folder:
            self.selected_folder.set(folder)
            self.status.set("Ready to scan.")
            self.view_mode.set("Selected folder")
            self._refresh_tables()

    def _start_scan(self) -> None:
        folder = self.selected_folder.get()
        if not folder:
            messagebox.showinfo("Choose a folder", "Pick a photo folder first.")
            return

        self.status.set("Scanning photos...")
        thread = threading.Thread(target=self._scan_worker, args=(folder,), daemon=True)
        thread.start()

    def _scan_worker(self, folder: str) -> None:
        worker_database = PhotoDatabase(self.database.db_path)
        try:
            count = 0
            scanned_paths: set[str] = set()
            for photo in scan_folder(folder, progress=lambda path: self.scan_queue.put(("progress", path))):
                worker_database.upsert_photo(photo)
                scanned_paths.add(photo.path)
                count += 1
            self.scan_queue.put(("done", (count, scanned_paths)))
        except Exception as exc:
            self.scan_queue.put(("error", str(exc)))
        finally:
            worker_database.close()

    def _poll_scan_queue(self) -> None:
        try:
            while True:
                kind, payload = self.scan_queue.get_nowait()
                if kind == "progress":
                    self.status.set(f"Scanning: {payload}")
                elif kind == "done":
                    count, scanned_paths = payload
                    self.current_scan_paths = scanned_paths
                    self.view_mode.set("Last scan")
                    self.status.set(f"Scan complete. Indexed {count} photos.")
                    self._refresh_tables()
                elif kind == "error":
                    self.status.set("Scan failed.")
                    messagebox.showerror("Scan failed", str(payload))
        except queue.Empty:
            pass
        self.after(150, self._poll_scan_queue)

    def _refresh_tables(self) -> None:
        self._refresh_photos()
        self._refresh_duplicates()
        self._refresh_similar()
        self._refresh_top_picks(show_status=False)

    def _refresh_photos(self) -> None:
        self.photos_tree.delete(*self.photos_tree.get_children())
        library_root, paths = self._current_scope()
        photos = self.database.list_photos(library_root=library_root, paths=paths)
        for photo in photos:
            self.photos_tree.insert(
                "",
                END,
                values=(
                    photo.filename,
                    format_preference(photo.user_rating),
                    format_score(photo.quality_score),
                    format_score(photo.sharpness_score),
                    format_score(photo.lighting_score),
                    format_score(photo.composition_score),
                    format_score(photo.expression_score),
                    format_bytes(photo.file_size),
                    format_timestamp(photo.modified_at),
                    photo.path,
                ),
            )

    def _refresh_duplicates(self) -> None:
        self.duplicates_tree.delete(*self.duplicates_tree.get_children())
        library_root, paths = self._current_scope()
        self.duplicate_groups = find_exact_duplicate_groups(self.database, library_root=library_root, paths=paths)
        for group_index, group in enumerate(self.duplicate_groups, start=1):
            for item in group.items:
                self.duplicates_tree.insert(
                    "",
                    END,
                    values=(
                        group_index,
                        display_action(item.suggested_action),
                        format_preference(item.user_rating),
                        format_score(item.quality_score),
                        format_score(item.sharpness_score),
                        format_score(item.lighting_score),
                        format_score(item.composition_score),
                        format_score(item.expression_score),
                        item.filename,
                        format_bytes(item.file_size),
                        item.path,
                    ),
                )
        self.status.set(
            f"Loaded {len(self.database.list_photos(library_root=library_root, paths=paths))} recent photos and "
            f"{len(self.duplicate_groups)} duplicate groups."
        )

    def _refresh_similar(self) -> None:
        self.similar_tree.delete(*self.similar_tree.get_children())
        library_root, paths = self._current_scope()
        self.similar_groups = find_similar_photo_groups(self.database, library_root=library_root, paths=paths)
        for group_index, group in enumerate(self.similar_groups, start=1):
            for item in group.items:
                self.similar_tree.insert(
                    "",
                    END,
                    values=(
                        group_index,
                        display_action(item.suggested_action),
                        format_preference(item.user_rating),
                        format_score(item.quality_score),
                        format_score(item.sharpness_score),
                        format_score(item.lighting_score),
                        format_score(item.composition_score),
                        format_score(item.expression_score),
                        item.filename,
                        format_bytes(item.file_size),
                        item.path,
                    ),
                )

    def _move_review_duplicates(self) -> None:
        if not self.duplicate_groups:
            messagebox.showinfo("No duplicates", "No exact duplicate groups are currently loaded.")
            return
        folder = self.selected_folder.get()
        if not folder:
            messagebox.showinfo("Choose a folder", "Pick the library folder before moving files.")
            return
        review_root = Path(folder) / "_sanik_photo_review"
        confirm = messagebox.askyesno(
            "Move duplicates",
            f"Move suggested duplicate files into this review folder?\n\n{review_root}",
        )
        if not confirm:
            return
        moved = move_review_duplicates(self.database, self.duplicate_groups, review_root)
        self.status.set(f"Moved {moved} files to review folder.")
        self._refresh_tables()

    def _current_scope(self) -> tuple[str | None, set[str] | None]:
        mode = self.view_mode.get()
        if mode == "All indexed":
            return None, None
        if mode == "Last scan":
            return None, self.current_scan_paths
        folder = self.selected_folder.get()
        return (str(Path(folder).expanduser().resolve()), None) if folder else (None, None)

    def _remove_missing(self) -> None:
        library_root, paths = self._current_scope()
        if paths is not None:
            messagebox.showinfo("Switch view", "Remove Missing works for Selected folder or All indexed views.")
            return
        label = library_root if library_root else "all indexed folders"
        confirm = messagebox.askyesno(
            "Remove missing records",
            f"Remove database records for files that no longer exist?\n\nScope: {label}\n\nYour actual photos will not be deleted.",
        )
        if not confirm:
            return
        removed = self.database.remove_missing_files(library_root=library_root)
        self.status.set(f"Removed {removed} missing file records from the index.")
        self._refresh_tables()

    def _clear_selected_folder(self) -> None:
        folder = self.selected_folder.get()
        if not folder:
            messagebox.showinfo("Choose a folder", "Pick a photo folder first.")
            return
        library_root = str(Path(folder).expanduser().resolve())
        confirm = messagebox.askyesno(
            "Clear this folder",
            f"Clear indexed records for this folder only?\n\n{library_root}\n\nYour actual photos will not be deleted.",
        )
        if not confirm:
            return
        cleared = self.database.clear_library(library_root=library_root)
        if self.view_mode.get() == "Last scan":
            self.current_scan_paths.clear()
        self.status.set(f"Cleared {cleared} records from the app index.")
        self._refresh_tables()

    def _clear_all_library(self) -> None:
        confirm = messagebox.askyesno(
            "Clear all indexed data",
            "Clear all photo records from the app database?\n\nYour actual photos will not be deleted.",
        )
        if not confirm:
            return
        cleared = self.database.clear_library()
        self.current_scan_paths.clear()
        self.status.set(f"Cleared {cleared} records from the app index.")
        self._refresh_tables()

    def _selected_photo_id(self) -> int | None:
        tree = self.focus_get()
        if not isinstance(tree, ttk.Treeview):
            tree = self._active_tree()
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        path = str(tree.item(selected[0], "values")[-1])
        return self.database.get_photo_id_by_path(path)

    def _active_tree(self) -> ttk.Treeview | None:
        tab = self.notebook.select()
        if not tab:
            return None
        for tree in (self.photos_tree, self.duplicates_tree, self.similar_tree, self.top_picks_tree):
            if str(tree.master) == tab:
                return tree
        return None

    def _show_selected_details(self) -> None:
        photo_id = self._selected_photo_id()
        if photo_id is None:
            return
        people = self.database.people_for_photo(photo_id)
        caption, suggested_path = self.database.note_for_photo(photo_id)
        photo = self.database.get_photo(photo_id)
        self.people_text.set(", ".join(people) if people else "None yet")
        self.preference_text.set(format_preference(photo.user_rating) if photo else "")
        self.selected_photo_path.set(photo.path if photo else "")
        self.caption_text.set(caption or "Not generated")
        self.suggested_path_text.set(suggested_path or "Not generated")
        if photo:
            self._load_preview(photo.path)

    def _load_preview(self, path: str) -> None:
        if Image is None or ImageTk is None:
            self.preview_label.configure(text="Install Pillow for previews", image="")
            self.preview_image = None
            return
        source = Path(path)
        if not source.exists():
            self.preview_label.configure(text="File missing", image="")
            self.preview_image = None
            return
        try:
            with Image.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail((220, 140))
                self.preview_image = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_image, text="", width=220, height=140)
        except Exception:
            self.preview_label.configure(text="Preview unavailable", image="")
            self.preview_image = None

    def _open_selected_image(self) -> None:
        path = self.selected_photo_path.get()
        if not path:
            messagebox.showinfo("Select a photo", "Select one photo row first.")
            return
        if not Path(path).exists():
            messagebox.showerror("File missing", f"This file no longer exists:\n\n{path}")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Open failed", str(exc))

    def _tag_selected_people(self) -> None:
        photo_id = self._selected_photo_id()
        if photo_id is None:
            messagebox.showinfo("Select a photo", "Select one photo row first.")
            return
        current = ", ".join(self.database.people_for_photo(photo_id))
        raw_names = simpledialog.askstring(
            "Tag people",
            "Enter people in this photo, separated by commas.",
            initialvalue=current,
            parent=self,
        )
        if raw_names is None:
            return
        names = [name.strip() for name in raw_names.split(",") if name.strip()]
        self.database.add_people_to_photo(photo_id, names)
        self._generate_caption_for_photo(photo_id)
        self._show_selected_details()

    def _generate_selected_caption(self) -> None:
        photo_id = self._selected_photo_id()
        if photo_id is None:
            messagebox.showinfo("Select a photo", "Select one photo row first.")
            return
        self._generate_caption_for_photo(photo_id)
        self._show_selected_details()

    def _generate_caption_for_photo(self, photo_id: int) -> None:
        photo = self.database.get_photo(photo_id)
        if photo is None:
            return
        people = self.database.people_for_photo(photo_id)
        caption = caption_for_photo(photo, people)
        suggested_path = suggested_organization_path(photo, people)
        self.database.save_photo_note(photo_id, caption, suggested_path)
        self.status.set("Generated caption and organization suggestion.")

    def _refresh_top_picks(self, show_status: bool = True) -> None:
        self.top_picks_tree.delete(*self.top_picks_tree.get_children())
        library_root, paths = self._current_scope()
        self.top_picks = select_top_picks(
            self.database,
            count=DEFAULT_PICK_COUNT,
            library_root=library_root,
            paths=paths,
        )
        for index, photo in enumerate(self.top_picks, start=1):
            self.top_picks_tree.insert(
                "",
                END,
                values=(
                    index,
                    format_preference(photo.user_rating),
                    format_score(photo.quality_score),
                    format_score(photo.sharpness_score),
                    format_score(photo.lighting_score),
                    format_score(photo.composition_score),
                    format_score(photo.expression_score),
                    photo.filename,
                    format_bytes(photo.file_size),
                    photo.path,
                ),
            )
        if show_status:
            threshold = round(DEFAULT_SCORE_THRESHOLD * 100)
            model_note = "taste model on" if load_taste_model(self.database) else "heuristics only"
            self.status.set(
                f"Selected {len(self.top_picks)} top picks "
                f"(best {DEFAULT_PICK_COUNT} plus any scoring {threshold}+, {model_note})."
            )

    def _export_top_picks(self) -> None:
        if not self.top_picks:
            self._refresh_top_picks(show_status=False)
        if not self.top_picks:
            messagebox.showinfo("No top picks", "There are no top picks to export for this view.")
            return
        folder = self.selected_folder.get()
        if not folder:
            messagebox.showinfo("Choose a folder", "Pick a photo folder first.")
            return
        target_root = Path(folder) / "_sanik_photo_top_picks"
        confirm = messagebox.askyesno(
            "Export top picks",
            f"Copy the current top picks into this folder?\n\n{target_root}\n\nOriginal photos will stay where they are.",
        )
        if not confirm:
            return
        target_root.mkdir(parents=True, exist_ok=True)
        copied = 0
        for rank, photo in enumerate(self.top_picks, start=1):
            source = Path(photo.path)
            if not source.exists():
                continue
            target = unique_target(target_root / f"{rank:02d}-{source.name}")
            shutil.copy2(source, target)
            self.database.log_file_action(photo.id, "copy_top_pick", str(source), str(target))
            copied += 1
        self.status.set(f"Copied {copied} top picks to {target_root}.")

    def _rate_selected_photo(self, rating: int) -> None:
        photo_id = self._selected_photo_id()
        if photo_id is None:
            messagebox.showinfo("Select a photo", "Select one photo row first.")
            return
        self.database.set_photo_rating(photo_id, rating)
        self._refresh_tables()
        self._show_selected_details()
        self.status.set(f"Saved preference: {format_preference(rating)}.")

    def _train_taste_model(self) -> None:
        result = train_taste_model(self.database)
        self.status.set(result.message)
        if result.trained:
            self._refresh_top_picks(show_status=False)
            self.notebook.select(self.top_picks_tree.master)
        else:
            messagebox.showinfo("More feedback needed", result.message)


def format_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def format_score(score: float | None) -> str:
    return "" if score is None else f"{round(score * 100):d}"


def display_action(action: str) -> str:
    return "standout" if action == "keep" else action


def format_preference(rating: int | None) -> str:
    if rating == 1:
        return "Like"
    if rating == 0:
        return "Maybe"
    if rating == -1:
        return "Reject"
    return ""


def main() -> None:
    app = PhotoManagerApp()
    app.mainloop()
