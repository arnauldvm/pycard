#!/usr/bin/env python3

from jinja2 import Template
import os
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging
import csv
import time
import re
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from livereload import Server


VERSION = '0.1.1a'

DEFAULT_RENDERED_CARDS_FILE = "index.html"


class CardRenderer:
    def __init__(self, input_path, prefix, rendered_cards_file, csv_file=None, css_file=None):
        self.prefix = prefix
        self.input_path = input_path

        self.csv_card_path = csv_file if csv_file else self.get_path("csv")
        self.css_file = css_file if css_file else "{}.{}".format(self.prefix, 'css')
        self.custom_header_path = self.get_path("header.html")
        self.single_card_template_path = self.get_path("html.jinja2")

        self.cards_template_path = os.path.join(os.path.dirname(__file__), 'cards.html.jinja2')

        self.all_cards_rendered_path = os.path.join(input_path, rendered_cards_file)

    def get_path(self, extension):
        return os.path.join(self.input_path, "{}.{}".format(self.prefix, extension))

    def render_cards(self):
        # I've noticed that when saving the CSV file
        # the server reloads an empty page
        # unless I add a small sleep before attempting to read everything
        time.sleep(0.5)

        # load the csv file
        cards_data = []
        with open(self.csv_card_path, "r", encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile, dialect='custom_delimiter')
            for row in reader:
                cards_data.append(row)

        rendered_cards = []

        # load the single card template
        with open(self.single_card_template_path, "r") as template_file:
            template = Template(template_file.read())

            # render the template with card data
            for card_data in cards_data:
                if str(card_data.get('ignore', "false")).lower() == "true":
                    continue

                rendered = template.render(
                    card_data,
                    __card_data=card_data,
                    __time=str(time.time())
                )
                num_cards = card_data.get('num_cards')
                if num_cards is None or re.match("^[^0-9]*$", num_cards):
                    num_cards = 1
                else:
                    num_cards = int(num_cards)
                for i in range(0, num_cards):
                    rendered_cards.append(rendered)

        # Load custom header html if it exists
        custom_header = None

        if os.path.exists(self.custom_header_path):
            with open(self.custom_header_path, "r") as f:
                custom_header = f.read()

        # render the cards template with all rendered cards
        with open(self.cards_template_path, "r") as cards_template_file:
            template = Template(cards_template_file.read())
            with open(self.all_cards_rendered_path, "w") as all_cards_rendered_file:
                all_cards_rendered_file.write(
                    template.render(
                        rendered_cards=rendered_cards,
                        css_file=self.css_file,
                        custom_header=custom_header
                    )
                )


class RenderingEventHandler(FileSystemEventHandler):
    def __init__(self, card_renderers):
        self.card_renderers = card_renderers

    def on_any_event(self, event):
        if event.src_path in [ card_renderer.all_cards_rendered_path for card_renderer in self.card_renderers ]:
            return

        for card_renderer in self.card_renderers:
            card_renderer.render_cards()


def parse_args():
    parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--version', action='version', version="%prog {}".format(VERSION))
    parser.add_argument("--path", "-p",
                      help="path to assets",
                      default=os.getcwd())

    parser.add_argument("--prefix", "-x",
                      help="filename prefix",
                      default="_card")

    parser.add_argument("--delimiter", "-d",
                      help="delimiter used in the csv file",
                      default=",")

    parser.add_argument("--port",
                      help="port to use for live reloaded page",
                      type=int,
                      default=8800)

    parser.add_argument("--address",
                      help="host address to bind to",
                      dest="host_address",
                      default="0.0.0.0",
                      metavar="ADDRESS")

    parser.add_argument("--render",
                     help="rendered file",
                     dest="rendered_cards_file",
                     default=DEFAULT_RENDERED_CARDS_FILE)

    parser.add_argument("--csv",
                     help="csv file [default: prefix + '.csv']",
                     dest="csv_file")

    parser.add_argument("--css",
                     help="css file [default: prefix + '.css']",
                     dest="css_file")

    parser.add_argument("--pattern",
                     help="activates pattern matching",
                     default=None)

    return parser.parse_args()


def re_glob(dir, pattern):
    regex = re.compile(pattern)
    files = {
        matched.group(1): file
        for file in os.listdir(dir)
        for matched in [ regex.match(file) ]
        if matched
    }
    return files

def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    args = parse_args()

    port = args.port
    assets_path = args.path
    file_prefix = args.prefix
    host_address = args.host_address
    rendered_cards_file = args.rendered_cards_file
    csv_file = args.csv_file
    css_file = args.css_file
    pattern = args.pattern

    csv.register_dialect('custom_delimiter', delimiter=args.delimiter)

    if pattern is None:
        card_renderers = [ CardRenderer(assets_path, file_prefix, rendered_cards_file, csv_file, css_file) ]
    else:
        matches = re_glob(assets_path, pattern + re.escape(".html.jinja2"))
        card_renderers = [
            CardRenderer(assets_path,
                file_prefix.format(match),
                rendered_cards_file.format(match),
                csv_file.format(match),
                css_file.format(match)
            )
            for match in matches.keys()
        ]

    observer = Observer()
    observer.schedule(LoggingEventHandler(), assets_path, recursive=True)
    observer.schedule(RenderingEventHandler(card_renderers), assets_path, recursive=True)

    for card_renderer in card_renderers:
        card_renderer.render_cards()

    observer.start()

    server = Server()
    for card_renderer in card_renderers:
        server.watch(card_renderer.all_cards_rendered_path)
    server.serve(root=assets_path, port=port, host=host_address)

    observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
