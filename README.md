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
- Score photos for sharpness, lighting, composition, smile, and overall quality.
- Score Joy, Wow, and face count for people/scenery-aware picking.
- Suggest one standout per duplicate or similar-photo group.
- Pick the top 15 photos, plus any extra photos scoring 75 or higher.
- Train a local taste model from Like, Maybe, and Reject labels.
- Force a rescan/rescore of the selected folder after improving scoring logic or
  installing image libraries.
- View all indexed photos, only the selected folder, or only the last scan.
- Clear all indexed records or only the selected folder's records.
- Remove database records for files that no longer exist.
- Tag people in selected photos.
- Generate local captions and suggested organization paths.
- Preview the selected image and open it in the Windows default photo app.
- Review a selected photo in a larger window with quick Like/Maybe/Reject actions.
- Resize photos in bulk into a separate output folder.
- Preview and process HEIC files when `pillow-heif` is installed.
- Move non-keeper duplicates to a review folder instead of deleting them.
- Move unwanted photos to a deleted folder and count them as Reject feedback.
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
- **Smile**: local OpenCV-based face/smile estimate when a natural-looking smile
  is detected.
- **Joy**: people-focused score based on visible faces, smile, sharpness, and
  lighting.
- **Wow**: scenery-focused score based on color richness, dynamic range,
  composition, detail, and low face dominance.

Smile scoring runs locally with OpenCV. If no face/smile is detected, the field
stays blank. Rescan folders after installing dependencies to populate new Smile
scores. The app does not upload photos anywhere.

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
- **Balanced**: mixes people joy, scenery wow, quality, and your taste model.
- **Happy People**: favors visible, sharp, well-lit faces and natural smiles.
- **Amazing Scenery**: favors color, dynamic range, composition, detail, and
  landscape-style photos.

The picker first chooses the standout from each similar-photo group, then fills
the remaining slots by overall quality score. It always includes the best 15
photos, and if more photos score 75 or higher, it includes those too. This helps
avoid selecting many near-identical versions of the same moment while still
letting strong albums grow beyond 15.

Use **Like**, **Maybe**, and **Reject** on selected photos to teach the picker.
Liked photos move up, rejected photos move down, and the feedback is stored
locally.

Use **Train Model** after marking at least 2 liked and 2 rejected photos. The app
builds a small local taste model from your feedback and uses it to reorder future
Top Picks. As you mark more photos, run **Train Model** again to refine it.

The visible Top Picks score is calculated when the Top Picks table refreshes.
The underlying photo measurements are stored during scanning. Use
**Rescan / Rescore** after installing new image libraries or changing scoring
logic. The trained taste model is stored in the app database and remains
available when you scan or upload new folders.

Use **Export Top Picks** to copy the current picks into:

```text
_sanik_photo_top_picks
```

Original photos stay where they are.

## Review and Export

- **Large Review**: opens the selected photo in a larger review window.
- Keyboard shortcuts in Large Review:
  - `L`: Like
  - `M`: Maybe
  - `R`: Reject
  - Right arrow: next photo
  - Left arrow: previous photo
- When you rate a photo in Large Review, the review advances to the next photo.
  If opened from Top Picks, it reviews current Top Picks; otherwise it reviews
  the current app view.
- **Resize Export**: creates resized JPEG copies for the current view. If you are
  on the Top Picks tab, it resizes the current picks; otherwise it resizes photos
  in the selected app view. Originals stay untouched.
- **Delete / Reject**: moves the selected photo into `_sanik_photo_deleted`,
  marks it Reject for training, and hides it from normal Library, duplicate, and
  Top Picks views. The app skips its own `_sanik_photo_*` work folders during
  scans so those moved files do not come back into active picks.

## Project Layout

```text
app.py                  Desktop app entry point
sanik_photo/
  database.py           SQLite schema and queries
  duplicate_finder.py   Duplicate grouping and keeper suggestions
  file_actions.py       Safe file move operations
  image_export.py       Bulk resize/export helpers
  image_loader.py       Shared image opener registration including HEIC
  organizer.py          Captions and folder-path suggestions
  quality.py            Local photo quality scoring
  scanner.py            Folder scanning and hashing
  taste_model.py        Local preference model trained from your feedback
  top_picks.py          Best-photo selection
  ui.py                 Tkinter desktop interface
tests/
  test_scanner.py       Basic scanner/database smoke test
```

## Next Useful Upgrades

- Add thumbnails and EXIF date taken.
- Add event grouping by time and folder.
- Add local face detection and people tagging.
- Add richer image embeddings for taste learning.
