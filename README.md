# rebase-helper

A script for use during an interactive `git rebase` when history shows a
file as *moved* from an old solution into a new one, but you want an
alternate branch where the old solution is left completely unchanged (i.e.
the move becomes a copy) while still preserving git history for the new
location.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- A git checkout with `git rebase -i` in progress

## Usage

1. Start (or resume) an interactive rebase and mark the commits that
   contain moves you want to fix up as `edit`:

   ```sh
   git rebase -i <base>
   ```

2. When the rebase stops on a commit, run the script from the repo root,
   pointing it at the old and new solution directories:

   ```sh
   uv run main.py --old-prefix src/OldSolution --new-prefix src/NewSolution
   ```

   For each file renamed from under `--old-prefix` to under `--new-prefix`
   in the current commit (`HEAD`, compared against `HEAD~1`), the script
   restores the file's pre-move content into the old path and stages it,
   so the commit ends up containing both the untouched original file and
   the moved file.

   Files that were already recognized as copies (rather than renames) are
   left alone and just logged, since the original file is already present.

   Plain deletions under `--old-prefix` with no corresponding path under
   `--new-prefix` (e.g. a file that became an orphan after other files
   moved out and was deleted in the same commit) are restored the same
   way as renames.

3. Review the staged changes, then amend the commit and continue the
   rebase:

   ```sh
   git status
   git diff --cached
   git commit --amend --no-edit
   git rebase --continue
   ```

   Repeat from step 2 for each commit the rebase stops on.

### Options

| Flag | Description |
| --- | --- |
| `--old-prefix` | Directory prefix of the original solution, e.g. `src/OldSolution` (required) |
| `--new-prefix` | Directory prefix of the new solution, e.g. `src/NewSolution` (required) |
| `--repo` | Path to the git repository (default: current directory) |
| `--dry-run` | Report what would be restored without touching the working tree |

## Development

```sh
uv run main.py --help
```
