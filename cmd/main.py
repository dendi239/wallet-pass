#! /usr/bin/env python3
import argparse
from cmd.bot import main

import textract

from uz.parse import parse_ticket_from_pdf


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", nargs="?")
    parser.add_argument("--ics", nargs="?")
    args = parser.parse_args()

    if args.pdf is not None:
        for page in textract.process(args.pdf).decode("utf-8").split("\f"):
            if page:
                ticket = parse_ticket_from_pdf(page)
                print(ticket)
    else:
        main()
