import csv
import sys
import typing
from pathlib import Path

# list of licenses compatible with MIT
allowed_licenses = [
    "Apache Software License",
    "BSD License",
    "GNU General Public License (GPL)",
    "ISC License (ISCL)",
    "Public Domain",
    "Python Software Foundation License",
    "Mozilla Public License 2.0 (MPL 2.0)",
    "MIT License",
    "The Unlicense (Unlicense)",
]


def check_license_compliance(
    licenses_file: str,
    allowed_licenses: typing.List[str],
) -> typing.List[str]:
    incompliance_items = list()
    with open(licenses_file, mode="r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            name = row["Name"]
            # note that "License" can be a comma separated list of licenses
            licenses = row["License"]
            for license in licenses.split(";"):
                license = license.strip()
                if license not in allowed_licenses:
                    incompliance_items.append((name, licenses))
        return incompliance_items


def main(licenses_file: Path):
    incompliance_items = check_license_compliance(licenses_file, allowed_licenses)
    if len(incompliance_items) > 0:
        print("found dependencies with licenses incompliance with MIT license:")
        for name, license in incompliance_items:
            print(f"- {name}: {license}")
        raise Exception("found dependencies with licenses incompliance with MIT license.")
    else:
        print("all dependencies are compliance with MIT license.")


if __name__ == "__main__":
    main(licenses_file=Path(sys.argv[1]).resolve().absolute())
