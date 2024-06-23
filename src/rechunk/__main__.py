import logging
from rich.logging import RichHandler, get_console
from rich.traceback import install
from .utils import tqdm

from .alg import main as alg_main


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
    alg_main()


if __name__ == "__main__":
    main()
