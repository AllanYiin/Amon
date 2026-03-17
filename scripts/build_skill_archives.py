from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amon.skills import build_skill_archive, iter_skill_directories


def main() -> int:
    parser = argparse.ArgumentParser(description="Build .skill archives from bundled skill directories.")
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "src" / "amon" / "resources" / "skills",
        help="Bundled skill source directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "skills",
        help="Output directory for generated .skill archives.",
    )
    args = parser.parse_args()

    source_dir = args.source.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for skill_dir in iter_skill_directories(source_dir):
        output_path = output_dir / f"{skill_dir.name}.skill"
        build_skill_archive(skill_dir, output_path)
        print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
