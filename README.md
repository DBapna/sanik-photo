# SanikPhoto

SanikPhoto is a local-first desktop photo manager for scanning folders, finding
duplicate images, and preparing a safer workflow for album curation and people
tagging.

The app is local-first: photos are scanned on your laptop and the index is stored
in SQLite.

The desktop UI is branded for **Sanik** and will use the local Sanik logo when it
is available on this machine.

## Features in this MVP

- Pick a folder from your laptop.
- Recursively scan common photo file types.
- Store the photo library in SQLite.
- Detect exact duplicates using SHA-256 file hashes.
- Detect reduced or lightly compressed copies when Pillow is installed.
- Score photos for sharpness, lighting, composition, and overall quality.
- Suggest one standout per duplicate or similar-photo group.
- Pick the top 15 photos from the current view while avoiding near-duplicate moments.
- Learn from your feedback with Like, Maybe, and Reject labels.
- View all indexed photos, only the selected folder, or only the last scan.
- Clear all indexed records or only the selected folder's records.
- Remove database records for files that no longer exist.
- Tag people in selected photos.
- Generate local captions and suggested organization paths.
- Preview the selected image and open it in the Windows default photo app.
- Move non-keeper duplicates to a review folder instead of deleting them.
- Keep a record of file actions.

## Run

```powershell
python app.py
```

## Smoke Test

```powershell
python -m unittest discover -s tests
```

## Image Intelligence

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

After installing dependencies, rescan your folder. The app records image
dimensions, perceptual hashes, and local quality scores:

- **Score**: combined standout score from the available signals.
- **Sharp**: edge-detail based sharpness estimate.
- **Light**: brightness, contrast, and clipping estimate.
- **Comp**: simple composition estimate based on visual energy and balance.

Expression scoring is reserved for a future local face-analysis model. For now,
the app leaves expression neutral and does not upload photos anywhere.

## Library Views and Cleanup

The app keeps an index between runs. It does not delete or rewrite your actual
photo files when you clear the index.

- **Selected folder**: show records for the folder currently chosen at the top.
- **Last scan**: show only files found during the most recent scan.
- **All indexed**: show everything currently stored in the app database.
- **Clear This Folder**: remove indexed records for the selected folder only.
- **Clear All Index**: remove all photo records from the app database.
- **Remove Missing**: remove index records when the original file path no
  longer exists.

## Tagging and Organization

Select a row in the Library, Exact Duplicates, or Similar Photos tab.

- **Tag People**: enter names separated by commas. The app stores these labels
  locally and uses them in captions and suggested paths.
- **Generate Caption**: create a simple local description from date, people,
  and quality scores.
- **Open Image**: open the selected file in the Windows default photo app.
- **Suggested path**: create a possible folder/name convention:

```text
YYYY/MM-Month/People-Name-Name/Event-Name/original-filename.jpg
```

This first version does not automatically move files into that structure. It
only suggests the path so you can review it safely.

## Top Picks

Use the **Top Picks** tab to review the best photos from the current view:

- **Selected folder**: picks from the folder currently chosen at the top.
- **Last scan**: picks from only the most recent scan.
- **All indexed**: picks from everything in the app database.

The picker first chooses the standout from each similar-photo group, then fills
the remaining slots by overall quality score. This helps avoid selecting many
near-identical versions of the same moment.

Use **Like**, **Maybe**, and **Reject** on selected photos to train the picker.
Liked photos move up, rejected photos move down, and the feedback is stored
locally so future Top Picks reflect your taste better.

Use **Export Top Picks** to copy the current picks into:

```text
_sanik_photo_top_picks
```

Original photos stay where they are.

## Project Layout

```text
app.py                  Desktop app entry point
sanik_photo/
  database.py           SQLite schema and queries
  duplicate_finder.py   Duplicate grouping and keeper suggestions
  file_actions.py       Safe file move operations
  organizer.py          Captions and folder-path suggestions
  quality.py            Local photo quality scoring
  scanner.py            Folder scanning and hashing
  top_picks.py          Best-photo selection
  ui.py                 Tkinter desktop interface
tests/
  test_scanner.py       Basic scanner/database smoke test
```

## Next Useful Upgrades

- Add thumbnails and EXIF date taken.
- Add event grouping by time and folder.
- Add local face detection and people tagging.
