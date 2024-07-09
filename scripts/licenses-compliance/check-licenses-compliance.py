import csv
import sys
import typing
from pathlib import Path

# list of licenses compatible with MIT
allowed_licenses = [
    "MIT",
    "Apache-2.0",
    "BSD",
    "ISC",
]


def check_license_compliance(
    licenses_file: str,
    allowed_licenses: typing.List[str],
) -> typing.List[str]:
    incompliance_items = list()
    with open(licenses_file, mode="r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row["License"] not in allowed_licenses:
                incompliance_items.append((row["Name"], row["License"]))
        return incompliance_items


def main(licenses_file: Path):
    incompliance_items = check_license_compliance(licenses_file, allowed_licenses)
    if len(incompliance_items) > 0:
        print("found dependencies with licenses incompliance with MIT license:")
        for name, license in incompliance_items:
            print(f"- {name}: {license}")
    else:
        print("all dependencies are compliance with MIT license.")


if __name__ == "__main__":
    main(licenses_file=Path(sys.argv[1]).resolve().absolute())
