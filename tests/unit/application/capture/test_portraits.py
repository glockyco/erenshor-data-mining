from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from erenshor.application.capture.portraits import (
    PortraitResult,
    PortraitRun,
    capture_portraits,
    portrait_requests,
    recapture_run,
    write_contact_sheets,
)
from erenshor.application.capture.wine import from_wine_path

Answer = Callable[[dict[str, Any]], dict[str, Any]] | Exception


class FakeMod:
    """Answers each request in turn; a complete answer writes the PNG where the request asked."""

    def __init__(self, answers: list[Answer]) -> None:
        self.answers = answers
        self.sent: list[dict[str, Any]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer(self.sent[-1]))


def completed(object_name: str, *, renderers: int = 3, clipped: bool = False, luminance: float = 0.4) -> Answer:
    def answer(request: dict[str, Any]) -> dict[str, Any]:
        Image.new("RGBA", (40, 80), (180, 120, 90, 255)).save(from_wine_path(request["outputPath"]))
        return {
            "type": "portrait_complete",
            "file": request["file"],
            "stableKey": request["stableKey"],
            "objectName": object_name,
            "width": 40,
            "height": 80,
            "renderers": renderers,
            "clipped": clipped,
            "meanLuminance": luminance,
        }

    return answer


def ended(_request: dict[str, Any]) -> dict[str, Any]:
    return {"type": "portraits_ended", "returned": True, "scene": "Stowaway"}


MANIFEST = {
    "game_build": "24405256",
    "camera_preset": "portrait-1",
    "entries": [
        {
            "file": "Faith.png",
            "kind": "character",
            "stable_key": "character:faith",
            "source": {
                "resources_path": None,
                "scene": "PlaneOfSoluna",
                "object_name": "Faith",
                "npc_name": "Faith",
                "position": None,
                "landing": [361.9, 327.1, 1346.7],
            },
            "pages": ["Faith"],
        },
        {
            "file": "Ceremonial Brazier.png",
            "kind": "character",
            "stable_key": "character:sm_prop_brazier_01 (1):duskenlight:485.82:65.42:397.38",
            "source": {
                "resources_path": None,
                "scene": "Duskenlight",
                "object_name": "SM_Prop_Brazier_01 (1)",
                "npc_name": "Ceremonial Brazier",
                "position": [485.82, 65.42, 397.38],
                "landing": [485.82, 65.42, 397.38],
            },
            "pages": ["Ceremonial Brazier"],
        },
        {
            "file": "Summoned: Treant.png",
            "kind": "summon",
            "stable_key": "character:summoned treant",
            "source": {"resources_path": "npcs/Summoned Treant", "scene": None},
            "pages": ["Summoned: Treant"],
        },
    ],
}


def _run(mod: FakeMod, tmp_path: Path, files: tuple[str, ...] = ()) -> tuple[PortraitRun, list[PortraitRun]]:
    progress: list[PortraitRun] = []
    run = PortraitRun(game_build="24405256", preset="portrait-1")
    asyncio.run(capture_portraits(mod, portrait_requests(MANIFEST, files), tmp_path, run, progress.append))
    return run, progress


def test_requests_load_prefabs_first_and_then_each_scene_once() -> None:
    requests = portrait_requests(MANIFEST)

    assert [request.file for request in requests] == ["Summoned: Treant.png", "Ceremonial Brazier.png", "Faith.png"]
    # A placed character answers to its object name until it starts and to its NPC name after.
    assert requests[1].expected_names == {"SM_Prop_Brazier_01 (1)", "Ceremonial Brazier"}
    assert requests[0].expected_names == {"Summoned Treant"}


def test_a_scene_request_lands_the_player_and_names_both_names(tmp_path: Path) -> None:
    mod = FakeMod([completed("Ceremonial Brazier"), ended])

    run, _ = _run(mod, tmp_path, ("Ceremonial Brazier.png",))

    assert mod.sent[0]["source"] == {
        "scene": "Duskenlight",
        "objectName": "SM_Prop_Brazier_01 (1)",
        "npcName": "Ceremonial Brazier",
        "position": [485.82, 65.42, 397.38],
        "landing": [485.82, 65.42, 397.38],
    }
    assert mod.sent[-1] == {"type": "end_portraits"}
    assert [(result.status, result.png) for result in run.results] == [("accepted", "Ceremonial Brazier.png")]
    assert run.returned


def test_an_interrupted_batch_keeps_its_results_and_lists_the_rest(tmp_path: Path) -> None:
    mod = FakeMod([completed("Summoned Treant"), ConnectionResetError("game closed"), ConnectionResetError("gone")])

    run, progress = _run(mod, tmp_path)

    assert [result.file for result in run.results] == ["Summoned: Treant.png"]
    assert run.interrupted is not None and run.interrupted.startswith("Ceremonial Brazier.png: ConnectionResetError")
    assert run.not_captured == ["Ceremonial Brazier.png", "Faith.png"]
    assert not run.returned
    # Each step reaches the recorder, so a crash still leaves the results on disk.
    assert len(progress) >= 2


def test_a_capture_of_another_object_is_rejected(tmp_path: Path) -> None:
    mod = FakeMod([completed("Zenith"), ended])

    run, _ = _run(mod, tmp_path, ("Faith.png",))

    assert run.results[0].status == "rejected"
    assert run.results[0].reasons == ["wrong model: captured Zenith, expected Faith"]


def test_a_capture_without_renderer_or_inside_the_frame_edge_is_rejected(tmp_path: Path) -> None:
    mod = FakeMod([completed("Summoned Treant", renderers=0, clipped=True), ended])

    run, _ = _run(mod, tmp_path, ("Summoned: Treant.png",))

    assert run.results[0].status == "rejected"
    assert run.results[0].reasons == ["no renderer", "clipped: the subject reaches the edge of the frame"]


def test_a_dark_capture_is_accepted_with_a_warning_for_the_reviewer(tmp_path: Path) -> None:
    # The constellations of Soluna's plane are dark in the game.
    mod = FakeMod([completed("Faith", luminance=0.03), ended])

    run, _ = _run(mod, tmp_path, ("Faith.png",))

    assert (run.results[0].status, run.results[0].warnings) == ("accepted", ["dark: mean luminance 0.030"])


def test_a_mod_error_fails_the_file_and_the_batch_goes_on(tmp_path: Path) -> None:
    mod = FakeMod(
        [
            completed("Summoned Treant"),
            lambda request: {"type": "portrait_error", "file": request["file"], "reason": "Cancelled"},
            completed("Faith"),
            ended,
        ]
    )

    run, _ = _run(mod, tmp_path)

    assert [(result.file, result.status) for result in run.results] == [
        ("Summoned: Treant.png", "accepted"),
        ("Ceremonial Brazier.png", "failed"),
        ("Faith.png", "accepted"),
    ]
    assert run.results[1].reasons == ["Cancelled"]


def test_every_capture_is_drawn_on_one_of_the_sheets(tmp_path: Path) -> None:
    run = PortraitRun(game_build="24405256", preset="portrait-3")
    for name in ("a", "b", "c", "d", "e"):
        Image.new("RGBA", (40, 80), (180, 120, 90, 255)).save(tmp_path / f"{name}.png")
        run.results.append(
            PortraitResult(
                file=f"{name}.png",
                stable_key=f"character:{name}",
                kind="character",
                status="accepted",
                png=f"{name}.png",
            )
        )

    sheets = write_contact_sheets(run, tmp_path, lambda _title: None, tmp_path / "sheets", columns=2, rows=1, tile=40)

    assert [sheet.name for sheet in sheets] == ["sheet-001.png", "sheet-002.png", "sheet-003.png"]


def test_a_recapture_keeps_the_other_captures_and_drops_the_files_earlier_picture(tmp_path: Path) -> None:
    run = PortraitRun(game_build="24405256", preset="portrait-3")
    for name in ("Faith", "Lucian Revald"):
        Image.new("RGBA", (40, 80), (180, 120, 90, 255)).save(tmp_path / f"{name}.png")
        run.results.append(
            PortraitResult(
                file=f"{name}.png",
                stable_key=f"character:{name}",
                kind="character",
                status="accepted",
                png=f"{name}.png",
            )
        )

    recapture = recapture_run(run.to_json(), tmp_path, {"Lucian Revald.png"})

    assert [result.file for result in recapture.results] == ["Faith.png"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["Faith.png"]
