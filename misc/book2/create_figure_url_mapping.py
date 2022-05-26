import argparse
from probml_utils.url_utils import figure_url_mapping_from_lof

parser = argparse.ArgumentParser(description="create figure url mapping")
parser.add_argument("-lof", "--lof", type=str, help="")
parser.add_argument("-csv", "--csv", type=str, help="")
args = parser.parse_args()

print(f"Parsing started from {args.lof}...........")

if args.csv:
    figure_mapping = figure_url_mapping_from_lof(args.lof, args.csv, book_no=2)
else:
    figure_mapping = figure_url_mapping_from_lof(args.lof, "", book_no=2)
