"""Restore original-solution files during an interactive rebase.

Usage: run this after `git rebase -i` stops on a commit (via `edit`), before
amending it. It compares HEAD^ (the previous commit in the rebased history)
to HEAD (the commit currently being replayed) using rename/copy detection.
For every rename whose source is under --old-prefix and destination is under
--new-prefix, it restores the source path's pre-move content (as it was in
HEAD^, unchanged) into the working tree and stages it, so the commit ends up
containing both the untouched original-solution file and the moved
new-solution file. Pure copies matching the prefixes are only verified and
logged, since the original-solution file is already present. Plain deletions
under --old-prefix (e.g. a file that became an orphan after other files
moved out and was deleted in the same commit, with no corresponding path
under --new-prefix) are restored the same way as renames. Plain
modifications to files that stayed under --old-prefix (edits that slipped
into the same commit as an unrelated move) are reverted to their HEAD^
content as well.

    uv run main.py --old-prefix src/OldSolution --new-prefix src/NewSolution
    git status  # review
    git commit --amend --no-edit
    git rebase --continue
"""

import argparse
import sys
from pathlib import Path
from typing import cast

from git import Repo
from git.objects.blob import Blob


def find_prefixed_changes(
    repo: Repo, old_prefix: str, new_prefix: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str], list[str]]:
    diff_index = repo.commit("HEAD~1").diff(
        repo.commit("HEAD"),
        find_copies_harder=True,
        M=True,
        C=True,
    )

    renames: list[tuple[str, str]] = []
    copies: list[tuple[str, str]] = []
    deletions: list[str] = []
    modifications: list[str] = []
    for diff in diff_index:
        if diff.change_type == "D":
            src = diff.a_path
            if src is not None and src.startswith(old_prefix + "/"):
                deletions.append(src)
            continue

        if diff.change_type == "M":
            src = diff.a_path
            if src is not None and src.startswith(old_prefix + "/"):
                modifications.append(src)
            continue

        if diff.change_type not in ("R", "C"):
            continue
        src, dst = diff.a_path, diff.b_path
        if src is None or dst is None:
            continue
        if not (src.startswith(old_prefix + "/") and dst.startswith(new_prefix + "/")):
            continue
        if diff.change_type == "R":
            renames.append((src, dst))
        elif diff.change_type == "C":
            copies.append((src, dst))

    return renames, copies, deletions, modifications


def restore_path(repo: Repo, path: str, dry_run: bool) -> None:
    blob = cast(Blob, repo.commit("HEAD~1").tree / path)
    data = cast(bytes, blob.data_stream.read())
    assert repo.working_tree_dir is not None
    target = Path(repo.working_tree_dir) / path

    print(f"[restore] {path} (unchanged content from HEAD~1)")
    if dry_run:
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    repo.index.add([path])  # pyright: ignore[reportUnknownMemberType]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old-prefix", required=True, help="Directory prefix of the original solution, e.g. src/OldSolution")
    parser.add_argument("--new-prefix", required=True, help="Directory prefix of the new solution, e.g. src/NewSolution")
    parser.add_argument("--repo", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be restored without touching the working tree")
    args = parser.parse_args()

    old_prefix = args.old_prefix.rstrip("/")
    new_prefix = args.new_prefix.rstrip("/")

    repo = Repo(args.repo, search_parent_directories=True)
    if repo.bare:
        print("error: repository is bare", file=sys.stderr)
        return 1

    try:
        repo.commit("HEAD~1")
    except Exception:
        print("error: HEAD has no parent commit to diff against", file=sys.stderr)
        return 1

    renames, copies, deletions, modifications = find_prefixed_changes(repo, old_prefix, new_prefix)

    for src, dst in copies:
        print(f"[copy, no action] {src} -> {dst} already recognized as a copy; original is already present")

    to_restore = [src for src, _dst in renames] + deletions + modifications

    if not to_restore:
        print("No matching renames, deletions, or modifications found between HEAD~1 and HEAD for the given prefixes.")
        return 0

    for src in to_restore:
        restore_path(repo, src, args.dry_run)

    if args.dry_run:
        print(f"Dry run: {len(to_restore)} file(s) would be restored. Nothing written or staged.")
    else:
        print(f"Restored and staged {len(to_restore)} file(s).")
        print("Review with `git status` / `git diff --cached`, then run `git commit --amend --no-edit`.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
