"""Create a reviewable canonical menu and vectors from JSON/CSV/item-per-line text.

Does not activate a menu or mutate a running backend. Default encoding is local;
remote provider usage requires deliberate environment configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.mvp.menu import import_status
from app.mvp.menu_embeddings import MenuIndex, provider_from_env
from app.mvp.menu_import import MenuPrepareRequest, parse_menu, review_warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--name", default="Imported menu")
    parser.add_argument(
        "--media-type", choices=["application/json", "text/csv", "text/plain"]
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Reviewed candidate JSON destination"
    )
    args = parser.parse_args()
    index_path = args.output.with_suffix(".index.json")
    if (
        args.output.exists()
        or index_path.exists()
        or args.input.resolve() in {args.output.resolve(), index_path.resolve()}
    ):
        parser.error("Choose new output paths; existing files are not overwritten")
    media_type = args.media_type or {
        ".json": "application/json",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }.get(args.input.suffix.lower())
    if media_type is None:
        parser.error(
            "Use JSON/CSV/TXT or specify --media-type; PDF/photo extraction is not configured"
        )
    try:
        menu = parse_menu(
            MenuPrepareRequest(
                content=args.input.read_text(encoding="utf-8-sig"),
                media_type=media_type,
                name=args.name,
            )
        )
        index = MenuIndex.build(menu, provider_from_env())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # This artifact is for inspection/adapter handoff, never trusted activation.
        index_path.write_text(
            json.dumps(
                {
                    **index.status(),
                    "vectors": [
                        {"menu_id": key, "vector": row}
                        for key, row in zip(index.item_ids, index.vectors, strict=True)
                    ],
                },
                indent=2,
            )
            + "\n"
        )
        args.output.write_text(menu.model_dump_json(indent=2) + "\n")
    except (ValueError, OSError) as exc:
        # Do not print raw validation input/provider bodies.
        parser.exit(
            1,
            f"Menu preparation failed ({type(exc).__name__}); check input/configuration.\n",
        )
    print(
        json.dumps(
            {
                "menu_path": str(args.output),
                "index_path": str(index_path),
                "index": index.status(),
                "warnings": review_warnings(menu),
                "import_status": import_status(menu),
                "requires_human_review": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
