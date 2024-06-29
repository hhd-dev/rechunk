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
        handlers=[TqdmLoggingHandler()],
    )


def main():
    setup_logger()

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
        help="Maximum number of layers to create.",
        type=int,
        default=39,
    )
    group.add_argument(
        "--prefill-ratio",
        help="The amount to prefill layers in the first pass."
        + "It is heuristic and faster than the fill step, but may be non-optimal."
        + "The lower the ratio, the larger this script will take.",
        type=float,
        default=0.4,
    )
    group.add_argument(
        "--max-layer-ratio",
        help="The amount after which the fill step will stop adding packages to layers."
        + "Helps the output layers be uniform in size."
        + "Meta packages will always be grouped together.",
        type=float,
        default=1.3,
    )

    args = parser.parse_args()
    alg_main(
        args.repo,
        args.ref,
        args.contentmeta,
        args.meta,
        args.previous_manifest,
        args.max_layers,
        args.prefill_ratio,
        args.max_layer_ratio,
    )


if __name__ == "__main__":
    main()
