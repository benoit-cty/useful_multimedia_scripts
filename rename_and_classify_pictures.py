#!/usr/bin/python3

'''
This script rename your pictures and videos according to a given name and the date you took them, according to EXIF data.

Usage :
python3 rename_and_classify_pictures.py <folder> <name>

Writen by : Benoît Courty
Licence : BSD 3
'''

import sys
import argparse
import re
from datetime import datetime
from pathlib import Path
from PIL import Image, UnidentifiedImageError


JPG_EXTENSIONS = {".jpg", ".jpeg"}
RAW_EXTENSIONS = {
    ".3fr", ".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".pef",
    ".raf", ".raw", ".rw2", ".srw",
}


def date_taken(path):
    """Return the photo date, falling back to the file modification time."""
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            value = exif.get(36867) or exif.get(306)  # DateTimeOriginal, DateTime
        if value:
            return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").strftime("%y%m%d")
    except (OSError, UnidentifiedImageError, ValueError):
        pass

    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%y%m%d")


def picture_number(path):
    """Return the last five digits of the original camera filename."""
    match = re.search(r"(\d{5})$", path.stem)
    return match.group(1) if match else path.stem


def unique_destination(directory, stem, extension, reserved_destinations):
    """Build a destination that neither exists nor conflicts with this run."""
    candidate = directory / f"{stem}{extension.lower()}"
    suffix = 2
    while candidate in reserved_destinations or candidate.exists():
        candidate = directory / f"{stem} - {suffix}{extension.lower()}"
        suffix += 1
    reserved_destinations.add(candidate)
    return candidate


def unique_pair_destinations(jpg_dir, raw_dir, stem, jpg_extension, raw_extension,
                             reserved_destinations):
    """Build matching JPEG and RAW destinations without overwriting either file."""
    suffix = 1
    while True:
        suffix_text = "" if suffix == 1 else f" - {suffix}"
        jpg_destination = jpg_dir / f"{stem}{suffix_text}{jpg_extension.lower()}"
        raw_destination = raw_dir / f"{stem}{suffix_text}{raw_extension.lower()}"
        if (
            jpg_destination not in reserved_destinations
            and raw_destination not in reserved_destinations
            and not jpg_destination.exists()
            and not raw_destination.exists()
        ):
            reserved_destinations.update({jpg_destination, raw_destination})
            return jpg_destination, raw_destination
        suffix += 1


def move(source, destination, modify):
    print(f"{source} -> {destination}")
    if modify:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)

def main(argv):
    parser = argparse.ArgumentParser(description='Process some files.')
    parser.add_argument('folder', type=str, help='Input dir for videos')
    parser.add_argument('name')
    parser.add_argument('--modify', dest='dry_run', action='store_const',
                        const=False, default=True,
                        help='No dry run (default: no modification)')

    args = parser.parse_args(argv)
    source_dir = Path(args.folder).resolve()
    if not source_dir.is_dir():
        parser.error(f"folder does not exist or is not a directory: {args.folder}")

    jpg_dir = source_dir / 'jpg'
    raw_dir = source_dir / 'raw'
    jpg_only_dir = source_dir / 'jpg_only'
    files = sorted(path for path in source_dir.iterdir() if path.is_file())
    raw_by_stem = {
        path.stem.casefold(): path
        for path in files
        if path.suffix.casefold() in RAW_EXTENSIONS
    }
    reserved_destinations = set()

    print(f"Looking into {source_dir} to classify and rename pictures")
    for jpg in files:
        if jpg.suffix.casefold() not in JPG_EXTENSIONS:
            continue

        raw = raw_by_stem.pop(jpg.stem.casefold(), None)
        stem = f"{date_taken(jpg)} - {picture_number(jpg)} - {args.name}"
        if raw:
            jpg_destination, raw_destination = unique_pair_destinations(
                jpg_dir,
                raw_dir,
                stem,
                jpg.suffix,
                raw.suffix,
                reserved_destinations,
            )
        else:
            jpg_destination = unique_destination(
                jpg_only_dir, stem, jpg.suffix, reserved_destinations
            )
        move(jpg, jpg_destination, not args.dry_run)

        if raw:
            move(raw, raw_destination, not args.dry_run)

    for raw in raw_by_stem.values():
        destination = unique_destination(
            raw_dir,
            f"{date_taken(raw)} - {picture_number(raw)} - {args.name}",
            raw.suffix,
            reserved_destinations,
        )
        move(raw, destination, not args.dry_run)

    if args.dry_run:
        print("Dry run: no files were modified. Use --modify to apply these changes.")

if __name__ == "__main__":
   main(sys.argv[1:])
