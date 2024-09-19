import json
import pathlib
from argparse import ArgumentParser
from datetime import datetime, timezone
from sys import exit
from zipfile import ZipFile

from colorama import Fore, Style
from numbers_parser import Document

from onepass2numbers import _get_version


def print_warning(s: str) -> None:
    print(Fore.RED + Style.BRIGHT + f"WARNING! {s}" + Style.RESET_ALL)


def print_error(s: str) -> None:
    print(Fore.RED + Style.BRIGHT + f"ERROR! {s}" + Style.RESET_ALL)


def fix_dup_keys(ordered_pairs: dict) -> dict:
    index = 0
    dictionary = {}
    for key, value in ordered_pairs:
        if key in dictionary:
            dictionary[key + str(index)] = value
            index += 1
        else:
            dictionary[key] = value
    return dictionary


def field_filter(fields: dict[str, str]) -> list[str]:
    filtered_fields = []
    for field in fields:
        value_key = next(iter(field["value"].keys()))
        value = field["value"][value_key]
        if not value or (isinstance(value, str) and value.startswith("otpauth://")):
            continue
        filtered_fields.append(f"{field['title']}: {value}")

    return filtered_fields


class PasswordConverter:
    def __init__(self) -> None:
        parser = ArgumentParser(
            description="Convert a 1Password 1PUX file to a Numbers spreadsheet",
        )
        parser.add_argument("-V", "--version", action="store_true")

        parser.add_argument(
            "--output",
            "-o",
            help="The output file name.",
        )
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Supress informational messages.",
        )
        parser.add_argument(
            "archive",
            nargs="?",
            metavar="1PUX",
            type=pathlib.Path,
            help="1Password 1PUX export",
        )
        self.args = parser.parse_args()
        if self.args.version:
            print(_get_version())
            exit(0)
        elif not self.args.archive:
            parser.print_help()
            exit(1)

    def read_1pux_data(self) -> None:
        with ZipFile(self.args.archive) as zipf, zipf.open("export.data") as dataf:
            return json.load(dataf, object_pairs_hook=fix_dup_keys)

    def convert(self) -> None:
        try:
            self.data = self.read_1pux_data()
        except FileNotFoundError as e:
            print_error(str(e))
        else:
            self.convert_data_to_numbers()

    def add_sheet(self, name: str) -> None:
        if self.current_sheet_num > 0:
            self.doc.add_sheet()
        self.current_sheet = self.doc.sheets[self.current_sheet_num]
        self.current_sheet.name = name

        for col, value in enumerate(
            [
                "Title",
                "URL",
                "Username",
                "Password",
                "OTP",
                "Created",
                "Updated",
                "Notes",
            ],
        ):
            self.current_sheet.tables[0].write(0, col, value)
        self.current_sheet_num += 1

    def add_row(self, item: object, row: int) -> None:
        if "overview" not in item:
            print_warning("Overview is empty! Skipping item")
            return

        details = item.get("details", {})
        notes = details.get("notesPlain", "")

        section_notes = []
        login_totp = ""
        for section in item["details"]["sections"]:
            if len(section["fields"]) > 0:
                fields = field_filter(section["fields"])
                section_notes += ["\n".join(fields)]
            for field in section["fields"]:
                value = field["value"]
                login_totp = value.get("totp", "")

        notes += "\n\n".join(section_notes)

        login_username, login_password = "", ""
        for field in details["loginFields"]:
            if "designation" not in field:
                continue
            designation = field["designation"]
            if designation == "username":
                login_username = field["value"]
            elif designation == "password":
                login_password = field["value"]
            else:
                print_warning(f"Unknown designation '{designation}'")

        for col, value in enumerate(
            [
                item["overview"].get("title", ""),
                item["overview"].get("url", ""),
                login_username,
                login_password,
                login_totp,
                datetime.fromtimestamp(item["createdAt"], tz=timezone.utc),
                datetime.fromtimestamp(item["updatedAt"], tz=timezone.utc),
                notes,
            ],
        ):
            self.current_sheet.tables[0].write(row, col, value)

    def convert_data_to_numbers(self) -> None:
        self.doc = Document()
        self.current_sheet_num = 0

        if len(self.data["accounts"]) > 1:
            print_warning("Only exporting one account")

        account = self.data["accounts"][0]
        if not self.args.quiet:
            print(f"Processing account: {account['attrs']['name']}")

        for vault in account["vaults"]:
            folder = vault["attrs"]["name"]
            if not self.args.quiet:
                print(f"Processing folder: {folder}")

            self.add_sheet(folder)

            iterable = vault["items"]
            if len(iterable) == 0:
                print_warning(f"Empty iterable for '{folder}'")
                return

            if "item" in iterable[0]:
                iterable = iterable[0].values()

            row = 1
            for item in iterable:
                self.add_row(item, row)
                row += 1

        self.doc.save(self.args.output)


def main() -> None:
    converter = PasswordConverter()
    converter.convert()


if __name__ == "__main__":  # pragma: no cover
    # execute only if run as a script
    main()
