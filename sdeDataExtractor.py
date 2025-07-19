import os
import yaml
import json
import threading
import itertools
import sys
import time

# ─── Paths ────────────────────────────────────────────────
SDE_ROOT = "sde"
REGIONS_PATH = os.path.join(SDE_ROOT, "fsd", "regions.yaml")
STATIONS_PATH = os.path.join(SDE_ROOT, "bsd", "staStations.yaml")
MARKET_GROUPS_PATH = os.path.join(SDE_ROOT, "fsd", "marketGroups.yaml")
TYPES_PATH = os.path.join(SDE_ROOT, "fsd", "types.yaml")
ICON_IDS_PATH = os.path.join(SDE_ROOT, "fsd", "iconIDs.yaml")


# ─── Spinner Utility ───────────────────────────────────────
class Spinner:
    """Context-manager for an animated spinner in the console."""

    def __init__(self, message="Working"):
        self.message = message
        self._spinner = itertools.cycle(["|", "/", "-", "\\"])
        self._stop = False
        self._thread = threading.Thread(target=self._spin)

    def _spin(self):
        while not self._stop:
            sys.stdout.write(f"\r{self.message} {next(self._spinner)}")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * (len(self.message) + 2) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop = True
        self._thread.join()


# ─── Common Utilities ─────────────────────────────────────
def load_yaml(path):
    if not os.path.exists(path):
        print(f"⚠️ Missing YAML file: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"💾 Saved: {filename}")


def normalize_yes_no(val):
    v = val.strip().lower()
    if v in ("yes", "y"):
        return True
    if v in ("no", "n"):
        return False
    return None


# ─── Region Extraction ────────────────────────────────────
def extract_regions():
    raw = load_yaml(REGIONS_PATH)
    regions = {}
    print(f"\n🌍 Parsing {len(raw)} regions…")
    for rid, info in raw.items():
        regions[rid] = {
            "regionID":        rid,
            "regionName":      info.get("regionName", ""),
            "constellationIDs": info.get("constellations", [])
        }
    return regions


# ─── Station Extraction ───────────────────────────────────
def extract_stations():
    raw = load_yaml(STATIONS_PATH)
    stations = {}
    print(f"\n🏭 Parsing {len(raw)} stations…")
    for s in raw:
        sid = str(s.get("stationID", ""))
        if not sid:
            continue
        stations[sid] = {
            "stationID":       sid,
            "stationName":     s.get("stationName", ""),
            "solarSystemID":   s.get("solarSystemID", ""),
            "regionID":        s.get("regionID", ""),
            "constellationID": s.get("constellationID", ""),
            "stationTypeID":   s.get("stationTypeID", "")
        }
    return stations


# ─── Market Menu Extraction ────────────────────────────────
def load_icon_map():
    raw = load_yaml(ICON_IDS_PATH)
    icon_map = {}
    for key, info in raw.items():
        try:
            iid = int(key)
            file_path = info.get("iconFile", "")
            icon_map[iid] = os.path.basename(file_path)
        except ValueError:
            continue
    return icon_map


def extract_market_menu(include_items=False):
    groups_data = load_yaml(MARKET_GROUPS_PATH)
    types_data = load_yaml(TYPES_PATH) if include_items else {}
    icon_map = load_icon_map()

    group_map = {}
    children = {}

    print(f"\n⏳ Building market menu (alphabetical)...")
    with Spinner("Processing"):
        # 1) Build group entries
        for gid_str, info in groups_data.items():
            gid = int(gid_str)
            name = info.get("nameID", {}).get("en", "").strip()
            icon_id = int(info.get("iconID", 0))
            has_types = bool(info.get("hasTypes", 0))

            group_map[gid] = {
                "name": name,
                "_info": {
                    "marketGroupID": str(gid),
                    "iconID":        str(icon_id),
                    "iconFile":      icon_map.get(icon_id, ""),
                    "hasTypes":      str(has_types)
                },
                "items":   [],
                "children": []
            }
            parent = info.get("parentGroupID")
            if parent is not None:
                children.setdefault(parent, []).append(gid)

        # 2) Sort children by name and attach
        for gid, grp in group_map.items():
            child_ids = children.get(gid, [])
            # Sort by the group's own name
            grp["children"] = sorted(
                child_ids,
                key=lambda cid: group_map[cid]["name"].lower()
            )

        # 3) Optionally attach and sort item types
        if include_items:
            for tid_str, tinfo in types_data.items():
                if not tinfo.get("published") or "marketGroupID" not in tinfo:
                    continue
                tid = int(tid_str)
                gid = tinfo["marketGroupID"]
                entry = {
                    "typeID":   str(tid),
                    "typeName": tinfo["name"].get("en", "").strip(),
                    "iconID":   str(int(tinfo.get("iconID", 0))),
                    "iconFile": icon_map.get(int(tinfo.get("iconID", 0)), ""),
                    "volume":   tinfo.get("volume", 0),
                    "mass":     tinfo.get("mass", 0),
                    "published": True
                }
                if gid in group_map:
                    group_map[gid]["items"].append(entry)

        # After all items added, sort each group's items by typeName
        if include_items:
            for grp in group_map.values():
                grp["items"] = sorted(
                    grp["items"],
                    key=lambda x: x["typeName"].lower()
                )

    # 4) Determine alphabetical roots
    all_children = {cid for clist in children.values() for cid in clist}
    roots = sorted(
        [gid for gid in group_map if gid not in all_children],
        key=lambda g: group_map[g]["name"].lower()
    )

    # 5) Recursively assemble tree
    def build_tree(gid):
        grp = group_map[gid]
        node = {grp["name"]: {"_info": grp["_info"]}}
        if grp["items"]:
            node[grp["name"]]["items"] = grp["items"]  # already sorted
        for child in grp["children"]:
            node[grp["name"]].update(build_tree(child))
        return node

    menu = {}
    for gid in roots:
        menu.update(build_tree(gid))

    return menu


# ─── Main Interactive Menu ─────────────────────────────────
def main():
    print("\n🛠 EVE Market Data Extractor\n")
    print("1) Build regions.json")
    print("2) Build stations.json")
    print("3) Build marketMenu.json")
    print("4) Build Everything\n")

    choice = input("Enter choice [1-4]: ").strip()
    if choice not in ("1", "2", "3", "4"):
        print("⚠️ Invalid selection.")
        return

    if choice in ("1", "4"):
        regions = extract_regions()
        write_json("regions.json", regions)

    if choice in ("2", "4"):
        stations = extract_stations()
        write_json("stations.json", stations)

    if choice in ("3", "4"):
        menu = extract_market_menu(include_items=True)
        write_json("marketMenu.json", menu)


if __name__ == "__main__":
    main()
