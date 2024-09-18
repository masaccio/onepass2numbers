import json
from argparse import ArgumentParser
from datetime import datetime
from sys import argv, exit
from zipfile import ZipFile

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
        metavar="1PUX-ARCHIVE",
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


def red_message(s: str) -> None:
    print(f"\033[31mWARNING! {s}\033[0m")


parser = command_line_parser()
args = parser.parse_args()
if args.version:
    print(_get_version())
    exit(0)
elif not args.archive:
    parser.print_help()
    exit(1)

data = read_1pux_data(args.archive)

doc = Document()
sheet_num = 0

if len(data["accounts"]) > 1:
    red_message("only exporting one account")

account = data["accounts"][0]
print(f"Processing account: {account['attrs']['name']}")

# TODO:
# Other login fields (add to notes)
# ignore empty fields in notes
# ignore OTP in fields for notes

for vault in account["vaults"]:
    folder = vault["attrs"]["name"]
    print(f"Processing folder: {folder}")

    iterable = vault["items"]
    if len(iterable) == 0:
        red_message("Empty iterable")
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
        ]
    ):
        sheet.tables[0].write(0, col, value)

    if "item" in iterable[0]:
        iterable = iterable[0].values()

    row = 1
    for item in iterable:
        favorite = item["favIndex"] if "favIndex" in item else 0

        if "overview" not in item:
            print("\033[93mWARNING! Overview is empty! Skipping item\033[0m")
            continue
        overview = item["overview"]
        name = overview["title"] if "title" in overview else ""
        login_uri = overview["url"] if "url" in overview else ""

        # Details Subsection
        details = item["details"] if "details" in item else {}
        notes = details["notesPlain"] if "notesPlain" in details else ""
        updated = datetime.fromtimestamp(item["updatedAt"])
        created = datetime.fromtimestamp(item["createdAt"])

        for section in item["details"]["sections"]:
            if len(section["fields"]) > 1:
                fields = [
                    f"{x['title']}: {x['value'][list(x['value'].keys())[0]]}"
                    for x in section["fields"]
                ]
                notes += "\n".join(fields)

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
                login_totp = value["totp"] if "totp" in value else ""

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
            ]
        ):
            sheet.tables[0].write(row, col, value)

        row += 1

    sheet_num += 1

doc.save(argv[2])
