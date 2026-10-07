"""Portrait captures of the model image manifest, and their review.

The client sends each manifest entry to the capture mod as a
``capture_portrait`` request, one at a time, grouped by scene so that each
scene loads once. It reviews each answer, records the result, and at the end
asks the mod to take the player back to where the batch started. The review
rejects output that is clipped, empty, or of another object than the entry
names, and flags dark output for the reviewer, because some creatures are dark
in the game (design D3 of the change restore-missing-wiki-images).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from .wine import wine_path

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence
    from pathlib import Path

WS_PORT = 18586
RESPONSE_TIMEOUT_SECS = 180.0

# Mean luminance of the opaque pixels below which the reviewer checks a capture.
DARK_LUMINANCE = 0.08
# Alpha above which a pixel shows the subject, as the mod frames it.
SUBJECT_ALPHA = 32
# The surface behind character pictures on the wiki (Template:Character/styles.css),
# so that the review shows each capture as readers will see it.
WIKI_SURFACE = (49, 62, 89)

_UNSAFE_FILE_CHARACTERS = re.compile(r'[<>:"/\\|?*]')


class Connection(Protocol):
    """The part of a WebSocket connection that the client uses."""

    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


@dataclass(frozen=True, slots=True)
class PortraitRequest:
    """One manifest entry as the mod captures it."""

    file: str
    stable_key: str
    kind: str
    source: Mapping[str, Any]
    pages: tuple[str, ...]

    @property
    def scene(self) -> str | None:
        scene = self.source.get("scene")
        return str(scene) if scene else None

    @property
    def expected_names(self) -> frozenset[str]:
        """The names that the captured object may have: the prefab's, or the placed character's two names."""
        resources_path = self.source.get("resources_path")
        if resources_path:
            return frozenset({str(resources_path).rsplit("/", 1)[-1]})
        names = (self.source.get("object_name"), self.source.get("npc_name"))
        return frozenset(str(name).strip() for name in names if name)

    def message(self, output: Path, preset: str) -> dict[str, Any]:
        source = self.source
        if source.get("resources_path"):
            wire_source: dict[str, Any] = {"resourcesPath": source["resources_path"]}
        else:
            wire_source = {
                "scene": source["scene"],
                "objectName": source["object_name"],
                "npcName": source.get("npc_name"),
                "position": source.get("position"),
                "landing": source["landing"],
            }
        return {
            "type": "capture_portrait",
            "file": self.file,
            "stableKey": self.stable_key,
            "preset": preset,
            "source": wire_source,
            "outputPath": wine_path(output),
        }


@dataclass(slots=True)
class PortraitResult:
    """The review of one capture."""

    file: str
    stable_key: str
    kind: str
    status: str  # accepted, rejected, or failed
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    png: str | None = None
    sha256: str | None = None
    object_name: str | None = None
    width: int | None = None
    height: int | None = None
    mean_luminance: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "stable_key": self.stable_key,
            "kind": self.kind,
            "status": self.status,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "png": self.png,
            "sha256": self.sha256,
            "object_name": self.object_name,
            "width": self.width,
            "height": self.height,
            "mean_luminance": self.mean_luminance,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> PortraitResult:
        return cls(
            file=str(data["file"]),
            stable_key=str(data["stable_key"]),
            kind=str(data["kind"]),
            status=str(data["status"]),
            reasons=[str(reason) for reason in data["reasons"]],
            warnings=[str(warning) for warning in data["warnings"]],
            png=data["png"],
            sha256=data["sha256"],
            object_name=data["object_name"],
            width=data["width"],
            height=data["height"],
            mean_luminance=data["mean_luminance"],
        )


@dataclass(slots=True)
class PortraitRun:
    """The results of one batch. An interrupted batch names why it stopped."""

    game_build: str
    preset: str
    results: list[PortraitResult] = field(default_factory=list)
    not_captured: list[str] = field(default_factory=list)
    interrupted: str | None = None
    returned: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "game_build": self.game_build,
            "preset": self.preset,
            "interrupted": self.interrupted,
            "returned": self.returned,
            "results": [result.to_json() for result in self.results],
            "not_captured": self.not_captured,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> PortraitRun:
        return cls(
            game_build=str(data["game_build"]),
            preset=str(data["preset"]),
            results=[PortraitResult.from_json(result) for result in data["results"]],
            not_captured=[str(file) for file in data["not_captured"]],
            interrupted=data["interrupted"],
            returned=bool(data["returned"]),
        )


def portrait_requests(manifest: Mapping[str, Any], files: Sequence[str] = ()) -> list[PortraitRequest]:
    """The manifest entries to capture, prefabs first and then scene by scene."""
    entries = manifest["entries"]
    wanted = set(files)
    if wanted:
        unknown = wanted - {entry["file"] for entry in entries}
        if unknown:
            raise ValueError(f"The manifest has no entry for {', '.join(sorted(unknown))}")
    requests = [
        PortraitRequest(
            file=entry["file"],
            stable_key=entry["stable_key"],
            kind=entry["kind"],
            source=entry["source"],
            pages=tuple(entry["pages"]),
        )
        for entry in entries
        if not wanted or entry["file"] in wanted
    ]
    return sorted(requests, key=lambda request: (request.scene or "", request.file))


def local_png_name(file: str) -> str:
    """A name for the staged PNG that every file system accepts. The results map it back to the title."""
    return _UNSAFE_FILE_CHARACTERS.sub("_", file)


def recapture_run(staged: Mapping[str, Any], png_dir: Path, files: Collection[str]) -> PortraitRun:
    """The staged run without ``files``, which a recapture of them continues.

    The other files keep their captures and reviews. The earlier PNGs of
    ``files`` go, so that a failed recapture leaves no stale picture.
    """
    run = PortraitRun.from_json(staged)
    for result in run.results:
        if result.file in files and result.png is not None:
            (png_dir / result.png).unlink(missing_ok=True)
    run.results = [result for result in run.results if result.file not in files]
    run.not_captured, run.interrupted, run.returned = [], None, False
    return run


def review(request: PortraitRequest, answer: Mapping[str, Any], png: Path) -> PortraitResult:
    """Accept or reject the mod's answer to one request."""
    result = PortraitResult(file=request.file, stable_key=request.stable_key, kind=request.kind, status="failed")
    if answer.get("type") != "portrait_complete":
        result.reasons.append(str(answer.get("reason") or f"unexpected answer {answer.get('type')}"))
        return result

    result.object_name = str(answer.get("objectName", ""))
    result.width = int(answer.get("width", 0))
    result.height = int(answer.get("height", 0))
    result.mean_luminance = float(answer.get("meanLuminance", 0.0))
    if result.object_name.strip() not in request.expected_names:
        expected = " or ".join(sorted(request.expected_names))
        result.reasons.append(f"wrong model: captured {result.object_name}, expected {expected}")
    if int(answer.get("renderers", 0)) == 0:
        result.reasons.append("no renderer")
    if answer.get("clipped"):
        result.reasons.append("clipped: the subject reaches the edge of the frame")
    if not png.is_file():
        result.reasons.append("empty: the mod wrote no image")
    else:
        data = png.read_bytes()
        result.png = png.name
        result.sha256 = hashlib.sha256(data).hexdigest()
        with Image.open(png) as image:
            alpha = image.convert("RGBA").getchannel("A")
            if alpha.point(lambda value: 255 if value > SUBJECT_ALPHA else 0).getbbox() is None:
                result.reasons.append("empty: no visible pixel")
    if result.mean_luminance < DARK_LUMINANCE:
        result.warnings.append(f"dark: mean luminance {result.mean_luminance:.3f}")
    result.status = "rejected" if result.reasons else "accepted"
    return result


async def capture_portraits(
    connection: Connection,
    requests: Sequence[PortraitRequest],
    png_dir: Path,
    run: PortraitRun,
    on_result: Callable[[PortraitRun], None],
    timeout: float = RESPONSE_TIMEOUT_SECS,
) -> PortraitRun:
    """Capture each request in turn, reviewing and recording each answer.

    A lost connection or a missing answer interrupts the batch: the results so
    far stay, and the remaining files are listed as not captured. The client
    then still asks the mod to return the player when it can.
    """
    for index, request in enumerate(requests):
        png = png_dir / local_png_name(request.file)
        try:
            await connection.send(json.dumps(request.message(png, run.preset)))
            answer = await _answer(connection, {"portrait_complete", "portrait_error"}, timeout)
        except (ConnectionError, TimeoutError, OSError) as error:
            run.interrupted = f"{request.file}: {type(error).__name__}: {error}"
            run.not_captured = [pending.file for pending in requests[index:]]
            on_result(run)
            break
        run.results.append(review(request, answer, png))
        on_result(run)

    try:
        await connection.send(json.dumps({"type": "end_portraits"}))
        ended = await _answer(connection, {"portraits_ended", "portrait_error"}, timeout)
        run.returned = ended.get("type") == "portraits_ended"
    except (ConnectionError, TimeoutError, OSError):
        run.returned = False
    on_result(run)
    return run


async def _answer(connection: Connection, types: set[str], timeout: float) -> dict[str, Any]:
    """The next message of one of ``types``; progress messages of other types are skipped."""
    async with asyncio.timeout(timeout):
        while True:
            message: dict[str, Any] = json.loads(await connection.recv())
            if message.get("type") in types:
                return message


@dataclass(frozen=True, slots=True)
class WikiPicture:
    """The picture that a file title shows on the wiki now, and the account that uploaded it, unless hidden."""

    user: str | None
    data: bytes


def _review_rank(result: PortraitResult) -> tuple[int, str]:
    """Failed and rejected captures first, then accepted ones with a warning, then the rest."""
    rank = {"failed": 0, "rejected": 1}.get(result.status, 2 if result.warnings else 3)
    return rank, result.file


def _tile(picture: Image.Image, size: int) -> Image.Image:
    """A picture fitted into a square of the infobox surface, as the character infobox shows it."""
    tile = Image.new("RGB", (size, size), WIKI_SURFACE)
    fitted = picture.convert("RGBA")
    fitted.thumbnail((size - 8, size - 8), Image.Resampling.LANCZOS)
    tile.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2), fitted)
    return tile


def write_contact_sheets(
    run: PortraitRun,
    png_dir: Path,
    wiki: Callable[[str], WikiPicture | None],
    directory: Path,
    *,
    columns: int = 4,
    rows: int = 8,
    tile: int = 180,
) -> list[Path]:
    """Draw every capture beside the picture that its title shows on the wiki now.

    ``wiki`` gives the live picture of a file title, or None when the title
    shows none. Each cell holds the capture, the wiki's picture, the file
    title, the entity, the review, and the uploader. Problems come first (see
    ``_review_rank``), and each sheet's header names the build, the preset,
    the counts, and the sheet's place among the others.
    """
    font = ImageFont.load_default(size=13)
    small = ImageFont.load_default(size=11)
    header, caption, gap = 44, 68, 14
    cell_width = 2 * tile + 4 + gap
    results = sorted(run.results, key=_review_rank)
    statuses = ("accepted", "rejected", "failed")
    counts = {status: sum(result.status == status for result in results) for status in statuses}
    summary = (
        f"Model captures, game build {run.game_build}, preset {run.preset}: {counts['accepted']} accepted, "
        f"{counts['rejected']} rejected, {counts['failed']} failed"
        + (f", interrupted at {run.interrupted}" if run.interrupted else "")
    )
    colours = {"accepted": (64, 150, 80), "rejected": (190, 60, 50), "failed": (120, 120, 120)}
    per_sheet = columns * rows
    total = max(1, -(-len(results) // per_sheet))
    directory.mkdir(parents=True, exist_ok=True)
    sheets: list[Path] = []
    for number, start in enumerate(range(0, max(1, len(results)), per_sheet), start=1):
        page = results[start : start + per_sheet]
        page_rows = max(1, -(-len(page) // columns))
        sheet = Image.new("RGB", (columns * cell_width, header + page_rows * (tile + caption)), (236, 236, 236))
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 6), summary, fill=(0, 0, 0), font=font)
        draw.text(
            (8, 24),
            f"Sheet {number} of {total}. Left: the capture. Right: the picture that its title shows on the wiki now.",
            fill=(70, 70, 70),
            font=small,
        )
        for index, result in enumerate(page):
            x = (index % columns) * cell_width
            y = header + (index // columns) * (tile + caption)
            if result.png is not None:
                with Image.open(png_dir / result.png) as image:
                    sheet.paste(_tile(image, tile), (x, y))
            else:
                sheet.paste(Image.new("RGB", (tile, tile), WIKI_SURFACE), (x, y))
            shown = wiki(result.file)
            wiki_x = x + tile + 4
            if shown is None:
                sheet.paste(Image.new("RGB", (tile, tile), (200, 200, 200)), (wiki_x, y))
                draw.text((wiki_x + 8, y + tile // 2 - 6), "no picture on the wiki", fill=(90, 90, 90), font=small)
            else:
                try:
                    with Image.open(io.BytesIO(shown.data)) as image:
                        sheet.paste(_tile(image, tile), (wiki_x, y))
                except (UnidentifiedImageError, OSError):
                    sheet.paste(Image.new("RGB", (tile, tile), (200, 200, 200)), (wiki_x, y))
                    draw.text((wiki_x + 8, y + tile // 2 - 6), "unreadable picture", fill=(190, 60, 50), font=small)
            status_colour = colours[result.status]
            if result.warnings and result.status == "accepted":
                status_colour = (200, 150, 30)
            draw.rectangle((x, y + tile, x + 2 * tile + 3, y + tile + 4), fill=status_colour)
            draw.text((x + 4, y + tile + 7), result.file[:52], fill=(0, 0, 0), font=font)
            draw.text((x + 4, y + tile + 24), result.stable_key[:62], fill=(70, 70, 70), font=small)
            note = "; ".join(result.reasons + result.warnings) or result.kind
            draw.text((x + 4, y + tile + 38), note[:66], fill=status_colour, font=small)
            uploader = f"wiki: {shown.user or 'uploader hidden'}" if shown is not None else "wiki: no picture"
            draw.text((x + 4, y + tile + 52), uploader, fill=(70, 70, 70), font=small)
        path = directory / f"sheet-{number:03d}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets
