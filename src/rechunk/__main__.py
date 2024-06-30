import logging
from rich.logging import RichHandler, get_console
from rich.traceback import install
from .utils import tqdm

from .alg import main as alg_main
import argparse


class TqdmLoggingHandler(RichHandler):
    def emit(self, record):
        with tqdm.external_write_mode(file=self.console.file):
            return super().emit(record)


def setup_logger():
    FORMAT = "%(message)s"
    install()
    logging.basicConfig(
        level=logging.INFO,
        datefmt="[%H:%M]",
        format=FORMAT,
        handlers=[
            TqdmLoggingHandler(
                enable_link_path=False,
                show_level=True,
                show_path=False,
                show_time=False,
            )
        ],
    )


def argparse_func():
    parser = argparse.ArgumentParser(
        description="OCI Rechunk: Repartition your OCI images into OSTree commits."
    )
    parser.add_argument(
        "-r", "--repo", help="Path to the OSTree repo", default="./repo"
    )
    parser.add_argument(
        "-b",
        "--ref",
        help="The branch in the OSTree repo to use.",
        default="master",
    )
    parser.add_argument(
        "-c",
        "--contentmeta",
        help="Output path for contentmeta for ostree-rs-ext.",
        default="./contentmeta.json",
    )
    parser.add_argument(
        "-p",
        "--previous-manifest",
        help="The previous build manifest.",
        default=None,
    )
    parser.add_argument(
        "--version",
        help="The version format (e.g., '3.1_<date>').",
        default=None,
    )
    parser.add_argument(
        "-l", "--label", help="Add labels to the output image.", action="append"
    )
    parser.add_argument(
        "--version-fn", help="Output path for version name.", default=None
    )

    # Hyperparameters
    group = parser.add_argument_group("Hyperparameters")
    group.add_argument(
        "-m",
        "--meta",
        help="Path to the meta.yml file. Contains meta package groupings that are used to create the layers. A default file is provided.",
        required=False,
        default=None,
    )
    group.add_argument(
        "--max-layers",
        help="Maximum number of layers to create (0-100).",
        type=int,
        default=None,
    )
    group.add_argument(
        "--prefill-ratio",
        help="The amount to prefill layers in the first pass. "
        + "It is heuristic and faster than the fill step, but may be non-optimal. "
        + "The lower the ratio, the larger this script will take.",
        type=float,
        default=None,
    )
    group.add_argument(
        "--max-layer-ratio",
        help="The amount after which the fill step will stop adding packages to layers. "
        + "Helps the output layers be uniform in size. "
        + "Meta packages will always be grouped together.",
        type=float,
        default=None,
    )

    args = parser.parse_args()
    alg_main(
        repo=args.repo,
        ref=args.ref,
        contentmeta_fn=args.contentmeta,
        meta_fn=args.meta,
        previous_manifest=args.previous_manifest,
        max_layers=args.max_layers,
        prefill_ratio=args.prefill_ratio,
        max_layer_ratio=args.max_layer_ratio,
        labels=args.label,
        version=args.version,
        version_fn=args.version_fn,
        result_fn=None,
    )


def main():
    setup_logger()
    try:
        argparse_func()
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Received keyboard interrupt. Exiting.")


if __name__ == "__main__":
    main()
