import os
import yaml
import json
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import threading

# ─── Paths ────────────────────────────────────────────────
SDE_ROOT = "sde"
UNIVERSE_ROOT = os.path.join(SDE_ROOT, "universe")
STATIONS_PATH = os.path.join(SDE_ROOT, "bsd", "staStations.yaml")
TYPES_PATH = os.path.join(SDE_ROOT, "fsd", "types.yaml")
TYPE_MATERIALS_PATH = os.path.join(SDE_ROOT, "fsd", "typeMaterials.yaml")
MARKET_GROUPS_PATH = os.path.join(SDE_ROOT, "fsd", "marketGroups.yaml")
ICON_IDS_PATH = os.path.join(SDE_ROOT, "fsd", "iconIDs.yaml")
GROUPS_PATH = os.path.join(SDE_ROOT, "fsd", "groups.yaml")

PLEX_TYPE_ID = 44992
PLEX_REGION_ID = 19000001
ASTEROID_CATEGORY_ID = 25
ICE_CATEGORY_ID = 87
GAS_GROUP_ID = 883  # "Harvestable Clouds"
GAS_CATEGORY_ID = 49  # Gas category
MOON_ORE_GROUP_IDS = {1920, 1921, 1922, 1923}  # All moon ore groups

# Common compressed ore keywords to filter out
COMPRESSED_KEYWORDS = ["compressed", "compact"]

# ─── Utilities ─────────────────────────────────────────────


def extract_all_refined_type_ids_and_items(type_materials, types):
    """Build set of all materialTypeIDs used in reprocessing and collect their info"""
    refined_type_ids = set()
    refined_items = []

    for entry in type_materials.values():
        for material in entry.get("materials", []):
            mtid = material["materialTypeID"]
            refined_type_ids.add(mtid)

    for tid in sorted(refined_type_ids):
        tdata = types.get(tid)
        if not tdata:
            continue
        refined_items.append({
            "typeID": tid,
            "name": tdata.get("name", {}).get("en", "Unknown"),
            "volume": tdata.get("volume", 1.0)
        })

    return refined_type_ids, refined_items


def load_yaml(path):
    if not os.path.exists(path):
        print(f"⚠️ Missing: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml_parallel(paths):
    """Load multiple YAML files in parallel using threads"""
    results = {}
    lock = threading.Lock()

    def load_single(path):
        data = load_yaml(path)
        with lock:
            results[path] = data

    # Use ThreadPoolExecutor for I/O bound operations
    with ThreadPoolExecutor(max_workers=min(8, len(paths))) as executor:
        executor.map(load_single, paths)

    return results


def write_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"💾 Exported: {filename}")

# ─── Station Extraction ────────────────────────────────────


def extract_stations():
    raw = load_yaml(STATIONS_PATH)
    stations = {}
    for s in raw:
        sid = str(s.get("stationID", ""))
        if sid:
            stations[sid] = s
    return stations

# This function is no longer needed since we're not filtering by NPC corps
# All stations in staStations.yaml are NPC stations

# ─── Simplified Location Extraction ─────────────────────────


def extract_locations():
    stations = extract_stations()

    print("\n🧭 Extracting universe locations (using directory names)...")
    print(f"📊 Found {len(stations)} NPC stations to process")

    # Group stations by region, constellation, system
    region_structure = {}

    # First pass: organize stations by their location hierarchy
    for station_id, station_data in stations.items():
        region_id = station_data.get("regionID")
        constellation_id = station_data.get("constellationID")
        system_id = station_data.get("solarSystemID")

        if not all([region_id, constellation_id, system_id]):
            continue

        # Initialize nested structure
        if region_id not in region_structure:
            region_structure[region_id] = {
                "regionID": region_id,
                "constellations": {}
            }

        if constellation_id not in region_structure[region_id]["constellations"]:
            region_structure[region_id]["constellations"][constellation_id] = {
                "constellationID": constellation_id,
                "systems": {}
            }

        if system_id not in region_structure[region_id]["constellations"][constellation_id]["systems"]:
            region_structure[region_id]["constellations"][constellation_id]["systems"][system_id] = {
                "solarSystemID": system_id,
                "stations": {}
            }

        # Add station to the system
        region_structure[region_id]["constellations"][constellation_id]["systems"][system_id]["stations"][station_id] = station_data

    print(f"📍 Found {len(region_structure)} regions with stations")

    # Build a map of what we need to look up
    regions_to_lookup = set(region_structure.keys())

    print(
        f"🔍 Looking up directory names for {len(regions_to_lookup)} regions with stations...")
    print("🔍 Also scanning for PLEX region in hidden directory...")

    locations = {}

    # Process each region directory in the universe (including hidden PLEX region)
    for dirpath, _, filenames in os.walk(UNIVERSE_ROOT):
        if "region.yaml" not in filenames:
            continue

        ryaml = os.path.join(dirpath, "region.yaml")
        rdata = load_yaml(ryaml)
        region_id = rdata.get("regionID")

        # Check if this is a region we need (has stations) OR if it's the PLEX region
        is_plex_region = (region_id == PLEX_REGION_ID)
        has_stations = (region_id in regions_to_lookup)

        if not has_stations and not is_plex_region:
            continue

        # Extract region name from directory path
        # Path structure: .../universe/eve/REGION_NAME/... or .../universe/hidden/REGION_NAME/...
        path_parts = dirpath.split(os.sep)
        region_name = path_parts[-1]  # Last part is the region directory name

        print(
            f"⚙️  Processing: {region_name} (ID: {region_id})...", end=" ", flush=True)

        # Start building the region object
        region_obj = {"regionID": region_id}

        # Get constellation folders
        constellation_folders = [d for d in os.listdir(dirpath)
                                 if os.path.isdir(os.path.join(dirpath, d))]

        station_count = 0

        for const_folder in constellation_folders:
            constellation_path = os.path.join(dirpath, const_folder)
            cyaml = os.path.join(constellation_path, "constellation.yaml")

            if not os.path.exists(cyaml):
                continue

            cdata = load_yaml(cyaml)
            constellation_id = cdata.get("constellationID")
            constellation_name = const_folder  # Use directory name

            # Check if this constellation has stations
            has_stations = (region_id in region_structure and
                            constellation_id in region_structure[region_id]["constellations"])

            # For PLEX region, include all constellations even without stations
            if not has_stations and not is_plex_region:
                continue

            constellation_obj = {"constellationID": constellation_id}

            # Process system folders in this constellation
            system_folders = [d for d in os.listdir(constellation_path)
                              if os.path.isdir(os.path.join(constellation_path, d))]

            for sys_folder in system_folders:
                system_path = os.path.join(constellation_path, sys_folder)
                syaml = os.path.join(system_path, "solarsystem.yaml")

                if not os.path.exists(syaml):
                    continue

                sdata = load_yaml(syaml)
                system_id = sdata.get("solarSystemID")
                system_name = sys_folder  # Use directory name

                # Check if this system has stations or is in PLEX region
                has_system_stations = (has_stations and
                                       system_id in region_structure[region_id]["constellations"][constellation_id]["systems"])

                # For PLEX region, include all systems even without stations
                if not has_system_stations and not is_plex_region:
                    continue

                system_obj = {
                    "solarSystemID": system_id,
                    "solarSystemNameID": sdata.get("solarSystemNameID"),
                    "security": sdata.get("security"),
                    "stations": {}
                }

                # Add stations if this system has them (PLEX region won't have stations)
                if has_system_stations:
                    system_stations = region_structure[region_id]["constellations"][
                        constellation_id]["systems"][system_id]["stations"]
                    system_obj["stations"] = system_stations
                    station_count += len(system_stations)

                # Use system directory name as key
                constellation_obj[system_name] = system_obj

            # Only add constellation if it has systems, use constellation directory name as key
            # For PLEX region, include all constellations even without stations
            if len(constellation_obj) > 1:  # More than just constellationID
                region_obj[constellation_name] = constellation_obj

        # Add region if it has content or is PLEX region, use region directory name as key
        if len(region_obj) > 1 or is_plex_region:
            locations[region_name] = region_obj
            if is_plex_region:
                print("✅ (PLEX region - no stations)")
            else:
                print(f"✅ ({station_count} stations)")
        else:
            print("⏭️ (no content)")

    print(f"\n💾 Writing locations.json...")
    write_json("locations.json", locations)

# ─── PLEX Market Lookup ───────────────────────────────────


def get_plex_location():
    try:
        with open("locations.json", "r", encoding="utf-8") as f:
            locations = json.load(f)

        for region_name, region_data in locations.items():
            if region_data.get("regionID") == PLEX_REGION_ID:
                for constellation_name, const_data in region_data.items():
                    if not isinstance(const_data, dict) or "constellationID" not in const_data:
                        continue
                    for system_name, sys_data in const_data.items():
                        if not isinstance(sys_data, dict) or "solarSystemID" not in sys_data:
                            continue
                        # Return the first system in the PLEX region as the PLEX location
                        return {
                            "region": region_name,
                            "regionID": region_data.get("regionID"),
                            "constellation": constellation_name,
                            "constellationID": const_data.get("constellationID"),
                            "system": system_name,
                            "systemID": sys_data.get("solarSystemID"),
                            "security": sys_data.get("security")
                        }
    except Exception as e:
        print(f"⚠️ Failed to find PLEX location: {e}")
    return {}

# ─── Market Structure Extraction ───────────────────────────


def extract_market():
    print("\n🛒 Building market.json from types.yaml, marketGroups.yaml, iconIDs.yaml...")

    types = load_yaml(TYPES_PATH)
    market_groups = load_yaml(MARKET_GROUPS_PATH)
    icon_ids = load_yaml(ICON_IDS_PATH)

    # Normalize keys
    types = {int(k): v for k, v in types.items()}
    market_groups = {int(k): v for k, v in market_groups.items()}
    icon_ids = {int(k): v for k, v in icon_ids.items()}

    from collections import defaultdict

    # Step 1: Create mapping of iconID to iconFile filename (not full path)
    icon_lookup = {
        icon_id: icon_data.get("iconFile", "").split("/")[-1]
        for icon_id, icon_data in icon_ids.items()
    }

    # Step 2: Collect types by marketGroupID
    types_by_mgid = defaultdict(list)
    for type_id, type_data in types.items():
        mgid = type_data.get("marketGroupID")
        if mgid is not None and mgid in market_groups:
            types_by_mgid[mgid].append({
                "typeID": str(type_id),
                "typeName": type_data.get("name", {}).get("en", "Unknown"),
                "iconID": str(type_data.get("iconID", "")),
                "iconFile": icon_lookup.get(type_data.get("iconID", 0), ""),
                "volume": type_data.get("volume", 0.0),
                "mass": type_data.get("mass", 0.0),
                "published": type_data.get("published", False)
            })

    # Step 3: Build parent->children map
    children_map = defaultdict(list)
    for mgid, mgdata in market_groups.items():
        parent_id = mgdata.get("parentGroupID")
        children_map[parent_id].append(mgid)

    # Step 4: Recursively build the market group tree
    def build_node(mgid):
        mgdata = market_groups[mgid]
        group_name = mgdata.get("nameID", {}).get("en", f"Unknown_{mgid}")
        has_types = mgdata.get("hasTypes", False)
        icon_id = mgdata.get("iconID", 0)

        node = {}

        info = {
            "marketGroupID": str(mgid),
            "iconID": str(icon_id),
            "iconFile": icon_lookup.get(icon_id, ""),
            "hasTypes": "True" if has_types else "False"
        }

        if has_types:
            # Leaf group with types
            items = sorted(types_by_mgid.get(mgid, []),
                           key=lambda x: x["typeName"])
            node["_info"] = info
            node["items"] = items
        else:
            # Parent group: build children recursively
            children = children_map.get(mgid, [])
            child_nodes = {}
            for child_id in sorted(children, key=lambda cid: market_groups[cid].get("nameID", {}).get("en", f"Unknown_{cid}")):
                child_node = build_node(child_id)
                child_nodes.update(child_node)
            node = dict(sorted(child_nodes.items()))
            node["_info"] = info

        return {group_name: node}

    # Step 5: Build top-level market tree
    market_tree = {}
    for root_id in sorted(children_map[None], key=lambda rid: market_groups[rid].get("nameID", {}).get("en", f"Unknown_{rid}")):
        market_tree.update(build_node(root_id))

    # Step 6: Write JSON
    write_json("market.json", market_tree)


# ─── Ores, Ice & Moon Ore Extraction ──────────────────────


def is_compressed_ore(name):
    """Check if an ore name indicates it's compressed"""
    name_lower = name.lower()
    return any(keyword in name_lower for keyword in COMPRESSED_KEYWORDS)


def group_ore_subtypes(items, item_type):
    """Group ore/ice/moon ore subtypes by base name with proper nesting"""
    subtypes = {}

    # Define prefixes for each type
    if item_type == "ore":
        prefixes = ["concentrated ", "dense ", "solid ", "thick ", "prismatic ",
                    "luminous ", "gleaming ", "condensed ", "massive ", "smooth "]
    elif item_type == "ice":
        prefixes = ["enriched ", "thick ",
                    "pristine ", "smooth ", "crystalline "]
    elif item_type == "moon_ore":
        prefixes = ["concentrated ", "dense ", "solid ", "thick ", "prismatic ",
                    "luminous ", "gleaming ", "condensed ", "massive ", "smooth "]
    else:
        prefixes = []

    # First pass: identify all base types and their variants
    base_variants = {}

    for item in items:
        name = item["name"]
        name_lower = name.lower()
        base_name = None
        is_base = True

        # Try to identify base name by removing common prefixes
        for prefix in prefixes:
            if name_lower.startswith(prefix):
                base_name = name[len(prefix):].strip()
                is_base = False
                break

        # If no prefix found, this is the base item
        if base_name is None:
            base_name = name
            is_base = True

        if base_name not in base_variants:
            base_variants[base_name] = {
                "base": None,
                "variants": []
            }

        if is_base:
            base_variants[base_name]["base"] = item
        else:
            base_variants[base_name]["variants"].append(item)

    # Second pass: build nested structure
    for base_name, data in base_variants.items():
        base_item = data["base"]
        variants = data["variants"]

        # Skip if we don't have a base item (orphaned variants)
        if base_item is None:
            continue

        # Create the nested structure
        subtypes[base_name] = {
            "typeID": base_item["typeID"],
            "name": base_item["name"],
            "volume": base_item["volume"],
            "group": base_item["group"],
            "refined_output": base_item["refined_output"]
        }

        # Add variants as nested properties
        for variant in sorted(variants, key=lambda x: x["name"]):
            variant_name = variant["name"]
            subtypes[base_name][variant_name] = {
                "typeID": variant["typeID"],
                "name": variant["name"],
                "volume": variant["volume"],
                "refined_output": variant["refined_output"]
            }

    return dict(sorted(subtypes.items()))


def extract_ores_ice_and_moon_ores():
    print("\n⛏ Extracting ores, ice, moon ores, minerals, and gas...")

    types = load_yaml(TYPES_PATH)
    materials = load_yaml(TYPE_MATERIALS_PATH)
    groups = load_yaml(GROUPS_PATH)

    # Refined material info (needed early)
    all_refined_type_ids, refined_items = extract_all_refined_type_ids_and_items(
        materials, types
    )

    # Define category IDs
    ASTEROID_CATEGORY_ID = 25
    ICE_CATEGORY_ID = 87
    GAS_CATEGORY_ID = 49

    # Identify ore, ice, gas, and moon ore group IDs
    ore_groups = {
        int(gid) for gid, g in groups.items()
        if g.get("categoryID") == ASTEROID_CATEGORY_ID
    }

    ice_groups = {
        int(gid) for gid, g in groups.items()
        if g.get("categoryID") == ICE_CATEGORY_ID and "ice" in g.get("name", {}).get("en", "").lower()
    }

    gas_groups = {
        int(gid) for gid, g in groups.items()
        if g.get("categoryID") == GAS_CATEGORY_ID
    }

    moon_ore_groups = MOON_ORE_GROUP_IDS  # Static/global

    print(f"🔍 Found {len(ore_groups)} asteroid ore groups")
    print(f"🧊 Found {len(ice_groups)} ice groups")
    print(f"🌙 Found {len(moon_ore_groups)} moon ore groups")
    print(f"☁️ Found {len(gas_groups)} gas groups")

    # Initialize categorized collections
    ores, ice_items, moon_ores, minerals, gas_clouds = [], [], [], [], []

    # Process all published item types
    for tid, tdata in types.items():
        if not tdata.get("published", False):
            continue

        type_id = int(tid)
        group_id = tdata.get("groupID")
        name = tdata.get("name", {}).get("en", "")
        volume = tdata.get("volume", 1.0)
        group_name = groups.get(group_id, {}).get(
            "name", {}).get("en", "Unknown")

        # Get reprocessing materials (if any)
        refined = [
            {"typeID": m["materialTypeID"], "quantity": m["quantity"]}
            for m in materials.get(type_id, {}).get("materials", [])
        ]

        entry = {
            "typeID": type_id,
            "name": name,
            "volume": volume,
            "group": group_name,
            "refined_output": refined
        }

        # Categorize entry
        if group_id in moon_ore_groups and not is_compressed_ore(name):
            moon_ores.append(entry)
        elif group_id in ore_groups and not is_compressed_ore(name):
            ores.append(entry)
        elif group_id in ice_groups and not is_compressed_ore(name):
            ice_items.append(entry)
        elif type_id in all_refined_type_ids:
            minerals.append(entry)
        elif group_id in gas_groups:
            gas_clouds.append(entry)

    # Group into subtypes
    ore_subtypes = group_ore_subtypes(ores, "ore")
    ice_subtypes = group_ore_subtypes(ice_items, "ice")
    moon_ore_subtypes = group_ore_subtypes(moon_ores, "moon_ore")

    print(f"⛏ Found {len(ores)} raw ore types")
    print(f"🧊 Found {len(ice_items)} ice types")
    print(f"🌙 Found {len(moon_ores)} moon ore types")
    print(f"💎 Found {len(minerals)} mineral types")
    print(f"☁️ Found {len(gas_clouds)} gas types")

    # Output JSON
    write_json("ores.json", {
        "ores": ores,
        "minerals": minerals,
        "ore_subtypes": ore_subtypes
    })

    write_json("ice.json", {
        "ice": ice_items,
        "ice_subtypes": ice_subtypes
    })

    write_json("moon_ore.json", {
        "moon_ores": moon_ores,
        "moon_ore_subtypes": moon_ore_subtypes
    })

    write_json("gas_clouds.json", {
        "gas_clouds": gas_clouds
    })

    write_json("refined_outputs.json", refined_items)


# ─── Main CLI ──────────────────────────────────────────────


def main():
    print("\n🛠 EVE Data Extractor")
    print("1) Build Market")
    print("2) Build Locations")
    print("3) Build Both Market & Locations")
    print("4) Build Ores, Ice & Moon Ores")
    print("5) Build All")

    choice = input("Enter choice [1–5]: ").strip()
    if choice not in ("1", "2", "3", "4", "5"):
        print("⚠️ Invalid selection.")
        return

    if choice in ("2", "3", "5"):
        extract_locations()

    if choice in ("1", "3", "5"):
        extract_market()

    if choice in ("4", "5"):
        extract_ores_ice_and_moon_ores()

    print("\n✅ Complete!")


if __name__ == "__main__":
    main()
