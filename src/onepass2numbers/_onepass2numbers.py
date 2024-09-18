import json
import pathlib
from argparse import ArgumentParser
from datetime import datetime
from sys import exit
from zipfile import ZipFile

from colorama import Fore, Style
from numbers_parser import Document

from onepass2numbers import _get_version


def command_line_parser() -> ArgumentParser:
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
        help="Supress informational messages.",
    )
    parser.add_argument(
        "archive",
        nargs="?",
        metavar="1PUX",
        type=pathlib.Path,
        help="1Password 1PUX export",
    )
    return parser


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


def read_1pux_data(filename: str) -> object:
    with ZipFile(filename) as zipf, zipf.open("export.data") as dataf:
        return json.load(dataf, object_pairs_hook=fix_dup_keys)


def print_warning(s: str) -> None:
    print(Fore.RED + Style.BRIGHT + f"WARNING! {s}" + Style.RESET_ALL)


def print_error(s: str) -> None:
    print(Fore.RED + Style.BRIGHT + f"ERROR! {s}" + Style.RESET_ALL)


def field_filter(fields: dict[str, str]) -> list[str]:
    filtered_fields = []
    for field in fields:
        value_key = next(iter(field["value"].keys()))
        value = field["value"][value_key]
        if not value or (isinstance(value, str) and value.startswith("otpauth://")):
            continue
        filtered_fields.append(f"{field["title"]}: {value}")

    return filtered_fields


parser = command_line_parser()
args = parser.parse_args()

if args.version:
    print(_get_version())
    exit(0)
elif not args.archive:
    parser.print_help()
    exit(1)

try:
    data = read_1pux_data(args.archive)
except FileNotFoundError as e:
    print_error(str(e))
    exit(1)

doc = Document()
sheet_num = 0

if len(data["accounts"]) > 1:
    print_warning("only exporting one account")

account = data["accounts"][0]
print(f"Processing account: {account['attrs']['name']}")

for vault in account["vaults"]:
    folder = vault["attrs"]["name"]
    print(f"Processing folder: {folder}")

    iterable = vault["items"]
    if len(iterable) == 0:
        print_warning("Empty iterable")
        continue

    if sheet_num > 0:
        doc.add_sheet()
    sheet = doc.sheets[sheet_num]
    sheet.name = folder

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
        sheet.tables[0].write(0, col, value)

    if "item" in iterable[0]:
        iterable = iterable[0].values()

    row = 1
    for item in iterable:
        favorite = item.get("favIndex", 0)

        if "overview" not in item:
            print_warning("Overview is empty! Skipping item")
            continue
        overview = item["overview"]
        name = overview.get("title", "")
        login_uri = overview.get("url", "")

        # Details Subsection
        details = item.get("details", {})
        notes = details.get("notesPlain", "")
        updated = datetime.fromtimestamp(item["updatedAt"])
        created = datetime.fromtimestamp(item["createdAt"])

        section_notes = []
        for section in item["details"]["sections"]:
            if len(section["fields"]) > 0:
                fields = field_filter(section["fields"])
                section_notes += ["\n".join(fields)]
        notes += "\n\n".join(section_notes)

        login_username, login_password = "", ""
        for field in details["loginFields"]:
            if "designation" not in field:
                continue
            if field["designation"] == "username":
                login_username = field["value"]
            if field["designation"] == "password":
                login_password = field["value"]

        login_totp = ""
        for section in details["sections"]:
            fields = section["fields"]
            if len(fields) == 0:
                continue
            for field in fields:
                value = field["value"]
                login_totp = value.get("totp", "")

        for col, value in enumerate(
            [
                name,
                login_uri,
                login_username,
                login_password,
                login_totp,
                created,
                updated,
                notes,
            ],
        ):
            sheet.tables[0].write(row, col, value)

        row += 1

    sheet_num += 1

doc.save(args.output)
