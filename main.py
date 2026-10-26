import yaml
from yaml import CLoader as Loader

from modules.ics_export import IcsExportModule
from modules.json_export import JsonExportModule
from scraper import Scraper

import sys
import api

available_modules = {"json": JsonExportModule, "ics": IcsExportModule}


def main():
    if sys.argv[1] == "solve":
        print("Telescopium has started...")

        with open("config.yml") as f:
            config = yaml.load(f.read(), Loader)

        scraper = Scraper(config["scraper"])

        for export_method in config["export"].keys():
            if export_method in available_modules.keys():
                export_module = available_modules[export_method](
                    config["export"][export_method]
                )
                export_module.export(scraper.shifts)

        print("Finished")
    elif sys.argv[1] == "api":
        try:
            host = sys.argv[2]
            port = int(sys.argv[3])
            if port < 0 or port >= 65535:
                raise ValueError()

        except ValueError:
            print(f"Invalid port: {port}", file=sys.stderr)
            sys.exit(1)

        api.API().run(host, port)


if __name__ == "__main__":
    main()
