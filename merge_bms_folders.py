#!/usr/bin/env python3
# merge_bms_folders.py

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


CHART_EXTENSIONS = {
    ".bms",
    ".bme",
    ".bml",
    ".pms",
    ".bmson",
}


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def has_chart_file_directly(folder: Path) -> bool:
    try:
        for child in folder.iterdir():
            if child.is_file() and child.suffix.lower() in CHART_EXTENSIONS:
                return True
    except PermissionError:
        print(f"[WARN] Permission denied: {folder}")
    except OSError as e:
        print(f"[WARN] Cannot read: {folder} ({e})")
    return False


def find_song_folders(root: Path, dest_root: Path) -> list[Path]:
    """
    直下にBMS譜面ファイルを持つフォルダを曲フォルダ候補とする。
    songs配下は探索対象から除外する。
    """
    candidates: list[Path] = []

    root = root.resolve()
    dest_root = dest_root.resolve()

    for current, dirs, files in os.walk(root):
        current_path = Path(current).resolve()

        if current_path == dest_root or is_relative_to(current_path, dest_root):
            dirs[:] = []
            continue

        # 隠し/一時系を軽く除外したい場合はここで dirs を編集できる
        if any(Path(f).suffix.lower() in CHART_EXTENSIONS for f in files):
            candidates.append(current_path)

    # 親候補の中にさらに曲フォルダ候補がある場合、親を移動すると危険なので親を除外する
    # 例: event_root に .bms が直置きされていて、さらに event_root/songA もある場合など
    candidate_set = set(candidates)
    nested_parents: set[Path] = set()

    for c in candidates:
        for other in candidates:
            if c == other:
                continue
            if is_relative_to(other, c):
                nested_parents.add(c)
                break

    if nested_parents:
        print("[WARN] Nested song-folder candidates found. Parent candidates will be skipped:")
        for p in sorted(nested_parents):
            print(f"       {p}")

    return [c for c in candidates if c not in nested_parents]


def ensure_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[ADD]  {src} -> {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def merge_tree_skip_existing(src_dir: Path, dst_dir: Path, dry_run: bool) -> tuple[int, int]:
    """
    src_dir の中身を dst_dir にマージする。
    既存ファイルはスキップ。
    戻り値: (追加したファイル数, スキップしたファイル数)
    """
    added = 0
    skipped = 0

    for current, dirs, files in os.walk(src_dir):
        current_path = Path(current)
        rel_dir = current_path.relative_to(src_dir)
        target_dir = dst_dir / rel_dir

        ensure_dir(target_dir, dry_run)

        for filename in files:
            src_file = current_path / filename
            dst_file = target_dir / filename

            if dst_file.exists():
                print(f"[SKIP] exists: {dst_file}")
                skipped += 1
                continue

            move_file(src_file, dst_file, dry_run)
            added += 1

    return added, skipped


def remove_tree(path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DELETE] {path}")
        return

    if path.exists():
        shutil.rmtree(path)


def cleanup_empty_parents(start: Path, stop_at: Path, dry_run: bool) -> None:
    """
    曲フォルダ削除後、空になった親フォルダを stop_at まで削除する。
    stop_at 自体は削除しない。
    """
    current = start.parent.resolve()
    stop_at = stop_at.resolve()

    while current != stop_at and is_relative_to(current, stop_at):
        try:
            if any(current.iterdir()):
                break

            if dry_run:
                print(f"[DELETE EMPTY DIR] {current}")
            else:
                current.rmdir()

            current = current.parent.resolve()
        except OSError:
            break


def process_song_folder(src_song_dir: Path, dest_root: Path, source_root: Path, dry_run: bool) -> None:
    src_song_dir = src_song_dir.resolve()
    dest_root = dest_root.resolve()
    source_root = source_root.resolve()

    target_dir = dest_root / src_song_dir.name

    if src_song_dir == target_dir:
        print(f"[OK] already in destination: {src_song_dir}")
        return

    if is_relative_to(src_song_dir, dest_root):
        print(f"[OK] already under destination, skipped: {src_song_dir}")
        return

    print()
    print(f"Source: {src_song_dir}")
    print(f"Target: {target_dir}")

    if not target_dir.exists():
        print("[MOVE] target does not exist; moving whole folder")

        if dry_run:
            print(f"[MOVE] {src_song_dir} -> {target_dir}")
        else:
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_song_dir), str(target_dir))

        cleanup_empty_parents(src_song_dir, source_root, dry_run)
        return

    print("[MERGE] target exists; merging contents, skipping existing files")
    added, skipped = merge_tree_skip_existing(src_song_dir, target_dir, dry_run)

    print(f"[MERGE RESULT] added={added}, skipped={skipped}")

    # 既存ファイルをスキップしても、容量削減目的なので移動元フォルダは削除する
    remove_tree(src_song_dir, dry_run)
    cleanup_empty_parents(src_song_dir, source_root, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge scattered BMS song folders into one songs directory by folder name."
    )
    parser.add_argument(
        "--dest",
        required=True,
        help=r"Destination songs directory, e.g. D:\bms\songs",
    )
    parser.add_argument(
        "--source",
        required=True,
        action="append",
        help="Source root directory. Specify multiple times for multiple roots.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move/delete files. Without this option, dry-run mode is used.",
    )

    args = parser.parse_args()

    dest_root = Path(args.dest).resolve()
    source_roots = [Path(s).resolve() for s in args.source]
    dry_run = not args.execute

    print(f"Destination: {dest_root}")
    print(f"Mode: {'EXECUTE' if not dry_run else 'DRY-RUN'}")
    print()

    if dry_run:
        print("This is a dry-run. No files will be changed.")
        print("Add --execute after checking the output.")
        print()

    if not dest_root.exists():
        print(f"[INFO] Destination does not exist yet: {dest_root}")
        if not dry_run:
            dest_root.mkdir(parents=True, exist_ok=True)

    all_candidates: list[tuple[Path, Path]] = []

    for source_root in source_roots:
        if not source_root.exists():
            print(f"[WARN] Source does not exist: {source_root}")
            continue

        if source_root == dest_root or is_relative_to(source_root, dest_root):
            print(f"[WARN] Source is destination or under destination, skipped: {source_root}")
            continue

        print(f"[SCAN] {source_root}")
        candidates = find_song_folders(source_root, dest_root)
        print(f"[FOUND] {len(candidates)} song folders")
        for c in candidates:
            all_candidates.append((c, source_root))

    # 浅い順に処理
    all_candidates.sort(key=lambda x: len(x[0].parts))

    print()
    print(f"Total song folders: {len(all_candidates)}")

    for src_song_dir, source_root in all_candidates:
        if not src_song_dir.exists():
            print(f"[SKIP] source no longer exists: {src_song_dir}")
            continue

        process_song_folder(
            src_song_dir=src_song_dir,
            dest_root=dest_root,
            source_root=source_root,
            dry_run=dry_run,
        )

    print()
    print("Done.")


if __name__ == "__main__":
    main()