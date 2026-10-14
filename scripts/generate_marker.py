"""Generate a lossless, physically sized printable reference marker."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from photomeasure.markers import marker_svg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--side-mm", type=float, default=50., help="Outer black-square side in millimetres (quiet zone excluded)")
    parser.add_argument("--marker-id", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path("marker_50mm.svg"))
    args = parser.parse_args()
    try:
        svg = marker_svg(args.side_mm, args.marker_id)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Saved {args.output}. Print at actual size with no fit-to-page. Ruler-check the {args.side_mm:g} mm black-square side and enter its actual size in the app.")


if __name__ == "__main__":
    main()
