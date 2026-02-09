"""
Utility functions
"""

import argparse
import logging


def add_log_options(parser: argparse.ArgumentParser) -> None:
    """Add logging-specific options to the argument parser

    Args:
        parser (argparse.ArgumentParser): Parser to modify
    """
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal logging")
    parser.add_argument(
        "-v",
        action="count",
        dest="vb",
        default=0,
        help="Increase verbosity (repeatable)",
    )


def process_log_options(log: logging.Logger, args: argparse.Namespace) -> bool:
    if not log.handlers:
        h = logging.StreamHandler()
        fmt = "[{levelname}] {asctime} ({name}) {message}"
        h.setFormatter(logging.Formatter(fmt, style="{"))
        log.addHandler(h)
    if args.quiet:
        log.setLevel(logging.CRITICAL)
    else:
        log.setLevel((logging.ERROR, logging.INFO, logging.DEBUG)[min(args.vb, 2)])
    return args.quiet
