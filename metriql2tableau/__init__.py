import argparse
import json
import logging
from .metadata import MetriqlMetadata
from .generate import GenerateTDS
import sys

__version__ = "0.2-incomplete"


def main(args: list = None):
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    parser = argparse.ArgumentParser(
        description="Generates Tableau TDS files for metriql datasets"
    )

    parser.add_argument("command", choices=["create-tds"], help="command to execute")

    parser.add_argument("--metriql-url", help="metriql URL", )

    parser.add_argument("--dataset", help="dataset for the TDS file")

    parser.add_argument("--file", help="source of the metadata file. if not set, the source is stdin")

    parsed = parser.parse_args(args=args)
    if parsed.command == "create-tds":
        if parsed.file is not None:
            source = open(parsed.file).read()
        else:
            source = sys.stdin.readline()
        metriql_metadata = MetriqlMetadata(parsed.metriql_url, json.loads(source))
        GenerateTDS(metriql_metadata).generate(parsed.dataset)
