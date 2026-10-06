"""Image titles of the kinds of character that share a wiki page but not a model.

A wiki page can hold several kinds of a character, such as the four training
dummies or the eight Vithean chests. Kinds that show the same model share the
page's image. A kind whose model differs from the page's reference model gets
its display name as its image title, so that it can show its own picture
(design D5 of the change restore-missing-wiki-images).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class PageCharacter:
    """A character that a wiki page shows, with the key of the model it shows."""

    stable_key: str
    wiki_page_name: str
    display_name: str
    model_key: str


def model_image_names(characters: Iterable[PageCharacter]) -> Mapping[str, str]:
    """The image title of each character whose kind's model differs from its page's, by stable key.

    The reference model of a page is the model of the kind whose display name
    is the page title, or else the model that most kinds show. Characters of
    pages whose kinds all show one model keep their image and are not listed.
    """
    pages: dict[str, dict[str, list[PageCharacter]]] = defaultdict(lambda: defaultdict(list))
    for character in characters:
        pages[character.wiki_page_name][character.display_name].append(character)
    images: dict[str, str] = {}
    for page, kinds in pages.items():
        if len(kinds) < 2:
            continue
        models = {name: {member.model_key for member in members} for name, members in kinds.items()}
        if len({model for kind_models in models.values() for model in kind_models}) < 2:
            continue
        for name, kind_models in models.items():
            if len(kind_models) > 1:
                raise ValueError(
                    f"{page}: the kind {name!r} shows {len(kind_models)} models, so no image title tells them apart"
                )
        model_by_kind = {name: next(iter(kind_models)) for name, kind_models in models.items()}
        reference = _reference_model(page, model_by_kind)
        for name, members in kinds.items():
            if model_by_kind[name] != reference:
                images.update((member.stable_key, name) for member in members)
    return images


def _reference_model(page: str, model_by_kind: Mapping[str, str]) -> str:
    """The model that keeps the page's image: the base kind's, or the one that most kinds show."""
    if page in model_by_kind:
        return model_by_kind[page]
    counts = Counter(model_by_kind.values()).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        raise ValueError(f"{page}: as many kinds show one model as another, so neither keeps the page's image")
    return counts[0][0]
