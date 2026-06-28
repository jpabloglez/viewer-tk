import argparse
import logging
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Medical image viewer for DICOM and NIfTI"
    )
    parser.add_argument(
        "path", nargs="?", metavar="PATH",
        help="DICOM directory or NIfTI file (.nii/.nii.gz) — auto-detected by type",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--directory", metavar="DIR", help="DICOM directory (explicit)")
    group.add_argument("-i", "--image", metavar="FILE", help="NIfTI file (explicit)")
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Auto-detect positional path when neither -d/-i is given
    if args.path and not args.directory and not args.image:
        p = args.path
        if os.path.isdir(p):
            args.directory = p
        elif os.path.isfile(p):
            args.image = p
        else:
            print(f"Error: '{p}' is not a valid file or directory.", file=sys.stderr)
            sys.exit(1)

    if args.directory and not os.path.isdir(args.directory):
        print(f"Error: directory '{args.directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if args.image and not os.path.isfile(args.image):
        print(f"Error: file '{args.image}' does not exist.", file=sys.stderr)
        sys.exit(1)

    from .app import run

    run(directory=args.directory, image=args.image)


if __name__ == "__main__":
    main()
