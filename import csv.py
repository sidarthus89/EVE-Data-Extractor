import csv
import json
import requests

# === CONFIG ===
CSV_URL = "https://www.fuzzwork.co.uk/dump/latest/staStations.csv"
OUTPUT_JSON = "stations_full.json"
AS_MAP = False  # Set to True for stationID -> stationData dict


def download_csv(url):
    print(f"Downloading: {url}")
    response = requests.get(url)
    response.raise_for_status()
    return response.text.splitlines()


def convert_csv_to_json(csv_lines, as_map=False):
    reader = csv.DictReader(csv_lines)

    if as_map:
        data = {row["stationID"]: row for row in reader}
    else:
        data = list(reader)

    return data


def save_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved JSON to {filename}")


if __name__ == "__main__":
    csv_lines = download_csv(CSV_URL)
    json_data = convert_csv_to_json(csv_lines, AS_MAP)
    save_json(json_data, OUTPUT_JSON)
