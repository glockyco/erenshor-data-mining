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
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from PIL import Image, ImageDraw, ImageFont

from .wine import wine_path

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
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


def write_contact_sheet(run: PortraitRun, png_dir: Path, output: Path, columns: int = 6, cell: int = 220) -> None:
    """A sheet of every capture with its file title, entity, and review, under a header with the build and preset."""
    font = ImageFont.load_default(size=13)
    small = ImageFont.load_default(size=11)
    caption = 54
    header = 40
    rows = max(1, -(-len(run.results) // columns))
    sheet = Image.new("RGB", (columns * cell, header + rows * (cell + caption)), (236, 236, 236))
    draw = ImageDraw.Draw(sheet)
    statuses = ("accepted", "rejected", "failed")
    counts = {status: sum(result.status == status for result in run.results) for status in statuses}
    draw.text(
        (8, 12),
        f"Model captures, game build {run.game_build}, preset {run.preset}: {counts['accepted']} accepted, "
        f"{counts['rejected']} rejected, {counts['failed']} failed"
        + (f", interrupted at {run.interrupted}" if run.interrupted else ""),
        fill=(0, 0, 0),
        font=font,
    )
    colours = {"accepted": (64, 150, 80), "rejected": (190, 60, 50), "failed": (120, 120, 120)}
    for index, result in enumerate(run.results):
        x = (index % columns) * cell
        y = header + (index // columns) * (cell + caption)
        tile = Image.new("RGB", (cell, cell), WIKI_SURFACE)
        if result.png is not None:
            with Image.open(png_dir / result.png) as image:
                portrait = image.convert("RGBA")
                portrait.thumbnail((cell - 12, cell - 12))
                tile.paste(portrait, ((cell - portrait.width) // 2, (cell - portrait.height) // 2), portrait)
        sheet.paste(tile, (x, y))
        status_colour = colours[result.status]
        if result.warnings and result.status == "accepted":
            status_colour = (200, 150, 30)
        draw.rectangle((x, y + cell, x + cell - 1, y + cell + 4), fill=status_colour)
        draw.text((x + 4, y + cell + 7), result.file[:34], fill=(0, 0, 0), font=font)
        draw.text((x + 4, y + cell + 24), result.stable_key[:40], fill=(70, 70, 70), font=small)
        note = "; ".join(result.reasons + result.warnings) or result.kind
        draw.text((x + 4, y + cell + 38), note[:44], fill=status_colour, font=small)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
