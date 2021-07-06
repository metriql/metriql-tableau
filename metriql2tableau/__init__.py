import argparse
import json
from .metadata import MetriqlMetadata
from .generate import GenerateTDS
import sys

__version__ = "0.3"


def main(args: list = None):
    parser = argparse.ArgumentParser(description="Generates Tableau TDS files for metriql datasets")

    parser.add_argument("command", choices=["create-tds"], help="command to execute")

    parser.add_argument("--metriql-url", help="metriql URL", )

    parser.add_argument("--dataset", help="dataset for the TDS file")

    parser.add_argument("--file", help="source of the metadata file. if not set, the source is stdin")

    parser.add_argument("--out", help="target location for TDS file. if not set, the source is stdout")

    parsed = parser.parse_args(args=args)
    if parsed.command == "create-tds":
        if parsed.file is not None:
            source = open(parsed.file).read()
        else:
            source = sys.stdin.readline()
        metriql_metadata = MetriqlMetadata(parsed.metriql_url, json.loads(source))
        GenerateTDS(metriql_metadata).generate(parsed.dataset, parsed.out)
