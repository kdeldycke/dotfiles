#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shrink an Apple Photos library: replace videos with smaller copies, merge duplicates.

Photos cannot replace the file of an asset, and `osxphotos` cannot encode a
video. So each video makes a round trip through a work directory, and each
subcommand is one step of it:

1. `export` copies the original out of the library with `osxphotos export`. It
   downloads the original from iCloud first when the library has no local copy.
2. `encode` writes an HEVC copy with `ffmpeg`, copies the metadata onto it with
   `exiftool`, and compares the copy with the original. A copy that differs, or
   that saves too little, is rejected: that video keeps its original.
3. `import` adds each accepted copy to the library with `osxphotos import`. The
   export database gives the new asset the date, location, title, description,
   keywords, favorite flag and albums of its original.
4. `check` reads each original and its new asset back from the Photos database
   and compares them field by field.
5. `mark` adds each original whose new asset passed `check` to an album.

The last step is manual: delete the content of that album in Photos, because
`osxphotos` has no delete command. `mark` runs after `check`, so the album only
holds an original that has a verified replacement.

`run` takes a list of videos through the first three steps one at a time, and
runs `check` and `mark` at intervals. `import` removes the exported original of
each copy that it adds: the original stays in the library and in iCloud until
the manual delete. The copy goes once its video is kept, or marked with its new
asset in iCloud. `status` prints the totals of a work directory.

`import`, `mark` and `dedup` drive Photos through AppleScript, and `export`
downloads through PhotoKit. Run them from a terminal that macOS lets control
Photos and read the Photos library. Without the first permission, `osxphotos`
reports each asset as missing or invalid and names no cause: `osascript` shows
the real error. `import`, `mark` and `dedup` are the steps that change the
library, and each takes `--dry-run`, as does `run`.

The download does not use the AppleScript route of `osxphotos`. That route
gives Photos 120 seconds per file, has no option to change that, and quits
Photos when the limit passes.

`import`, `mark` and `dedup` start Photos themselves when it is closed, and wait
until it answers. When `osxphotos` starts Photos, or starts it again after it quit
Photos on a timeout, that Photos has no window. In a test, an import sent to
such a Photos did not complete, and the same import took 7 seconds once Photos
was open with its window. So a failed `osxphotos` command quits Photos, and the
next step opens it the normal way. A Photos that stays silent restarts the same
way, up to `PHOTOS_RESTARTS` times.

An import that Photos cut short can leave the new asset out of some albums of
its original. `run` adds the asset to the albums it lacks, and `check` then
verifies it.

`encode` writes the date and the time zone that Photos shows for the original
into the `Keys:CreationDate` tag of the copy. Photos reads the time zone of a
new asset from that tag, which most camera files lack. When the offset that
Photos stores for the original disagrees with the date that it shows, the new
asset takes the offset of that date, and `check` accepts the difference.

`encode` keeps no text tag in the copy: no title, description, keywords or
comment. The import sets those fields from the export database, so a text tag in
the file can only add text that Photos never showed for the original. A DJI drone
writes its app version as the comment, `ffmpeg` wrote that comment into a `.mov`
copy as a description atom too, and Photos showed the version as the description
of the new asset.

With `--trim`, the round trip takes edited videos instead: each one whose enabled
edits are a trim, and at most a mute and a poster frame. Its `encode` step cuts
the original to the frames that the trim shows, with no re-encoding. `ffmpeg`
copies the packets from the key frame before the first kept frame, and the edit
list of each track hides what the cut holds before and after the kept frames. An
iPhone video holds a Dolby Vision box and `mebx` metadata tracks, which `ffmpeg`
drops: AVFoundation's passthrough export cuts it instead, and keeps both. The
step then checks the cut against the original: the bytes of each packet, the
decoded frames and audio samples, the durations, and the tracks and the format
boxes. A cut that drops a track or a box is rejected, and its video keeps its
original. The new asset has no edits, so it loses a poster frame that differs
from its first frame. An H.264 new asset can get an HEVC copy in a later run.

`osxphotos export --use-photokit` writes the edited render in place of the
original of an edited video: it gives PhotoKit the image constant for the
original, 2, where the video constant is 1. So `--trim` exports the original
again through `osxphotos run`, with the image constant whose value is 1.

The work directory holds one directory per asset UUID under `export/`, and the
same layout under `encoded/`. Each file keeps its exact name there, and that
name becomes the name of the new asset. A flat export renames the second of two
files that have the same name. The layout also lets the export database, which
finds a file by its relative path, match a copy to the record of its original.
`state.json` records the step each video reached, so each subcommand skips the
work that an earlier run completed, and a cut run resumes where it stopped:

- A video replaced or kept is never selected again. Its new HEVC asset is not
  selected either, because the selection takes H.264 videos only.
- A step that a crash cut starts again from the files of its own step: an
  export or an encode first removes what the cut run left in its directory.
- An encode counts as done only when `state.json` records its end with the
  current encoder settings. In any doubt, it runs again from the start.
- Before an import, a lookup by name and size finds a copy that a cut import
  already added to Photos, so no copy reaches the library twice.
- A video that fails `MAX_ATTEMPTS` runs is skipped, and `status` lists it.
- A video in the album of `mark` is never selected: it waits for its delete.
- One lock file lets only one process change a work directory at a time.

`dedup` finds the sets of assets that hold the same original file: Photos gives
them the same fingerprint, and their originals have the same size. Each set keeps
one asset: the edited one, then the favorite, then the one in more albums, then
the one added first. The kept asset joins every album of the set. It also takes
the favorite flag and the keywords of the other copies, and a title, description
or location that only a copy holds. `dedup` then reads the set again, and adds
each copy to the album of `mark` when the kept asset holds all that the copy
holds. A set whose copies differ in a way that no option can merge, like edits on
two copies, two titles, or a date set on a copy, stays as it is for a person.

Run `dedup` before a batch. `dedup` leaves out the assets in the album of `mark`,
so a copy of an original that a batch marked stays in the library.

Usage:
    photos_shrink.py run --work {directory} --uuid {uuid} [--dry-run]
    photos_shrink.py run --work {directory} --min-size {size} [--limit {n}]
    photos_shrink.py run --work {directory} --trim --min-size {size} [--list]
    photos_shrink.py status --work {directory}
    photos_shrink.py export --work {directory} --uuid {uuid} [--trim]
    photos_shrink.py encode --work {directory}
    photos_shrink.py import --work {directory} [--dry-run]
    photos_shrink.py check --work {directory}
    photos_shrink.py mark --work {directory} [--dry-run]
    photos_shrink.py dedup --work {directory} [--dry-run]
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from fractions import Fraction
from pathlib import Path

# Album that receives each new asset, to review a batch in Photos.
ALBUM_NEW = "Recompressed new"

# Album that receives an original once its new asset passed `check`. Its content
# is the list to delete by hand in Photos.
ALBUM_ORIGINALS = "Recompressed originals to delete"

# Seconds of audio, at most, that a cut copies before its first kept sample. The
# AAC decoder overlaps each packet with the one before it, and `ffmpeg` starts the
# audio at the video key frame, which can leave no packet before the cut.
AUDIO_PREROLL = Fraction(1)

# Seconds between two rounds of `check` and `mark` during `run`. Each round
# reads the whole Photos database, which takes about 15 seconds.
CHECK_INTERVAL = 1800

# Stream facts that must be the same in an original and in its encoded copy.
CHECKED_FACTS = ("display_size", "frames", "color", "audio")

# ffprobe keys that say how to read the pixel values.
COLOR_KEYS = ("color_range", "color_space", "color_transfer", "color_primaries")

# exiftool groups that the tag copy takes from the original. ffmpeg keeps either
# the Apple `Keys` tags or the `UserData` location, depending on its flags.
COPIED_GROUPS = ("ItemList", "Keys", "UserData")

# Codec tags of the data tracks that a cut copies: the GoPro telemetry.
CUT_DATA_TAGS = ("gpmd",)

# Codec tags of the tracks that a cut leaves out on purpose: the GoPro recovery
# data, and the timecode, which `ffmpeg` would write for the start of the original.
CUT_DROPS = ("fdsc", "tmcd")

# Format boxes that a cut can drop when they hold these exact bytes. `ffmpeg`
# writes no `chrm` box, and an all-zero one sets no chroma location: CoreMedia
# reads the same one from a cut without it.
CUT_EMPTY_BOXES = {"chrm": b"\x00\x00"}

# Value of the `encoder` field of a finished cut. Change it with the cut logic, so
# that a cut of an earlier version runs again.
CUT_SIGNATURE = "stream copy cut 2"

# Seconds of the original that the check of a cut reads on each side of the kept
# frames. The cut copies at most one group of pictures before them.
CUT_WINDOW = 10

# Container dates that the tag copy takes from the original.
DATE_TAGS = (
    "CreateDate",
    "ModifyDate",
    "TrackCreateDate",
    "TrackModifyDate",
    "MediaCreateDate",
    "MediaModifyDate",
)

# Seconds that PhotoKit gets to download one original from iCloud. In a test,
# downloads ran at 0.8 MiB/s: that is 11 GiB in this time.
DOWNLOAD_TIMEOUT = 4 * 3600

# Asset flags that each copy of a set of duplicates must share, with the words
# for each. `dedup` leaves a set whose copies differ in one to a person.
DUPLICATE_FLAGS = {
    "has_raw": "a RAW file",
    "hidden": "the hidden flag",
    "live_photo": "a Live Photo video",
}

# osxphotos query that prints the fields that find duplicates, for each asset that
# `dedup` can merge or mark. It leaves out the assets that other people share.
DUPLICATE_SCAN = (
    *("--not-shared", "--not-shared-library", "--not-syndicated"),
    *("--quiet", "--mute"),
    *("--print", "{uuid} {photo.fingerprint} {photo.original_filesize}"),
)

# ffmpeg arguments for the video stream. A lower `-crf` keeps more quality.
ENCODER = (
    *("-c:v", "libx265", "-preset", "medium", "-crf", "22"),
    *("-x265-params", "log-level=error"),
)

# Name of the database that `osxphotos export` keeps in its target directory.
EXPORT_DB = ".osxphotos_export.db"

# osxphotos template of the directory, under `export/`, that each asset gets.
EXPORT_LAYOUT = "{uuid}"

# Videos in a row that may fail before `run` stops: more point to a fault that
# every video shares, like a stuck Photos.
FAILURE_LIMIT = 3

# Steps after which a video needs no more work from `run`.
FINISHED = ("kept", "marked")

# Words for the handler types of movie tracks, in the messages of the cut check.
HANDLER_NAMES = {
    "meta": "metadata",
    "soun": "audio",
    "tmcd": "timecode",
    "vide": "video",
}

# File that a process locks while it changes the work directory.
LOCK_FILE = ".lock"

# Largest gap, in degrees, between two coordinates that count as the same place.
LOCATION_TOLERANCE = 1e-5

# Runs in which a video may fail before `run` skips it in its selection.
MAX_ATTEMPTS = 2

# Times that `run` adds a new asset to the albums it lacks, before it leaves the
# fix to a person.
MAX_REPAIRS = 2

# Disk space, in bytes, that `run` keeps on top of three times the size of the
# next original: its export, its copy, and its download into the library.
MIN_FREE = 50 * 2**30

# JavaScript for `osascript` that prints the disk space for important use, which
# counts what macOS can purge on demand. Photos keeps each downloaded original
# on disk, so that space can be more than twice the free space.
IMPORTANT_SPACE = (
    'function run(argv) { ObjC.import("Foundation"); const ref = Ref(); '
    "$.NSURL.fileURLWithPath(argv[0]).getResourceValueForKeyError(ref, "
    '"NSURLVolumeAvailableCapacityForImportantUsageKey", null); '
    "return String(ObjC.unwrap(ref[0])); }"
)

# Smallest share of the original size that a copy must save to replace it.
MIN_SAVING = 0.2

# Format boxes of a video sample description that `ffmpeg` drops from a `.mov`
# cut: the Dolby Vision configurations. A source with one goes through AVFoundation.
PASSTHROUGH_BOXES = ("dvcC", "dvvC", "dvwC")

# Python file that `osxphotos run` executes to cut a movie with AVFoundation's
# passthrough export: `{file} {source} {target} {first} {stop} {timescale}`. It
# keeps the times from `first` to `stop`, in units of 1/`timescale` s.
PASSTHROUGH_CUT = """\
import sys
import threading

import AVFoundation
import CoreMedia
import Foundation

source, target, first, stop, timescale = sys.argv[1:6]
asset = AVFoundation.AVURLAsset.URLAssetWithURL_options_(
    Foundation.NSURL.fileURLWithPath_(source), None
)
session = AVFoundation.AVAssetExportSession.exportSessionWithAsset_presetName_(
    asset, AVFoundation.AVAssetExportPresetPassthrough
)
session.setOutputURL_(Foundation.NSURL.fileURLWithPath_(target))
if target.lower().endswith(".mov"):
    session.setOutputFileType_(AVFoundation.AVFileTypeQuickTimeMovie)
else:
    session.setOutputFileType_(AVFoundation.AVFileTypeMPEG4)
session.setTimeRange_(
    CoreMedia.CMTimeRangeFromTimeToTime(
        CoreMedia.CMTimeMake(int(first), int(timescale)),
        CoreMedia.CMTimeMake(int(stop), int(timescale)),
    )
)
done = threading.Event()
session.exportAsynchronouslyWithCompletionHandler_(done.set)
done.wait()
if session.status() != AVFoundation.AVAssetExportSessionStatusCompleted:
    sys.exit(f"the passthrough export failed: {session.error()}")
"""

# Codec tags of the data tracks that `ffmpeg` cannot write: Apple's timed metadata,
# like the faces that an iPhone detects. A source with one goes through AVFoundation.
PASSTHROUGH_TAGS = ("mebx",)

# Python file that `osxphotos run` executes to export the unedited original of
# a video into a directory: `{file} {uuid} {directory}`. `PHOTOS_VERSION_UNADJUSTED`
# holds 1, the value of `PHVideoRequestOptionsVersionOriginal`.
PHOTOKIT_ORIGINAL = """\
import sys
from osxphotos.photokit import PHOTOS_VERSION_UNADJUSTED, PhotoLibrary

asset = PhotoLibrary().fetch_uuid(sys.argv[1])
for path in asset.export(sys.argv[2], version=PHOTOS_VERSION_UNADJUSTED):
    print(path)
"""

# AppleScript that asks Photos how many items its library holds.
PHOTOS_QUESTION = 'tell application "Photos" to count of media items'

# Seconds that Photos gets to quit before it is forced to quit.
PHOTOS_QUIT_WAIT = 30

# Times that `ready_photos` restarts a Photos that stays silent, before it exits.
PHOTOS_RESTARTS = 2

# Seconds that Photos gets to open its library and answer that question.
PHOTOS_TIMEOUT = 300

# Errors that a probe of an unusual file can raise.
PROBE_ERRORS = (RuntimeError, KeyError, IndexError, StopIteration)

# Asset fields that must be equal in an original and in its new asset.
SAME_FIELDS = (
    "original_filename",
    "favorite",
    "hidden",
    "title",
    "description",
    "keywords",
)

# osxphotos query that selects the videos of a batch, on top of `--min-size`.
SELECTION = (
    *("--only-movies", "--not-edited", "--not-shared"),
    *("--query-eval", "photo.exif_info and photo.exif_info.codec == 'avc1'"),
)

# osxphotos template fields that print the characters that its template parser
# reads. A text value takes them in place of those characters: see `literal`.
TEMPLATE_ESCAPES = {
    ",": "{comma}",
    "?": "{questionmark}",
    "{": "{openbrace}",
    "}": "{closebrace}",
}

# ffmpeg metadata keys that `encode` leaves out of each copy. In a `.mov` copy,
# ffmpeg writes the comment twice, as the `©cmt` and `©des` atoms, and exiftool
# can only delete the first one.
TEXT_KEYS = ("comment", "description", "keywords", "title")

# exiftool names of the text tags that `copy_tags` deletes from each copy, after
# it copies the tags of the original. exiftool calls the keywords `Keyword` in
# the `ItemList` group and `Keywords` in the other groups.
TEXT_TAGS = ("Comment", "Description", "Keyword", "Keywords", "Title")

# Photos edits that a cut applies. A trim must be among the enabled edits.
TRIM_EDITS = frozenset(("Mute", "Trim", "VideoPosterFrame"))

# osxphotos query that selects the videos of a `--trim` batch, on top of
# `--min-size`. `trim_edit` then keeps the videos that a cut can apply.
TRIM_SELECTION = ("--only-movies", "--edited", "--not-shared")

# Name that osxphotos gives to a person that nobody named in Photos.
UNNAMED_PERSON = "_UNKNOWN_"

# Seconds that `run` waits, at its end, for the last new assets to reach iCloud.
UPLOAD_WAIT = 7200

# Verdicts of one compared field. `SAME`, `OK` and `INFO` let `check` pass a
# video. `INFO` marks a field that `check` shows but does not compare, a location
# that the new asset gains from its own file, and a time zone offset that the new
# asset corrects to match the date that both assets show.
DIFFERENT = "DIFFERENT"
INFO = "info"
OK = "ok"
PENDING = "pending"
SAME = "same"


def tool(name: str) -> str:
    """Return the path of a command-line tool, or exit when it is missing."""
    found = shutil.which(name)
    if not found:
        sys.exit(f"{name} is not on PATH.")
    return found


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command and return its output, or raise when it exits with an error."""
    done = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="UTF-8",
        errors="replace",
        check=False,
    )
    if done.returncode:
        raise RuntimeError(
            f"{Path(args[0]).name} failed with exit code {done.returncode}: "
            f"{done.stderr.strip()[-600:]}"
        )
    return done


def drive(args: list[str], work: Path, extra_env: dict[str, str] | None = None) -> bool:
    """Run a command that prints its own progress, and return whether it passed.

    The command runs in the work directory, because `osxphotos` writes its crash
    log to the current directory.
    """
    extra_env = extra_env or {}
    settings = [f"{name}={shlex.quote(value)}" for name, value in extra_env.items()]
    print("$ " + " ".join([*settings, shlex.join(args)]), flush=True)
    env = {**os.environ, **extra_env}
    work.mkdir(parents=True, exist_ok=True)
    return subprocess.run(args, cwd=work, env=env, check=False).returncode == 0


def photos_running() -> bool:
    """Return whether the Photos app runs."""
    found = subprocess.run(
        [tool("pgrep"), "-x", "Photos"], capture_output=True, check=False
    )
    return found.returncode == 0


def quit_photos() -> None:
    """Quit Photos, and force it to quit when it ignores the first request."""
    for flag in ("-TERM", "-KILL"):
        subprocess.run(
            [tool("killall"), flag, "Photos"], capture_output=True, check=False
        )
        deadline = time.monotonic() + PHOTOS_QUIT_WAIT
        while photos_running() and time.monotonic() < deadline:
            time.sleep(1)
        if not photos_running():
            return
    sys.exit("Photos does not quit.")


def wait_for_photos() -> str | None:
    """Ask Photos how many items it holds, until it answers.

    :return: None once Photos answers, or the last problem when it stays silent
        for `PHOTOS_TIMEOUT` seconds.
    """
    deadline = time.monotonic() + PHOTOS_TIMEOUT
    while True:
        try:
            if int(run([tool("osascript"), "-e", PHOTOS_QUESTION]).stdout) > 0:
                return None
            problem = "its library shows no item"
        except (RuntimeError, ValueError) as error:
            problem = str(error)
        if "-1743" in problem:
            sys.exit(f"Photos refuses AppleScript from this terminal: {problem}")
        if time.monotonic() > deadline:
            return problem
        time.sleep(2)


def ready_photos() -> None:
    """Start Photos the normal way when it is closed, and wait until it answers.

    A direct question to Photos also shows a refused Automation permission,
    which `osxphotos` hides. A Photos that stays silent restarts, up to
    `PHOTOS_RESTARTS` times: after `osxphotos` quits Photos, it comes back with
    no window and an unloaded library, and answers after minutes or not at all.
    """
    problem = None
    for _ in range(PHOTOS_RESTARTS + 1):
        if problem is not None:
            print(f"Photos is silent: {problem}", file=sys.stderr)
            print("Restarting Photos.", file=sys.stderr, flush=True)
            quit_photos()
        if not photos_running():
            run([tool("open"), "-a", "Photos"])
        problem = wait_for_photos()
        if problem is None:
            return
    sys.exit(f"Photos is not ready: {problem}. Quit it and open it again.")


def drive_photos(args: list[str], work: Path, dry_run: bool = False) -> bool:
    """Run an `osxphotos` command that drives Photos, and return whether it passed.

    Photos starts first, except in a dry run. A command that fails has often made
    Photos quit on a timeout, and Photos then comes back with no window. So a
    failure quits Photos, and the next step opens it the normal way.
    """
    if not dry_run:
        ready_photos()
    passed = drive(args, work)
    if not passed and not dry_run:
        print("The command failed: quitting Photos.", file=sys.stderr, flush=True)
        quit_photos()
    return passed


def keep_awake() -> None:
    """Keep the Mac from sleeping on idle until this process ends."""
    try:
        subprocess.Popen([tool("caffeinate"), "-i", "-w", str(os.getpid())])
    except OSError as error:
        print(f"caffeinate did not start, so the Mac can sleep: {error}")


def lock_work(work: Path) -> object:
    """Lock the work directory for this process, or exit when another holds it.

    :return: The open lock file. The lock lasts as long as the file stays open.
    """
    work.mkdir(parents=True, exist_ok=True)
    handle = (work / LOCK_FILE).open("w", encoding="UTF-8")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"Another process uses {work}: wait for it to end.")
    return handle


def load_state(work: Path) -> dict[str, dict]:
    """Return the recorded step of each video, by the UUID of its original."""
    path = work / "state.json"
    if not path.exists():
        return {}
    state: dict[str, dict] = json.loads(path.read_text(encoding="UTF-8"))
    return state


def save_state(work: Path, state: dict[str, dict]) -> None:
    """Record the step of each video, through a file swap that a crash cannot cut."""
    work.mkdir(parents=True, exist_ok=True)
    partial = work / "state.json.partial"
    partial.write_text(json.dumps(state, indent=2) + "\n", encoding="UTF-8")
    partial.replace(work / "state.json")


def summary(state: dict[str, dict]) -> None:
    """Print how many videos are at each step."""
    counts: dict[str, int] = {}
    for record in state.values():
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    steps = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    print(f"Videos: {steps or 'none'}.")


def photos(uuids: list[str]) -> dict[str, dict]:
    """Return the Photos record of each asset by UUID, trashed assets included."""
    if not uuids:
        return {}
    args = [tool("osxphotos"), "query", "--deleted", "--json"]
    for uuid in uuids:
        args += ["--uuid", uuid]
    return {photo["uuid"]: photo for photo in json.loads(run(args).stdout)}


def trim_edit(photo: dict) -> dict | None:
    """Return the trim of an edited video that a cut can apply, or None.

    A cut applies the edits of `TRIM_EDITS`, and only when a trim is among them.
    An edit counts when its `enabled` flag is true or missing: Photos keeps an
    edit that a person turned off, and that edit changes nothing.

    :return: The trim start and end as `value/timescale` text, and whether the
        edits mute the video.
    """
    adjustments = (photo.get("adjustments") or {}).get("adjustments") or []
    enabled = {
        item.get("identifier"): item.get("settings") or {}
        for item in adjustments
        if isinstance(item, dict) and item.get("enabled", True)
    }
    if "Trim" not in enabled or not set(enabled) <= TRIM_EDITS:
        return None
    times = {key: enabled["Trim"][f"{key}Time"] for key in ("start", "end")}
    return {
        **{key: f"{time['value']}/{time['timescale']}" for key, time in times.items()},
        "mute": "Mute" in enabled,
    }


def refusal(photo: dict | None, trim: bool = False) -> str | None:
    """Return why a video cannot make the round trip, or None when it can.

    :param trim: Whether the round trip cuts the video to its trim.
    """
    if photo is None:
        return "it is not in the library"
    if not photo["ismovie"]:
        return "it is not a video"
    if photo["intrash"]:
        return "it is in Recently Deleted"
    if photo["shared"]:
        return "it is in a shared album"
    if trim:
        if trim_edit(photo) is None:
            return "it has no trim, or an edit that a cut cannot apply"
        return None
    if photo["hasadjustments"]:
        return "it has edits, which a new asset cannot keep"
    if (photo["exif_info"] or {}).get("codec") == "hvc1":
        return "it is HEVC already"
    return None


def export_original(uuid: str, path: Path, args: argparse.Namespace) -> None:
    """Replace an exported file with the unedited original, through PhotoKit.

    The file keeps its path, which the export database records for the import.
    """
    helper = args.work / ".photokit_original.py"
    helper.write_text(PHOTOKIT_ORIGINAL, encoding="UTF-8")
    with tempfile.TemporaryDirectory(dir=args.work) as scratch:
        command = [tool("osxphotos"), "run", str(helper), uuid, scratch]
        extra_env = {"OSXPHOTOS_PHOTOKIT_TIMEOUT": str(args.download_timeout)}
        if not drive(command, args.work, extra_env):
            raise RuntimeError("the export of the unedited original failed")
        found = [item for item in Path(scratch).iterdir() if item.is_file()]
        if len(found) != 1:
            raise RuntimeError(f"the export of the original wrote {len(found)} files")
        found[0].replace(path)


def export_videos(args: argparse.Namespace, uuids: list[str] | None = None) -> bool:
    """Copy each selected original out of the library, one directory per UUID."""
    state = load_state(args.work)
    export_dir = args.work / "export"
    trim = getattr(args, "trim", False)
    uuids = [uuid.upper() for uuid in uuids or args.uuid]
    retry = [u for u in uuids if state.get(u, {}).get("status", "failed") == "failed"]
    library = photos(retry)
    passed = True
    wanted = []
    for uuid in uuids:
        if uuid not in retry:
            print(f"{uuid}: already at step {state[uuid]['status']!r}.")
            continue
        reason = refusal(library.get(uuid), trim)
        if reason:
            print(f"{uuid}: refused, {reason}.", file=sys.stderr)
            passed = False
            continue
        wanted.append(uuid)
    for uuid in wanted:
        # osxphotos gives a new name to a file that a cut export left behind.
        for leftover in (export_dir / uuid).glob("*"):
            leftover.unlink()
    if wanted:
        export_dir.mkdir(parents=True, exist_ok=True)
        command = [tool("osxphotos"), "export", str(export_dir)]
        for uuid in wanted:
            command += ["--uuid", uuid]
        command += ["--directory", EXPORT_LAYOUT]
        command += ["--only-movies", "--update", "--verbose"]
        if trim:
            command.append("--skip-edited")
        extra_env = {}
        if args.download_missing:
            command += ["--download-missing", "--use-photokit"]
            extra_env["OSXPHOTOS_PHOTOKIT_TIMEOUT"] = str(args.download_timeout)
        passed = drive(command, args.work, extra_env) and passed
    for uuid in wanted:
        files = [
            path
            for path in sorted((export_dir / uuid).glob("*"))
            if path.is_file() and not path.name.startswith(".")
        ]
        if len(files) != 1:
            print(f"{uuid}: {len(files)} exported files, not 1.", file=sys.stderr)
            passed = False
            continue
        if trim:
            try:
                export_original(uuid, files[0], args)
            except RuntimeError as error:
                print(f"{uuid}: {error}.", file=sys.stderr)
                passed = False
                continue
        size = files[0].stat().st_size
        photo = library[uuid]
        if size != photo["original_filesize"]:
            print(
                f"{uuid}: the export holds {size} bytes "
                f"and the original {photo['original_filesize']}.",
                file=sys.stderr,
            )
            passed = False
            continue
        state[uuid] = {
            "date": photo["date"],
            "name": files[0].name,
            "source_bytes": size,
            "status": "exported",
            "tzoffset": photo["tzoffset"],
        }
        if trim:
            codec = (photo["exif_info"] or {}).get("codec")
            state[uuid].update(mode="trim", trim=trim_edit(photo), codec=codec)
        print(f"{uuid}: exported {files[0].name}, {size / 2**20:.0f} MiB.")
    save_state(args.work, state)
    return passed


def encode(src: Path, dst: Path) -> float:
    """Encode the video stream to HEVC, copy the audio, and return the seconds.

    `ffmpeg` writes to a partial file first, so a file at `dst` is always whole.
    The copy takes the metadata of the original, except the keys of `TEXT_KEYS`.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(f".partial-{dst.name}")
    start = time.monotonic()
    run([
        *(tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"),
        *("-i", str(src)),
        *("-map", "0:v:0", "-map", "0:a?"),
        *ENCODER,
        *("-tag:v", "hvc1"),
        *("-c:a", "copy"),
        *("-map_metadata", "0"),
        *(arg for key in TEXT_KEYS for arg in ("-metadata", f"{key}=")),
        str(partial),
    ])
    seconds = time.monotonic() - start
    partial.replace(dst)
    return seconds


def copy_tags(src: Path, dst: Path) -> None:
    """Copy the metadata tags and the container dates of the original.

    The copy names each group. It leaves out the track matrix, because `ffmpeg`
    already applied the rotation to the pixels. It then deletes the text tags of
    `TEXT_TAGS` from the copy.
    """
    run([
        *(tool("exiftool"), "-quiet", "-overwrite_original"),
        *("-api", "LargeFileSupport=1"),
        *("-tagsFromFile", str(src)),
        *(f"-{group}:All" for group in COPIED_GROUPS),
        *(f"-QuickTime:{tag}" for tag in DATE_TAGS),
        *(f"-{tag}=" for tag in TEXT_TAGS),
        str(dst),
    ])


def facts(path: Path) -> dict:
    """Return the stream facts of a video that `encode` must not change."""
    probe = (tool("ffprobe"), "-hide_banner", "-loglevel", "error", "-of", "json")
    info = json.loads(
        run([
            *probe,
            *("-count_frames", "-count_packets", "-show_streams", "-show_format"),
            str(path),
        ]).stdout
    )
    # The stream summary can contradict the bitstream, so read a decoded frame.
    first_frames = json.loads(
        run([
            *probe,
            *("-select_streams", "v:0", "-read_intervals", "%+3", "-show_frames"),
            *("-show_entries", f"frame={','.join(COLOR_KEYS)}"),
            str(path),
        ]).stdout
    )["frames"]
    streams = info["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    rotation = next(
        (
            int(d["rotation"])
            for d in video.get("side_data_list", [])
            if "rotation" in d
        ),
        0,
    )
    size = (video["width"], video["height"])
    if rotation % 180:
        size = size[::-1]
    colors = {key: first_frames[0].get(key) for key in COLOR_KEYS}
    # A stream that names no range uses the limited one, which an encoder writes out.
    if colors["color_range"] in (None, "unknown"):
        colors["color_range"] = "tv"
    return {
        "audio": (
            f"{audio['codec_name']} {audio['channels']}ch "
            f"{audio['nb_read_packets']} packets"
            if audio
            else None
        ),
        "codec": f"{video['codec_name']}/{video['codec_tag_string']}",
        "color": "/".join(str(colors[key]) for key in COLOR_KEYS),
        "display_size": f"{size[0]}x{size[1]}",
        "duration": float(info["format"]["duration"]),
        # A trimmed clip holds packets outside its edit list: count decoded frames.
        "frames": int(video["nb_read_frames"]),
    }


def differences(src: Path, dst: Path) -> list[str]:
    """Return each way an encoded copy differs from its original."""
    before = facts(src)
    after = facts(dst)
    found = [
        f"{key}: {before[key]} -> {after[key]}"
        for key in CHECKED_FACTS
        if before[key] != after[key]
    ]
    if after["codec"] != "hevc/hvc1":
        found.append(f"codec: {after['codec']}")
    if abs(before["duration"] - after["duration"]) > 0.1:
        found.append(f"duration: {before['duration']} -> {after['duration']}")
    return found


def stamp_date(record: dict, dst: Path) -> None:
    """Write the date and time zone of the original asset into the copy.

    Photos took the time zone of an imported iPhone video from this tag. A camera
    file has no such tag, so the copy gets one, with the date that Photos shows.
    """
    taken = datetime.fromisoformat(record["date"])
    value = f"{taken:%Y:%m:%d %H:%M:%S}{taken.isoformat()[-6:]}"
    run([
        *(tool("exiftool"), "-quiet", "-overwrite_original"),
        *("-api", "LargeFileSupport=1"),
        f"-Keys:CreationDate={value}",
        str(dst),
    ])
    written = run([tool("exiftool"), "-s3", "-Keys:CreationDate", str(dst)]).stdout
    if written.strip() != value:
        raise RuntimeError(
            f"Keys:CreationDate reads {written.strip()!r}, not {value!r}"
        )


def probe_json(args: list[str]) -> dict:
    """Run `ffprobe` with JSON output and return what it printed."""
    command = [tool("ffprobe"), "-hide_banner", "-loglevel", "error", "-of", "json"]
    info: dict = json.loads(run([*command, *args]).stdout)
    return info


def frame_times(path: Path) -> tuple[Fraction, list[int], int]:
    """Return the time base, the sorted frame times and the last frame duration.

    The times are those of the first video stream, in its time base.
    """
    info = probe_json([
        *("-select_streams", "v:0"),
        *("-show_entries", "stream=time_base:packet=pts,duration"),
        str(path),
    ])
    rows = sorted((int(p["pts"]), int(p.get("duration", 0))) for p in info["packets"])
    time_base = Fraction(info["streams"][0]["time_base"])
    return time_base, [pts for pts, _ in rows], rows[-1][1]


def kept_frames(path: Path, trim: dict) -> tuple[Fraction, int, int]:
    """Return the time base, the time of the first kept frame and the end time.

    The kept frames run from the frame on screen at the trim start to the last
    frame that starts before the trim end. Photos trims inside a frame, and at an
    edit that starts inside a frame, AVFoundation shows that frame while `ffmpeg`
    drops it. A cut on frame boundaries shows the same frames in both.

    A trim that runs to the end of the movie keeps its last frame for as long as
    the original shows it. An iPhone edit list can show that frame for one time
    unit less than its sample lasts, and AVFoundation ends the cut there.
    """
    time_base, pts, last = frame_times(path)
    start, end = Fraction(trim["start"]), Fraction(trim["end"])
    first = max((p for p in pts if p * time_base <= start), default=pts[0])
    after = [p for p in pts if p * time_base >= end]
    if after:
        return time_base, first, after[0]
    return time_base, first, min(pts[-1] + last, shown_end(path) // time_base)


def mp4_boxes(data: bytes, start: int, end: int):
    """Yield the type, the payload start and the end of each box in a byte range."""
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            return
        yield kind, pos + header, pos + size
        pos += size


def find_box(
    data: bytes, start: int, end: int, path: list[bytes]
) -> tuple[int, int] | None:
    """Return the payload range of the first box along a path of box types."""
    for kind, body, stop in mp4_boxes(data, start, end):
        if kind == path[0]:
            if len(path) == 1:
                return body, stop
            return find_box(data, body, stop, path[1:])
    return None


def required_box(data: bytes, start: int, end: int, path: list[bytes]) -> int:
    """Return the payload start of a box that every movie file holds, or raise."""
    found = find_box(data, start, end, path)
    if found is None:
        raise RuntimeError(f"the movie has no {b'/'.join(path).decode()} box")
    return found[0]


def read_moov(path: Path) -> tuple[int, bytes]:
    """Return the file offset and the bytes of the `moov` box, reading box headers."""
    with path.open("rb") as handle:
        end = handle.seek(0, os.SEEK_END)
        pos = 0
        while pos + 8 <= end:
            handle.seek(pos)
            size, kind = struct.unpack(">I4s", handle.read(8))
            if size == 1:
                size = struct.unpack(">Q", handle.read(8))[0]
            elif size == 0:
                size = end - pos
            if kind == b"moov":
                handle.seek(pos)
                return pos, handle.read(size)
            pos += size
    raise RuntimeError(f"{path.name} has no moov box")


def tracks(path: Path) -> list[dict]:
    """Return what the cut check compares in each track of a movie file.

    Each track gives its handler, its `tkhd` duration, volume and matrix, its edit
    list, and the child boxes of its sample description, by type. The offsets let
    `fit_tracks` rewrite the durations and the volume in place.
    """
    _, raw = read_moov(path)
    mvhd = required_box(raw, 8, len(raw), [b"mvhd"])
    movie_version = raw[mvhd]
    scale = struct.unpack_from(">I", raw, mvhd + (20 if movie_version else 12))[0]
    found = []
    for kind, start, stop in mp4_boxes(raw, 8, len(raw)):
        if kind != b"trak":
            continue
        hdlr = required_box(raw, start, stop, [b"mdia", b"hdlr"])
        tkhd = required_box(raw, start, stop, [b"tkhd"])
        version = raw[tkhd]
        # After the duration: 8 reserved bytes, the layer, the alternate group, the
        # volume, 2 reserved bytes, then the 36 bytes of the matrix.
        duration_at = tkhd + (28 if version else 20)
        volume_at = duration_at + (8 if version else 4) + 12
        track: dict = {
            "handler": raw[hdlr + 8 : hdlr + 12].decode("latin-1"),
            "duration": (duration_at, ">Q" if version else ">I"),
            "volume": raw[volume_at : volume_at + 2],
            "volume_at": volume_at,
            "matrix": raw[volume_at + 4 : volume_at + 40],
            "edits": [],
            "entry": {},
        }
        elst = find_box(raw, start, stop, [b"edts", b"elst"])
        if elst:
            version = raw[elst[0]]
            fmt = ">Qq" if version else ">Ii"
            for index in range(struct.unpack_from(">I", raw, elst[0] + 4)[0]):
                at = elst[0] + 8 + index * (20 if version else 12)
                segment, media = struct.unpack_from(fmt, raw, at)
                track["edits"].append((at, ">Q" if version else ">I", segment, media))
        stsd = find_box(raw, start, stop, [b"mdia", b"minf", b"stbl", b"stsd"])
        entry = next(mp4_boxes(raw, stsd[0] + 8, stsd[1]), None) if stsd else None
        if entry is not None:
            # A visual sample entry has 78 bytes of fields before its child boxes. A
            # sound entry has 28, and 16 or 36 more in QuickTime versions 1 and 2.
            skip = {"vide": 78}.get(track["handler"])
            if track["handler"] == "soun":
                sound_version = struct.unpack_from(">H", raw, entry[1] + 8)[0]
                skip = 28 + {1: 16, 2: 36}.get(sound_version, 0)
            if skip is not None:
                for child, body, end in mp4_boxes(raw, entry[1] + skip, entry[2]):
                    track["entry"][child.decode("latin-1")] = raw[body:end]
        found.append(track)
    return [{"timescale": scale, "mvhd": (mvhd, movie_version)}, *found]


def shown_end(path: Path) -> Fraction:
    """Return the time in seconds at which the first video track stops showing.

    That is the end of its edit list, or of its `tkhd` duration without one.
    """
    movie, *found = tracks(path)
    video = next(track for track in found if track["handler"] == "vide")
    if video["edits"]:
        units = sum(segment for _, _, segment, _ in video["edits"])
    else:
        _, raw = read_moov(path)
        at, fmt = video["duration"]
        units = struct.unpack_from(fmt, raw, at)[0]
    return Fraction(units, movie["timescale"])


def fit_tracks(path: Path, seconds: Fraction, source: Path) -> None:
    """End every track of a cut at `seconds`, and give it the volume of the source.

    `ffmpeg` ends a stream copy at the first packet whose decoding time reaches the
    end. With B-frames, that keeps frames that it decodes before the end and shows
    after it, and its edit list then shows them. It also writes a volume of 1 for
    every audio track, where a GoPro writes 0.39. Each track takes the volume of
    the first source track with the same handler.
    """
    base, _ = read_moov(path)
    movie, *found = tracks(path)
    units = seconds * movie["timescale"]
    if units.denominator != 1:
        raise RuntimeError(f"{seconds} s is no whole number of movie time units")
    volumes = [(track["handler"], track["volume"]) for track in tracks(source)[1:]]
    writes = []
    longest = 0
    for track in found:
        total = 0
        for at, fmt, segment, media in track["edits"]:
            if media >= 0:
                kept = min(segment, int(units) - total)
                if kept <= 0:
                    raise RuntimeError("an edit starts after the end of the cut")
                writes.append((at, fmt, kept))
                segment = kept
            total += segment
        writes.append((*track["duration"], total))
        longest = max(longest, total)
        match = next((item for item in volumes if item[0] == track["handler"]), None)
        if match is not None:
            volumes.remove(match)
            writes.append((track["volume_at"], ">H", struct.unpack(">H", match[1])[0]))
    mvhd, version = movie["mvhd"]
    writes.append((mvhd + (24 if version else 16), ">Q" if version else ">I", longest))
    with path.open("r+b") as handle:
        for offset, fmt, value in writes:
            handle.seek(base + offset)
            handle.write(struct.pack(fmt, value))


def cut_video(src: Path, dst: Path, record: dict) -> float:
    """Cut a video to its trim with no re-encoding, and return the seconds.

    The video and its GoPro telemetry come from the source from the key frame at
    or before the first kept frame. The audio comes from a second reading of the
    same file that starts up to `AUDIO_PREROLL` seconds earlier, shifted back by as
    much. A mute leaves the audio out. `ffmpeg` writes to a partial file first, and
    `fit_tracks` ends every track at the last kept frame. The cut takes the
    metadata of the original, except the keys of `TEXT_KEYS`.
    """
    time_base, first, stop = kept_frames(src, record["trim"])
    start, duration = first * time_base, (stop - first) * time_base
    entries = "stream=index,codec_type,codec_tag_string"
    streams = probe_json(["-show_entries", entries, str(src)])
    video = next(s for s in streams["streams"] if s["codec_type"] == "video")
    maps = ["-map", f"0:{video['index']}"]
    for stream in streams["streams"]:
        if stream["codec_type"] == "audio" and not record["trim"]["mute"]:
            maps += ["-map", f"1:{stream['index']}"]
        elif (
            stream["codec_type"] == "data"
            and stream["codec_tag_string"] in CUT_DATA_TAGS
        ):
            maps += ["-map", f"0:{stream['index']}"]
    preroll = min(AUDIO_PREROLL, start)
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(f".partial-{dst.name}")
    began = time.monotonic()
    run([
        *(tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-y"),
        # ffmpeg reads microseconds, and rounds them to each stream's time base.
        *("-ss", f"{float(start):.6f}", "-i", str(src)),
        *("-ss", f"{float(start - preroll):.6f}"),
        *("-itsoffset", f"{-float(preroll):.6f}", "-i", str(src)),
        *maps,
        *("-c", "copy", "-t", f"{float(duration):.6f}"),
        *("-write_tmcd", "0", "-map_metadata", "0"),
        *(arg for key in TEXT_KEYS for arg in ("-metadata", f"{key}=")),
        str(partial),
    ])
    fit_tracks(partial, duration, src)
    partial.replace(dst)
    record["cut"] = {"first": first, "stop": stop, "time_base": str(time_base)}
    return time.monotonic() - began


def needs_passthrough(path: Path) -> bool:
    """Tell whether a source holds what `ffmpeg` cannot write into a cut.

    `ffmpeg` 9.0.2 writes a Dolby Vision box only into an MP4 file, and only with
    `-strict unofficial`, and it writes no `mebx` track: an iPhone video has both.
    """
    entries = probe_json(["-show_entries", "stream=codec_tag_string", str(path)])
    if any(s.get("codec_tag_string") in PASSTHROUGH_TAGS for s in entries["streams"]):
        return True
    return any(set(t["entry"]) & set(PASSTHROUGH_BOXES) for t in tracks(path)[1:])


def passthrough_cut(src: Path, dst: Path, record: dict, work: Path) -> float:
    """Cut a video to its trim with AVFoundation, and return the seconds.

    The passthrough export copies each packet as it is, and keeps every track and
    format box. It starts and ends the cut on the frames that `kept_frames` gives,
    and it leaves out the packets before the first kept frame that no kept frame
    needs. It runs through `osxphotos run`, whose Python has PyObjC.
    """
    time_base, first, stop = kept_frames(src, record["trim"])
    if time_base.numerator != 1:
        raise RuntimeError(f"the time base {time_base} is no fraction 1/n of a second")
    helper = work / ".passthrough_cut.py"
    helper.write_text(PASSTHROUGH_CUT, encoding="UTF-8")
    dst.parent.mkdir(parents=True, exist_ok=True)
    partial = dst.with_name(f".partial-{dst.name}")
    began = time.monotonic()
    run([
        *(tool("osxphotos"), "run", str(helper), str(src), str(partial)),
        *(str(first), str(stop), str(time_base.denominator)),
    ])
    partial.replace(dst)
    record["cut"] = {"first": first, "stop": stop, "time_base": str(time_base)}
    return time.monotonic() - began


def in_order(part: list[str], whole: list[str]) -> bool:
    """Tell whether every item of `part` is in `whole`, in the same order."""
    remaining = iter(whole)
    return all(item in remaining for item in part)


def packet_hashes(
    path: Path, index: int, window: tuple[float, float] | None = None
) -> list[str]:
    """Return the SHA-256 of each packet of one stream, in decoding order.

    A window from time 0 reads from the file start, to include the packets that
    the edit list of the file hides before time 0.
    """
    args = ["-select_streams", str(index), "-show_entries", "packet=data_hash"]
    args += ["-show_data_hash", "SHA256"]
    if window:
        begin = f"{window[0]:.6f}" if window[0] > 0 else ""
        args += ["-read_intervals", f"{begin}%{window[1]:.6f}"]
    return [packet["data_hash"] for packet in probe_json([*args, str(path)])["packets"]]


def frame_hashes(
    path: Path, window: tuple[float, float] | None = None
) -> list[tuple[int, str]]:
    """Decode the first video stream and return the time and SHA-256 of each frame.

    A window decodes that range only, and keeps the timestamps of the file. The
    frames stay as stored, with no rotation.
    """
    args = [tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error"]
    if window:
        begin = max(window[0], 0)
        args += ["-copyts", "-ss", f"{begin:.6f}", "-t", f"{window[1] - begin:.6f}"]
    args += ["-noautorotate", "-i", str(path), "-map", "0:v:0"]
    args += ["-fps_mode", "passthrough"]
    args += ["-enc_time_base:v", "demux", "-f", "framehash", "-hash", "sha256", "-"]
    rows = []
    for line in run(args).stdout.splitlines():
        if not line.startswith("#"):
            parts = [part.strip() for part in line.split(",")]
            rows.append((int(parts[2]), parts[5]))
    return rows


def audio_samples(
    path: Path,
    window: tuple[float, float] | None = None,
    span: tuple[int, int] | None = None,
) -> bytes:
    """Decode the first audio stream to 32-bit float samples.

    A window decodes that range only, and keeps the timestamps of the file. A span
    then keeps the samples between two times in units of the stream time base.
    """
    args = [tool("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error"]
    if window:
        begin = max(window[0], 0)
        args += ["-copyts", "-ss", f"{begin:.6f}", "-t", f"{window[1] - begin:.6f}"]
    args += ["-i", str(path), "-map", "0:a:0"]
    if span:
        args += ["-af", f"atrim=start_pts={span[0]}:end_pts={span[1]}"]
    done = subprocess.run([*args, "-f", "f32le", "-"], capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError(f"ffmpeg failed to decode the audio of {path.name}")
    return done.stdout


def cut_problems(src: Path, dst: Path, record: dict) -> list[str]:
    """Return each way a cut differs from the frames of the original it must keep.

    The checks, each against the original:

    - The packets of each track of the cut are packets of the original, byte for
      byte and in their order, with the same codec configuration. AVFoundation
      leaves out the packets before the first kept frame that no kept frame
      needs, and the frame check proves that the kept frames decode the same.
    - The cut drops no track, except those of `CUT_DROPS` and a muted audio track.
    - The decoded frames of the cut, after its edit list, are the kept frames.
    - The decoded audio samples of the cut are those of the kept time.
    - The movie lasts as long as the kept frames, and no track lasts longer. Each
      track has the volume and the matrix of its original, and the format boxes
      of its sample description, among them a Dolby Vision box. Only an empty box
      of `CUT_EMPTY_BOXES` can go.
    """
    cut = record["cut"]
    time_base = Fraction(cut["time_base"])
    first, stop = cut["first"], cut["stop"]
    start, end = first * time_base, stop * time_base
    window = (float(start) - CUT_WINDOW, float(end) + CUT_WINDOW)
    mute = record["trim"]["mute"]
    problems = []
    show = ["-show_streams", "-show_data_hash", "SHA256"]
    before = probe_json([*show, str(src)])["streams"]
    after = probe_json([*show, str(dst)])["streams"]
    pool = list(before)
    for stream in after:
        key = (stream["codec_type"], stream.get("codec_tag_string"))
        matches = [
            s for s in pool if (s["codec_type"], s.get("codec_tag_string")) == key
        ]
        source = matches[0] if matches else None
        if source is None:
            problems.append(f"the cut has a {key[0]} track that the original lacks")
            continue
        pool.remove(source)
        if source.get("extradata_hash") != stream.get("extradata_hash"):
            problems.append(f"the {key[0]} codec configuration differs")
        want = packet_hashes(src, source["index"], window)
        have = packet_hashes(dst, stream["index"])
        if not have or not in_order(have, want):
            problems.append(f"the {key[0]} packets are no original packets in order")
    for source in pool:
        tag = source.get("codec_tag_string")
        if tag not in CUT_DROPS and not (source["codec_type"] == "audio" and mute):
            problems.append(f"the cut drops the {source['codec_type']} track {tag}")
    want = [digest for pts, digest in frame_hashes(src, window) if first <= pts < stop]
    have = [digest for _, digest in frame_hashes(dst)]
    if want != have:
        same = sum(a == b for a, b in zip(want, have))
        problems.append(
            f"frames: {same} of {len(have)} match the {len(want)} kept frames"
        )
    audio = next((s for s in before if s["codec_type"] == "audio"), None)
    if audio is not None and not mute:
        audio_tb = Fraction(audio["time_base"])
        # A cut can start half way between two samples, as with 44.1 kHz audio and
        # an iPhone time base of 1/600 s. AVFoundation then starts on the later one.
        half = Fraction(1, 2)
        span = ((start / audio_tb + half) // 1, (end / audio_tb + half) // 1)
        want_pcm = audio_samples(src, window, span)
        have_pcm = audio_samples(dst)
        frame = 4 * int(audio["channels"])
        overlap = min(len(want_pcm), len(have_pcm))
        # ffmpeg decodes the whole last packet that the edit list cuts through.
        extra = (len(have_pcm) - len(want_pcm)) // frame
        if want_pcm[:overlap] != have_pcm[:overlap] or not 0 <= extra < int(
            audio.get("frame_size") or 1024
        ):
            problems.append(
                f"audio: {len(have_pcm) // frame} samples for {len(want_pcm) // frame},"
                " or other values"
            )
    movie, *found = tracks(dst)
    _, *originals = tracks(src)
    mvhd, version = movie["mvhd"]
    _, raw = read_moov(dst)
    fmt = ">Q" if version else ">I"
    length = struct.unpack_from(fmt, raw, mvhd + (24 if version else 16))[0]
    lasts = Fraction(length, movie["timescale"])
    if lasts != end - start:
        problems.append(f"the movie lasts {float(lasts):.6f} s")
    for track in found:
        name = HANDLER_NAMES.get(track["handler"], track["handler"])
        shown = sum(segment for _, _, segment, _ in track["edits"])
        if Fraction(shown, movie["timescale"]) > end - start:
            problems.append(f"the {name} track lasts longer than the cut")
        source = next((t for t in originals if t["handler"] == track["handler"]), None)
        if source is None:
            continue
        originals.remove(source)
        if source["volume"] != track["volume"] or source["matrix"] != track["matrix"]:
            problems.append(f"the {name} track has another volume or matrix")
        dropped = sorted(
            kind
            for kind in set(source["entry"]) - set(track["entry"])
            if CUT_EMPTY_BOXES.get(kind) != source["entry"][kind]
        )
        if dropped:
            problems.append(f"the {name} format drops {', '.join(dropped)}")
    return problems


def encode_videos(args: argparse.Namespace, only: set[str] | None = None) -> bool:
    """Encode each exported video, then accept the copy or keep the original."""
    state = load_state(args.work)
    passed = True
    for uuid, record in state.items():
        if record["status"] != "exported" or (only and uuid not in only):
            continue
        src = args.work / "export" / uuid / record["name"]
        dst = args.work / "encoded" / uuid / record["name"]
        trim = record.get("mode") == "trim"
        signature = CUT_SIGNATURE if trim else " ".join(ENCODER)
        try:
            # A copy counts only when the state proves its encode ended with the
            # current settings. In any doubt, the encode runs again.
            if dst.exists() and record.get("encoder") == signature:
                # exiftool refuses to write while a cut run left its temporary file.
                for leftover in dst.parent.glob("*_exiftool_tmp"):
                    leftover.unlink()
            else:
                for leftover in dst.parent.glob("*"):
                    leftover.unlink()
                verb = "cutting" if trim else "encoding"
                print(f"{uuid}: {verb} {record['name']}.", flush=True)
                if not trim:
                    seconds = encode(src, dst)
                elif needs_passthrough(src):
                    seconds = passthrough_cut(src, dst, record, args.work)
                else:
                    seconds = cut_video(src, dst, record)
                record["encode_seconds"] = round(seconds)
                record["encoder"] = signature
                save_state(args.work, state)
            copy_tags(src, dst)
            if "date" in record:
                stamp_date(record, dst)
            problems = cut_problems(src, dst, record) if trim else differences(src, dst)
        except PROBE_ERRORS as error:
            record["error"] = f"{type(error).__name__}: {error}"
            save_state(args.work, state)
            print(f"{uuid}: {record['error']}", file=sys.stderr)
            passed = False
            continue
        record.pop("error", None)
        record["encoded_bytes"] = dst.stat().st_size
        saving = 1 - record["encoded_bytes"] / record["source_bytes"]
        if problems:
            record.update(status="kept", reason="; ".join(problems))
            passed = False
        # A cut needs no floor: the new asset also takes the place of the render of
        # the edit, which Photos keeps next to the original.
        elif saving < args.min_saving and not trim:
            floor = f"{args.min_saving:.0%}"
            record.update(status="kept", reason=f"saves {saving:.0%}, under {floor}")
        else:
            record["status"] = "encoded"
        outcome = record.get("reason", f"saves {saving:.0%}")
        print(f"{uuid}: {record['status']}, {outcome}.", flush=True)
        save_state(args.work, state)
    return passed


def adopt_imports(state: dict[str, dict], ready: dict[str, dict]) -> None:
    """Record each copy that an earlier import added to Photos but did not report.

    A copy matches by its name and its size in bytes, anywhere in the library: a
    cut import can stop before it adds the copy to its album. This keeps a second
    import of the same copy from happening.
    """
    taken = {record.get("new_uuid") for record in state.values()}
    for uuid, record in ready.items():
        command = [tool("osxphotos"), "query", "--name", record["name"], "--json"]
        for photo in json.loads(run(command).stdout):
            if (
                photo["uuid"] not in taken
                and photo["original_filename"] == record["name"]
                and photo["original_filesize"] == record["encoded_bytes"]
            ):
                record.update(status="imported", new_uuid=photo["uuid"])
                taken.add(photo["uuid"])
                print(f"{uuid}: an earlier run imported it as {photo['uuid']}.")
                break


def import_videos(args: argparse.Namespace, only: set[str] | None = None) -> bool:
    """Add each accepted copy to the library as a new asset."""
    state = load_state(args.work)
    ready = {
        uuid: record
        for uuid, record in state.items()
        if record["status"] == "encoded" and (not only or uuid in only)
    }
    if ready and not args.dry_run:
        try:
            adopt_imports(state, ready)
        except (RuntimeError, ValueError) as error:
            print(f"No import: the earlier imports are unknown: {error}")
            return False
        save_state(args.work, state)
        ready = {uuid: r for uuid, r in ready.items() if r["status"] == "encoded"}
    if not ready:
        return True
    report = args.work / "reports" / f"import-{time.strftime('%Y%m%dT%H%M%S')}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    command = [tool("osxphotos"), "import"]
    command += [
        str(args.work / "encoded" / uuid / r["name"]) for uuid, r in ready.items()
    ]
    command += ["--exportdb", str(args.work / "export" / EXPORT_DB)]
    command += ["--exportdir", str(args.work / "encoded")]
    command += ["--album", literal(ALBUM_NEW), "--report", str(report), "--verbose"]
    if args.dry_run:
        return drive([*command, "--dry-run"], args.work)
    passed = drive_photos(command, args.work)
    rows = json.loads(report.read_text(encoding="UTF-8")) if report.exists() else []
    for row in rows:
        uuid = Path(row["filepath"]).parent.name
        if uuid in ready and row["imported"] and row["uuid"] and not row["error"]:
            state[uuid].update(status="imported", new_uuid=row["uuid"])
            print(f"{uuid}: imported as {row['uuid']}.")
    for uuid in ready:
        if state[uuid]["status"] != "imported":
            print(f"{uuid}: the report records no import.", file=sys.stderr)
            passed = False
    save_state(args.work, state)
    clean_work_files(args.work)
    return passed


def normal(value: object) -> object:
    """Return a field value in a form that compares equal across two assets."""
    if isinstance(value, list):
        return sorted(value)
    return None if value == "" else value


def comparison(record: dict, old: dict | None, new: dict | None) -> list[tuple]:
    """Return one row per compared field: its name, both values and a verdict.

    `old` is None once Recently Deleted no longer holds the original. The rows
    then only describe the new asset.
    """
    if new is None:
        return [("asset", "present" if old else "absent", "absent", DIFFERENT)]
    rows: list[tuple] = []
    if old is not None:
        for field in SAME_FIELDS:
            same = normal(old[field]) == normal(new[field])
            rows.append((field, old[field], new[field], SAME if same else DIFFERENT))
        dates = [datetime.fromisoformat(photo["date"]) for photo in (old, new)]
        same = dates[0] == dates[1]
        rows.append(("date", old["date"], new["date"], SAME if same else DIFFERENT))
        offsets = [photo["tzoffset"] for photo in (old, new)]
        # Photos can store an offset for the original that disagrees with the date
        # it shows, like 7200 for a date at `+01:00`. The new asset then takes the
        # offset of that date, and keeps the same moment and the same wall time.
        shown = dates[1].utcoffset()
        fixed = (
            same
            and shown is not None
            and dates[0].utcoffset() == shown
            and offsets[1] == shown.total_seconds()
        )
        verdict = SAME if offsets[0] == offsets[1] else INFO if fixed else DIFFERENT
        rows.append(("tzoffset", *offsets, verdict))
        places = [(photo["latitude"], photo["longitude"]) for photo in (old, new)]
        same = places[0] == places[1] or (
            None not in (*places[0], *places[1])
            and all(abs(a - b) <= LOCATION_TOLERANCE for a, b in zip(*places))
        )
        # The camera wrote a position that Photos never read for the original, and
        # Photos reads it from the copy: the new asset keeps more, not less.
        gained = places[0] == (None, None) and None not in places[1]
        verdict = SAME if same else INFO if gained else DIFFERENT
        rows.append(("location", *places, verdict))
        albums = [
            {a["uuid"]: a["title"] for a in photo["album_info"]} for photo in (old, new)
        ]
        wanted = {u for u, title in albums[0].items() if title != ALBUM_ORIGINALS}
        same = wanted <= set(albums[1])
        titles = [sorted(album.values()) for album in albums]
        rows.append(("albums", *titles, SAME if same else DIFFERENT))
        # Photos detects faces on the new asset on its own schedule.
        persons = [len(photo["persons"]) for photo in (old, new)]
        rows.append(("persons", *persons, INFO))
    codecs = [
        (photo["exif_info"] or {}).get("codec") if photo else None
        for photo in (old, new)
    ]
    # A cut keeps the codec of its original.
    expected = record["codec"] if record.get("mode") == "trim" else "hvc1"
    verdict = (
        OK if codecs[1] == expected else PENDING if codecs[1] is None else DIFFERENT
    )
    rows.append(("codec", *codecs, verdict))
    sizes = [photo["original_filesize"] if photo else None for photo in (old, new)]
    rows.append((
        "bytes",
        *sizes,
        OK if sizes[1] == record["encoded_bytes"] else DIFFERENT,
    ))
    clouds = [photo["incloud"] if photo else None for photo in (old, new)]
    rows.append(("in iCloud", *clouds, OK if clouds[1] else PENDING))
    trashed = [photo["intrash"] if photo else None for photo in (old, new)]
    rows.append(("in Recently Deleted", *trashed, DIFFERENT if trashed[1] else OK))
    return rows


def check_videos(args: argparse.Namespace, tables: bool = True) -> bool:
    """Compare each original with its new asset in the Photos database."""
    state = load_state(args.work)
    pairs = {
        uuid: record
        for uuid, record in state.items()
        if "new_uuid" in record and (tables or record["status"] == "imported")
    }
    library = photos([*pairs, *(record["new_uuid"] for record in pairs.values())])
    passed = True
    for uuid, record in pairs.items():
        new_uuid = record["new_uuid"]
        rows = comparison(record, library.get(uuid), library.get(new_uuid))
        if tables:
            print(f"\n{record['name']}\n  original  {uuid}\n  new asset {new_uuid}")
            table = [("field", "original", "new asset", "verdict"), *rows]
            widths = [max(len(str(row[i])) for row in table) for i in range(3)]
            for row in table:
                cells = "  ".join(str(row[i]).ljust(widths[i]) for i in range(3))
                print(f"  {cells}  {row[3]}")
        differ = [row[0] for row in rows if row[3] == DIFFERENT]
        waiting = [row[0] for row in rows if row[3] == PENDING]
        record["check"] = "differs" if differ else "pending" if waiting else "ok"
        record["differs"] = differ
        if differ:
            passed = False
            result = f"the new asset differs: {', '.join(differ)}"
        elif waiting:
            result = f"Photos has not finished: {', '.join(waiting)}. Check again"
        else:
            if record["status"] == "imported":
                record["status"] = "verified"
            result = f"verified, step {record['status']!r}"
        print(f"  Result: {result}." if tables else f"{uuid}: {result}.")
    save_state(args.work, state)
    return passed


def literal(text: str) -> str:
    """Return the osxphotos template that prints `text` as it is.

    `osxphotos` reads each album, title, description and keyword option as a
    template. Its parser refuses a comma or a question mark outside a field, and
    reads a brace as the start or the end of a field.
    """
    return "".join(TEMPLATE_ESCAPES.get(char, char) for char in text)


def album_path(album: dict) -> str | None:
    """Return an album as `--split-folder` reads it: its folders, then its title.

    :return: None when a name holds a slash, which would split in the wrong place.
    """
    names = [*(album.get("folder_names") or []), album["title"]]
    return None if any("/" in name for name in names) else "/".join(names)


def complete_albums(args: argparse.Namespace) -> None:
    """Add each new asset to the albums of its original that it lacks.

    Photos can stop answering in the middle of an import, and `osxphotos` then
    quits it. The new asset exists by then, but it misses the albums that the
    import had not reached. This runs after `check` finds that gap.
    """
    state = load_state(args.work)
    todo = {
        uuid: record
        for uuid, record in state.items()
        if record["status"] == "imported"
        and record.get("differs") == ["albums"]
        and record.get("repairs", 0) < MAX_REPAIRS
    }
    if not todo:
        return
    library = photos([*todo, *(record["new_uuid"] for record in todo.values())])
    for uuid, record in todo.items():
        old, new = library.get(uuid), library.get(record["new_uuid"])
        if old is None or new is None:
            continue
        have = {album_path(album) for album in new["album_info"]}
        wanted = [
            album_path(album)
            for album in old["album_info"]
            if album["title"] != ALBUM_ORIGINALS
        ]
        missing = [path for path in wanted if path and path not in have]
        if None in wanted:
            print(f"{uuid}: a person adds the albums with a slash in a name.")
        if not missing:
            continue
        record["repairs"] = record.get("repairs", 0) + 1
        print(f"{uuid}: adding the new asset to the albums {missing}.", flush=True)
        command = [tool("osxphotos"), "batch-edit", "--uuid", record["new_uuid"]]
        for path in missing:
            command += ["--add-to-album", literal(path)]
        command += ["--split-folder", "/", "--verbose"]
        if drive_photos(command, args.work):
            record["check"] = "pending"
        save_state(args.work, state)


def mark_originals(args: argparse.Namespace) -> bool:
    """Add each original that has a verified new asset to the album to delete."""
    state = load_state(args.work)
    ready = [uuid for uuid, record in state.items() if record["status"] == "verified"]
    # A new asset can change after `check`, so compare again at the last moment.
    library = photos([*ready, *(state[uuid]["new_uuid"] for uuid in ready)])
    clean = []
    for uuid in ready:
        record = state[uuid]
        rows = comparison(record, library.get(uuid), library.get(record["new_uuid"]))
        if all(row[3] in {SAME, OK, INFO} for row in rows):
            clean.append(uuid)
        else:
            record["status"] = "imported"
            print(f"{uuid}: no longer verified. Run `check`.", file=sys.stderr)
    passed = len(clean) == len(ready)
    if clean:
        command = [tool("osxphotos"), "batch-edit"]
        for uuid in clean:
            command += ["--uuid", uuid]
        command += ["--add-to-album", literal(ALBUM_ORIGINALS), "--verbose"]
        if args.dry_run:
            command.append("--dry-run")
        marked = drive_photos(command, args.work, args.dry_run)
        passed = marked and passed
        if marked and not args.dry_run:
            for uuid in clean:
                state[uuid]["status"] = "marked"
    save_state(args.work, state)
    return passed


def clean_work_files(work: Path) -> None:
    """Remove the work files that no later step reads.

    The exported original goes once its copy is in the library: the original
    stays in the library and in iCloud until the manual delete. The copy goes
    once its video is finished.
    """
    state = load_state(work)
    freed = 0
    for uuid, record in state.items():
        if record.get("cleaned"):
            continue
        finished = record["status"] in FINISHED
        folders = [work / "export" / uuid] if finished or "new_uuid" in record else []
        if finished:
            folders.append(work / "encoded" / uuid)
        for folder in folders:
            for path in folder.glob("*"):
                freed += path.stat().st_size
                path.unlink()
            if folder.is_dir():
                folder.rmdir()
        if finished:
            record["cleaned"] = True
    if freed:
        print(f"Removed {freed / 2**30:.1f} GiB of work files.", flush=True)
    save_state(work, state)


def settle(args: argparse.Namespace, wait: int = 0) -> bool:
    """Run `check` and `mark`, then clean up, until no new asset waits or time ends.

    :param wait: Seconds to keep trying while a new asset waits for iCloud.
    """
    deadline = time.monotonic() + wait
    while True:
        print("\nChecking the imported videos.", flush=True)
        checked = check_videos(args, tables=False)
        complete_albums(args)
        passed = mark_originals(args) and checked
        clean_work_files(args.work)
        waiting = [
            record
            for record in load_state(args.work).values()
            if record["status"] == "imported" and record.get("check") == "pending"
        ]
        if not waiting or time.monotonic() > deadline:
            return passed and not waiting
        print(f"{len(waiting)} new assets wait for iCloud.", flush=True)
        time.sleep(60)


def disk_space(work: Path) -> int:
    """Return the disk space, in bytes, that a large write can count on.

    It is the space for important use when macOS gives it, and the free space
    otherwise. A sandbox, for one, hides the first and answers 0.
    """
    free = shutil.disk_usage(work).free
    try:
        answer = run([
            tool("osascript"),
            "-l",
            "JavaScript",
            "-e",
            IMPORTANT_SPACE,
            str(work),
        ])
        important = int(float(answer.stdout))
    except (RuntimeError, ValueError):
        return free
    if important <= 0:
        return free
    print(
        f"Disk: {free / 2**30:.0f} GiB free, "
        f"{important / 2**30:.0f} GiB with purgeable space.",
        flush=True,
    )
    return max(free, important)


def select_videos(args: argparse.Namespace) -> dict[str, int]:
    """Return the size in bytes of each selected video, by UUID, in batch order.

    The batch takes the smallest videos first, so a fault shows on a cheap one. It
    leaves out a video in `ALBUM_ORIGINALS`, which waits for its delete.
    """
    if args.uuid:
        return {uuid.upper(): 0 for uuid in args.uuid}
    selection = TRIM_SELECTION if args.trim else SELECTION
    command = [tool("osxphotos"), "query", *selection]
    command += ["--min-size", args.min_size, "--json"]
    found = json.loads(run(command).stdout)
    if args.trim:
        found = [photo for photo in found if trim_edit(photo) is not None]
    state = load_state(args.work)
    found = [
        photo
        for photo in found
        if state.get(photo["uuid"], {}).get("status") not in FINISHED
        and state.get(photo["uuid"], {}).get("attempts", 0) < MAX_ATTEMPTS
        and ALBUM_ORIGINALS not in {album["title"] for album in photo["album_info"]}
    ]
    found.sort(key=lambda photo: photo["original_filesize"])
    if args.limit:
        found = found[: args.limit]
    return {photo["uuid"]: photo["original_filesize"] for photo in found}


def run_videos(args: argparse.Namespace) -> bool:
    """Take each selected video through the whole round trip, one at a time."""
    selected = select_videos(args)
    if args.list:
        for uuid, size in selected.items():
            print(f"{uuid}  {size / 2**20:8.0f} MiB")
        print(f"{len(selected)} videos, {sum(selected.values()) / 2**30:.0f} GiB.")
        return True
    args.work.mkdir(parents=True, exist_ok=True)
    keep_awake()
    passed = True
    failures = 0
    last_check = time.monotonic()
    for index, (uuid, size) in enumerate(selected.items(), 1):
        record = load_state(args.work).get(uuid, {})
        if args.uuid and record.get("status") == "kept":
            # A video named on the command line runs again, even when an earlier
            # run kept its original.
            state = load_state(args.work)
            del state[uuid]
            save_state(args.work, state)
            record = {}
        if record.get("status") in FINISHED:
            continue
        size = record.get("source_bytes", size)
        free = disk_space(args.work)
        if free < args.min_free + 3 * size:
            print(f"Stopped: {free / 2**30:.0f} GiB of disk space.", file=sys.stderr)
            passed = False
            break
        print(f"\n[{index}/{len(selected)}] {uuid}", flush=True)
        done = (
            export_videos(args, [uuid])
            and encode_videos(args, {uuid})
            and import_videos(args, {uuid})
        )
        passed = passed and done
        failures = 0 if done else failures + 1
        if not done:
            state = load_state(args.work)
            record = state.setdefault(uuid, {"status": "failed"})
            record["attempts"] = record.get("attempts", 0) + 1
            save_state(args.work, state)
        if failures >= FAILURE_LIMIT:
            print(f"Stopped: {failures} videos failed in a row.", file=sys.stderr)
            break
        if not args.dry_run and time.monotonic() - last_check > CHECK_INTERVAL:
            settle(args)
            last_check = time.monotonic()
    if args.dry_run:
        return passed
    return settle(args, wait=args.upload_wait) and passed


def status_report(args: argparse.Namespace) -> bool:
    """Print the totals of the work directory, and each video that needs a look."""
    state = load_state(args.work)
    marked = [record for record in state.values() if record["status"] == "marked"]
    before = sum(record["source_bytes"] for record in marked)
    after = sum(record["encoded_bytes"] for record in marked)
    seconds = sum(record.get("encode_seconds", 0) for record in state.values())
    print(f"Replaced: {len(marked)} videos, {before / 2**30:.1f} GiB of originals.")
    if before:
        saved = (before - after) / 2**30
        print(f"Saved: {saved:.1f} GiB, {1 - after / before:.0%} of those originals.")
    print(f"Encoding time: {seconds / 3600:.1f} hours.")
    for uuid, record in state.items():
        label = f"{uuid} {record.get('name', '')}".strip()
        if record["status"] == "kept":
            print(f"Kept: {label}: {record['reason']}.")
        if record.get("check") == "differs" and record["status"] == "imported":
            print(f"Differs: {label}: {', '.join(record['differs'])}.")
        if record.get("attempts", 0) >= MAX_ATTEMPTS:
            print(f"Skipped after {record['attempts']} failed runs: {label}.")
        if "error" in record:
            print(f"Error: {label}: {record['error']}")
    return True


def duplicate_sets() -> list[list[dict]]:
    """Return the Photos records of the assets in each set of duplicates.

    The assets of a set hold the same original file: Photos gives them the same
    fingerprint, and their originals have the same size. A set leaves out the
    assets in Recently Deleted and in `ALBUM_ORIGINALS`. A short listing of the
    whole library finds the sets, so that only their assets are read in full.
    """
    keys: dict[tuple[str, str], list[str]] = {}
    listing = run([tool("osxphotos"), "query", *DUPLICATE_SCAN]).stdout
    for line in listing.splitlines():
        fields = line.split()
        # osxphotos prints an underscore for a field that has no value.
        if len(fields) == 3 and "_" not in fields[1:]:
            keys.setdefault((fields[1], fields[2]), []).append(fields[0])
    shared = [uuid for uuids in keys.values() if len(uuids) > 1 for uuid in uuids]
    found: dict[tuple[str, int], list[dict]] = {}
    for photo in photos(shared).values():
        titles = {album["title"] for album in photo["album_info"]}
        if not photo["intrash"] and ALBUM_ORIGINALS not in titles:
            key = (photo["fingerprint"], photo["original_filesize"])
            found.setdefault(key, []).append(photo)
    return [members for members in found.values() if len(members) > 1]


def keep_order(photo: dict) -> tuple:
    """Return the sort key that puts first the asset that a set of duplicates keeps.

    That is the edited asset, then the favorite, then the asset in more albums,
    then the asset added first.
    """
    added = photo["date_added"]
    return (
        not photo["hasadjustments"],
        not photo["favorite"],
        -len(photo["album_info"]),
        datetime.fromisoformat(added).timestamp() if added else float("inf"),
        photo["uuid"],
    )


def merge_plan(
    members: list[dict],
) -> tuple[dict, list[dict], list[list[str]], list[str]]:
    """Plan how a set of duplicates becomes one asset.

    The kept asset gains each album, keyword and favorite flag of the other copies,
    and the title, description and location that only a copy holds. What no option
    of `osxphotos batch-edit` can merge goes to a person: edits on two copies, a
    named person on a copy only, a flag of `DUPLICATE_FLAGS`, two values of one
    field, or a date that only a copy shows. A copy can show the date of the kept
    asset, or the date that its file gives: any other date is one that a person or
    an app set on that copy.

    :return: The asset to keep, the other copies, the `batch-edit` options with
        their values that give the kept asset what it lacks, and each difference
        that stops the merge.
    """
    kept, *copies = sorted(members, key=keep_order)
    changes: list[list[str]] = []
    problems = []
    if any(copy["hasadjustments"] for copy in copies):
        problems.append("more than one copy has edits")
    for flag, words in DUPLICATE_FLAGS.items():
        if len({photo[flag] for photo in members}) > 1:
            problems.append(f"only some copies have {words}")
    dates = {copy["date"] for copy in copies}
    for date in sorted(dates - {kept["date"], kept["date_original"]}):
        problems.append(f"only a copy shows the date {date}")
    named = {name for copy in copies for name in copy["persons"]}
    lost = named - set(kept["persons"]) - {UNNAMED_PERSON}
    if lost:
        problems.append(f"only a copy shows {', '.join(sorted(lost))}")
    for field in ("title", "description"):
        values = {photo[field] for photo in members if photo[field]}
        if len(values) > 1:
            problems.append(f"the copies have different {field}s")
        elif values and not kept[field]:
            changes.append([f"--{field}", *values])
    places = [
        (photo["latitude"], photo["longitude"])
        for photo in members
        if photo["latitude"] is not None
    ]
    if any(
        abs(a - b) > LOCATION_TOLERANCE
        for place in places
        for a, b in zip(place, places[0])
    ):
        problems.append("the copies have different locations")
    elif places and kept["latitude"] is None:
        changes.append(["--location", *(str(value) for value in places[0])])
    if not kept["favorite"] and any(copy["favorite"] for copy in copies):
        changes.append(["--set-favorite"])
    keywords = {word for copy in copies for word in copy["keywords"]}
    keywords -= set(kept["keywords"])
    changes += [["--keyword", word] for word in sorted(keywords)]
    have = {album["uuid"] for album in kept["album_info"]}
    gained = {
        album["uuid"]: album_path(album)
        for copy in copies
        for album in copy["album_info"]
        if album["uuid"] not in have
    }
    paths = sorted({path for path in gained.values() if path is not None})
    if None in gained.values():
        problems.append("an album name holds a slash")
    changes += [["--add-to-album", path] for path in paths]
    return kept, copies, changes, problems


def dedup_assets(args: argparse.Namespace) -> bool:
    """Merge each set of identical assets into one, and mark the other copies."""
    plans = [merge_plan(members) for members in duplicate_sets()]
    # The sets that free the most space come first.
    plans.sort(key=lambda plan: -plan[0]["original_filesize"] * len(plan[1]))
    passed = True
    for kept, copies, changes, problems in plans:
        size = f"{kept['original_filesize'] / 2**20:.1f} MiB"
        print(f"\n{kept['original_filename']}: {len(copies) + 1} assets of {size}")
        print(f"  keeps {kept['uuid']}")
        for copy in copies:
            print(f"  copy  {copy['uuid']}")
        if problems:
            print(f"  Review: {'; '.join(problems)}.")
            passed = False
            continue
        for change in changes:
            print(f"  adds  {shlex.join(change)}")
    merges = [plan for plan in plans if not plan[3]]
    count = sum(len(copies) for _, copies, _, _ in merges)
    freed = sum(plan[0]["original_filesize"] * len(plan[1]) for plan in merges)
    print(
        f"\nSets: {len(merges)} to merge, {len(plans) - len(merges)} to review. "
        f"Copies to delete: {count}, {freed / 2**30:.2f} GiB."
    )
    if args.dry_run or not merges:
        return passed
    for kept, _, changes, _ in merges:
        if changes:
            command = [tool("osxphotos"), "batch-edit", "--uuid", kept["uuid"]]
            for option, *values in changes:
                command += [option, *(literal(value) for value in values)]
            command += ["--split-folder", "/", "--verbose"]
            passed = drive_photos(command, args.work) and passed
    # A copy goes only once the kept asset holds all that the copy holds.
    library = photos([
        photo["uuid"] for kept, copies, _, _ in merges for photo in (kept, *copies)
    ])
    marks = []
    for kept, copies, _, _ in merges:
        uuids = [photo["uuid"] for photo in (kept, *copies)]
        fresh = [library[uuid] for uuid in uuids if uuid in library]
        done = len(fresh) == len(uuids) and not any(p["intrash"] for p in fresh)
        if done:
            again, _, gaps, problems = merge_plan(fresh)
            done = again["uuid"] == kept["uuid"] and not gaps and not problems
        if done:
            marks += uuids[1:]
        else:
            print(f"{kept['uuid']}: not merged. Run `dedup` again.", file=sys.stderr)
            passed = False
    if marks:
        command = [tool("osxphotos"), "batch-edit"]
        for uuid in marks:
            command += ["--uuid", uuid]
        command += ["--add-to-album", literal(ALBUM_ORIGINALS), "--verbose"]
        passed = drive_photos(command, args.work) and passed
    return passed


def main() -> int:
    """Run one step, and return 1 when it failed for a video or a set of assets."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = parser.add_subparsers(dest="step", required=True)

    def step(name: str, action) -> argparse.ArgumentParser:
        sub = steps.add_parser(name, help=action.__doc__.splitlines()[0])
        sub.add_argument("--work", type=Path, required=True, help="Work directory.")
        sub.set_defaults(action=action)
        return sub

    def download_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--download-missing",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Download from iCloud an original that the library has no copy of.",
        )
        sub.add_argument(
            "--download-timeout",
            type=int,
            default=DOWNLOAD_TIMEOUT,
            help="Seconds that PhotoKit gets to download one original.",
        )

    def encode_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--min-saving",
            type=float,
            default=MIN_SAVING,
            help="Smallest share of the original size that a copy must save.",
        )

    def trim_option(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--trim",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="Cut trimmed videos to their trims, with no re-encoding.",
        )

    def dry_run_option(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "--dry-run",
            action=argparse.BooleanOptionalAction,
            default=False,
            help="Show the changes to the library, and make none.",
        )

    sub = step("run", run_videos)
    selection = sub.add_mutually_exclusive_group(required=True)
    selection.add_argument("--uuid", nargs="+", help="UUID of each original.")
    selection.add_argument(
        "--min-size", help="Smallest original to select, like '500 MiB'."
    )
    sub.add_argument("--limit", type=int, help="Largest number of videos to select.")
    sub.add_argument(
        "--list",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Print the selected videos, and do nothing else.",
    )
    sub.add_argument(
        "--min-free",
        type=int,
        default=MIN_FREE,
        help="Free disk space, in bytes, to keep on top of the next video.",
    )
    sub.add_argument(
        "--upload-wait",
        type=int,
        default=UPLOAD_WAIT,
        help="Seconds to wait at the end for the last uploads to iCloud.",
    )
    download_options(sub)
    encode_options(sub)
    trim_option(sub)
    dry_run_option(sub)
    step("status", status_report)
    sub = step("export", export_videos)
    sub.add_argument("--uuid", nargs="+", required=True, help="UUID of each original.")
    download_options(sub)
    trim_option(sub)
    encode_options(step("encode", encode_videos))
    for name, action in (("import", import_videos), ("mark", mark_originals)):
        dry_run_option(step(name, action))
    step("check", check_videos)
    dry_run_option(step("dedup", dedup_assets))

    args = parser.parse_args()
    args.work = args.work.resolve()
    if args.step != "status" and not getattr(args, "list", False):
        args.lock = lock_work(args.work)
    passed = args.action(args)
    if args.step != "dedup":
        summary(load_state(args.work))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
