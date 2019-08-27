from jinja2 import Template
import os
from optparse import OptionParser
import logging
import csv
import time
import re
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler, FileSystemEventHandler
from itertools import zip_longest
from livereload import Server


VERSION = '0.1.0'

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

                num_cards = int(num_cards)
                for i in range(0, int(num_cards)):
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
    def __init__(self, card_renderer):
        self.card_renderer = card_renderer

    def on_any_event(self, event):
        if event.src_path == self.card_renderer.all_cards_rendered_path:
            return

        self.card_renderer.render_cards()


def parse_options():
    parser = OptionParser(
        usage="usage: %prog [options]",
        version="%prog {}".format(VERSION)
    )
    parser.add_option("-p", "--path",
                      help="path to assets [default: %default]",
                      dest="path",
                      default=os.getcwd(),
                      metavar="PATH")

    parser.add_option("-x", "--prefix",
                      help="filename prefix [default: %default]",
                      dest="prefix",
                      default="_card",
                      metavar="PREFIX")

    parser.add_option("-d", "--delimiter",
                      help="delimiter used in the csv file [default: %default]",
                      dest="delimiter",
                      default=",",
                      metavar="DELIMITER")

    parser.add_option("--port",
                      help="port to use for live reloaded page [default: %default]",
                      dest="port",
                      type="int",
                      default=8800,
                      metavar="PORT")

    parser.add_option("--address",
                      help="host address to bind to [default: %default]",
                      dest="host_address",
                      default="0.0.0.0",
                      metavar="ADDRESS")

    parser.add_option("--render",
                     help="rendered file [default: %default]",
                     dest="rendered_cards_file",
                     default=DEFAULT_RENDERED_CARDS_FILE,
                     metavar="RENDERED_CARDS_FILE")

    parser.add_option("--csv",
                     help="csv file [default: prefix + '.csv']",
                     dest="csv_file",
                     metavar="CSV_FILE")

    parser.add_option("--css",
                     help="css file [default: prefix + '.css']",
                     dest="css_file",
                     metavar="CSS_FILE")

    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    (options, args) = parse_options()

    port = options.port
    assets_path = options.path
    file_prefix = options.prefix
    host_address = options.host_address
    rendered_cards_file = options.rendered_cards_file
    csv_file = options.csv_file
    css_file = options.css_file

    csv.register_dialect('custom_delimiter', delimiter=options.delimiter)

    card_renderer = CardRenderer(assets_path, file_prefix, rendered_cards_file, csv_file, css_file)

    observer = Observer()
    observer.schedule(LoggingEventHandler(), assets_path, recursive=True)
    observer.schedule(RenderingEventHandler(card_renderer), assets_path, recursive=True)

    card_renderer.render_cards()

    observer.start()

    server = Server()
    server.watch(card_renderer.all_cards_rendered_path)
    server.serve(root=assets_path, port=port, host=host_address)

    observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
