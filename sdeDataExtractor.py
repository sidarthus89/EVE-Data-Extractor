import os
import yaml
import json
import requests
import shutil
from tqdm import tqdm

# ─── Paths ────────────────────────────────────────────────
SDE_ROOT = "sde"
MARKET_GROUPS_PATH = os.path.join(SDE_ROOT, "fsd", "marketGroups.yaml")
TYPES_PATH = os.path.join(SDE_ROOT, "fsd", "types.yaml")
STATIONS_PATH = os.path.join(SDE_ROOT, "bsd", "staStations.yaml")
ICON_IDS_PATH = os.path.join(SDE_ROOT, "bsd", "iconIDs.yaml")

# This is the path where the extracted SDE icon PNG files are stored
# Adjust if your extracted icons folder is somewhere else!
SDE_ICONS_PATH = os.path.join(SDE_ROOT, "icons")

TYPE_ICON_DIR = os.path.join("icons", "types")
GROUP_ICON_DIR = os.path.join("icons", "groups")

# ─── Utilities ─────────────────────────────────────────────


def load_yaml(path):
    if not os.path.exists(path):
        print(f"⚠️ Missing YAML file: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"💾 Saved: {filename}")


def normalize_yes_no(value):
    value = value.strip().lower()
    if value in ("yes", "y"):
        return True
    elif value in ("no", "n"):
        return False
    else:
        return None


# ─── Stations ──────────────────────────────────────────────

def extract_stations():
    stations_raw = load_yaml(STATIONS_PATH) or []
    stations = {}
    print(f"\n📦 Parsing {len(stations_raw)} station entries...")
    for s in tqdm(stations_raw, desc="🏭 Stations", unit="station"):
        sid = str(s.get("stationID"))
        if not sid:
            continue
        stations[sid] = {
            "stationID": sid,
            "stationName": s.get("stationName"),
            "solarSystemID": s.get("solarSystemID"),
            "regionID": s.get("regionID"),
            "constellationID": s.get("constellationID"),
            "stationTypeID": s.get("stationTypeID")
        }
    return stations


# ─── Market ────────────────────────────────────────────────

def extract_market_menu(need_item_types=False):
    market_groups = load_yaml(MARKET_GROUPS_PATH) or {}
    types = load_yaml(TYPES_PATH) if need_item_types else {}

    group_data = {}
    children_map = {}

    print(f"\n🧩 Processing {len(market_groups)} market groups...")
    for gid, group in tqdm(market_groups.items(), desc="Market Groups", unit="group"):
        name = group.get("nameID", {}).get("en")
        if not name:
            continue
        group_data[gid] = {
            "name": name,
            "_info": {
                "marketGroupID": str(gid),
                "iconID": str(group.get("iconID", "")),
                "hasTypes": str(group.get("hasTypes", 0))
            },
            "items": [],
            "children": []
        }
        parent = group.get("parentGroupID")
        if parent is not None:
            children_map.setdefault(parent, []).append(gid)

    if need_item_types and types:
        print(f"\n🔍 Scanning {len(types)} item types...")
        for tid, t in tqdm(types.items(), desc="Item Types", unit="type"):
            if not t.get("published") or "marketGroupID" not in t:
                continue
            gid = t["marketGroupID"]
            if gid in group_data:
                group_data[gid]["items"].append({
                    "typeID": str(tid),
                    "typeName": t["name"].get("en", ""),
                    "iconID": str(t.get("iconID", "")),
                    "volume": t.get("volume", 0),
                    "mass": t.get("mass", 0),
                    "published": True
                })

    def build_group(gid):
        g = group_data[gid]
        group_name = g["name"]
        node = {group_name: {"_info": g["_info"]}}
        if g.get("items"):
            node[group_name]["items"] = sorted(
                g["items"], key=lambda x: x["typeName"].lower())
        for child_id in sorted(children_map.get(gid, []), key=lambda cid: group_data[cid]["name"].lower()):
            node[group_name].update(build_group(child_id))
        return node

    market_menu = {}
    for gid in sorted([g for g in group_data if market_groups.get(g, {}).get("parentGroupID") is None],
                      key=lambda g: group_data[g]["name"].lower()):
        market_menu.update(build_group(gid))

    return market_menu, market_groups


# ─── Icon Downloads ───────────────────────────────────────

def download_type_icons(market_menu):
    os.makedirs(TYPE_ICON_DIR, exist_ok=True)
    type_ids = set()

    def collect_types(node):
        for section in node.values():
            for item in section.get("items", []):
                type_ids.add(item["typeID"])
            for k, v in section.items():
                if isinstance(v, dict):
                    collect_types({k: v})

    collect_types(market_menu)
    print(f"\n⬇️ Downloading {len(type_ids)} type icons...")
    for tid in tqdm(sorted(type_ids), desc="Type Icons", unit="icon"):
        url = f"https://images.evetech.net/types/{tid}/icon"
        try:
            r = requests.get(url, timeout=5)
            if r.ok:
                with open(os.path.join(TYPE_ICON_DIR, f"{tid}.png"), "wb") as f:
                    f.write(r.content)
        except Exception as e:
            print(f"⚠️ Error downloading type {tid}: {e}")


def copy_group_icons(market_groups, icon_ids_map):
    """
    Copy 32-resolution group icons using iconFile reference from iconIDs.yaml.
    """
    os.makedirs(GROUP_ICON_DIR, exist_ok=True)
    copied = 0
    missing_icons = []

    print(f"\n📂 Copying 32x32 group icons...")
    for gid, group in tqdm(market_groups.items(), desc="Group Icons", unit="group"):
        icon_id = group.get("iconID")
        if not icon_id:
            continue
        icon_file = icon_ids_map.get(icon_id)
        if not icon_file:
            missing_icons.append(icon_id)
            continue

        original_filename = os.path.basename(icon_file)
        if not original_filename:
            continue

        # Substitute '64' with '32' to target 32px icons
        filename_32 = original_filename.replace("64", "32")
        src_path = os.path.join(SDE_ICONS_PATH, filename_32)
        dst_path = os.path.join(GROUP_ICON_DIR, f"{gid}.png")

        if not os.path.exists(src_path):
            print(f"⚠️ Missing 32px icon file: {src_path}")
            continue
        try:
            shutil.copyfile(src_path, dst_path)
            copied += 1
        except Exception as e:
            print(f"⚠️ Error copying icon {filename_32}: {e}")

    print(f"✅ Copied {copied} 32x32 group icons.")
    if missing_icons:
        print(f"⚠️ Missing iconIDs in iconIDs.yaml: {set(missing_icons)}")


def load_icon_ids():
    """
    Load iconIDs.yaml and return a dict mapping iconID (int) -> iconFile (string).
    """
    icon_ids_data = load_yaml(ICON_IDS_PATH) or {}
    icon_map = {}
    for icon_id_str, info in icon_ids_data.items():
        try:
            icon_id = int(icon_id_str)
            icon_file = info.get("iconFile")
            if icon_file:
                icon_map[icon_id] = icon_file
        except Exception:
            continue
    return icon_map


# ─── Main Menu ─────────────────────────────────────────────

def main():
    print("\n🛠 EVE Market Data Extractor\n")

    stations_choice = normalize_yes_no(
        input("🔧 Build Station Menu? (yes/no): "))
    market_choice = normalize_yes_no(input("🔧 Build Market Menu? (yes/no): "))
    icons_choice = normalize_yes_no(input("🎨 Download Icons? (yes/no): "))

    if stations_choice is None or market_choice is None or icons_choice is None:
        print("⚠️ Invalid input. Please answer with yes, y, no, or n.")
        return

    icon_mode = None
    if icons_choice:
        print("\n🎯 Choose icon type:")
        print("  1 — All icons (type + group)")
        print("  2 — Only type icons")
        print("  3 — Only group icons")
        icon_mode = input("Enter your choice [1–3]: ").strip()

    if stations_choice:
        stations = extract_stations()
        write_json("stations.json", stations)

    need_type_icons = icons_choice and icon_mode in ("1", "2")
    need_item_types = market_choice or need_type_icons

    market_menu, market_groups = None, None
    if market_choice or icons_choice:
        market_menu, market_groups = extract_market_menu(
            need_item_types=need_item_types)

    if market_choice:
        write_json("marketMenu.json", market_menu)

    if icons_choice and icon_mode:
        icon_ids_map = {}
        if icon_mode in ("1", "3"):
            icon_ids_map = load_icon_ids()

        if icon_mode == "1":
            download_type_icons(market_menu)
            copy_group_icons(market_groups, icon_ids_map)
        elif icon_mode == "2":
            download_type_icons(market_menu)
        elif icon_mode == "3":
            copy_group_icons(market_groups, icon_ids_map)
        else:
            print("⚠️ Invalid icon mode. No icons downloaded.")


if __name__ == "__main__":
    main()
