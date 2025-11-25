#!/usr/bin/env python3
"""
SUMO Network Generator for Chepauk Area, Chennai

This script downloads OpenStreetMap data for the Chepauk area and converts it
to SUMO network format. The area includes:
- University of Madras (Chepauk campus)
- M.A. Chidambaram Cricket Stadium
- Busy junctions (Anna Salai / Wallajah Road / Kamarajar Salai)

Bounding box coordinates (WGS84):
- South: 13.0580
- North: 13.0720
- West: 80.2720
- East: 80.2880
"""

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# Bounding box for Chepauk area (tight perimeter)
# Covers: University of Madras, MA Chidambaram Stadium, nearby junctions
BBOX = {
    "south": 13.0580,
    "north": 13.0720,
    "west": 80.2720,
    "east": 80.2880
}

# Output files
OSM_FILE = "chepauk.osm"
NET_FILE = "chepauk.net.xml"
POLY_FILE = "chepauk.poly.xml"
ROU_FILE = "chepauk.rou.xml"
CFG_FILE = "chepauk.sumocfg"

def get_sumo_home():
    """Get SUMO_HOME environment variable or try common locations."""
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        return sumo_home

    # Try common locations
    common_paths = [
        "/usr/share/sumo",
        "/usr/local/share/sumo",
        "/opt/homebrew/share/sumo",
        "C:\\Program Files (x86)\\Eclipse\\Sumo",
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    print("ERROR: SUMO_HOME not set and SUMO not found in common locations.")
    print("Please set SUMO_HOME environment variable.")
    sys.exit(1)

def download_osm_data():
    """Download OpenStreetMap data for the Chepauk area."""
    print(f"Downloading OSM data for Chepauk area...")
    print(f"  Bounding box: {BBOX}")

    # Overpass API query
    overpass_url = "https://overpass-api.de/api/map"
    bbox_str = f"{BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']}"
    url = f"{overpass_url}?bbox={bbox_str}"

    try:
        print(f"  Fetching from: {url}")
        urllib.request.urlretrieve(url, OSM_FILE)
        print(f"  Saved to: {OSM_FILE}")

        # Check file size
        size = os.path.getsize(OSM_FILE)
        print(f"  File size: {size / 1024:.1f} KB")

        if size < 1000:
            print("WARNING: OSM file is very small. Network might be empty.")

    except Exception as e:
        print(f"ERROR downloading OSM data: {e}")
        print("Creating a synthetic network instead...")
        create_synthetic_network()
        return False

    return True

def create_synthetic_network():
    """Create a synthetic network if OSM download fails."""
    print("Creating synthetic Chepauk network...")

    # Create a simple grid network representing the area
    node_file = "chepauk.nod.xml"
    edge_file = "chepauk.edg.xml"

    # Nodes representing key locations
    nodes_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <!-- University of Madras area -->
    <node id="uni_north" x="0" y="500" type="traffic_light"/>
    <node id="uni_south" x="0" y="0" type="traffic_light"/>
    <node id="uni_east" x="200" y="250" type="traffic_light"/>
    <node id="uni_west" x="-200" y="250" type="priority"/>

    <!-- Stadium area -->
    <node id="stadium_north" x="400" y="400" type="traffic_light"/>
    <node id="stadium_south" x="400" y="100" type="traffic_light"/>
    <node id="stadium_east" x="600" y="250" type="priority"/>
    <node id="stadium_west" x="200" y="250" type="traffic_light"/>

    <!-- Main junction (Anna Salai / Wallajah Road) -->
    <node id="junction_main" x="200" y="250" type="traffic_light"/>
    <node id="junction_north" x="200" y="600" type="priority"/>
    <node id="junction_south" x="200" y="-100" type="priority"/>
    <node id="junction_east" x="700" y="250" type="priority"/>
    <node id="junction_west" x="-300" y="250" type="priority"/>

    <!-- Additional nodes for realistic network -->
    <node id="kamarajar_north" x="-100" y="600" type="priority"/>
    <node id="kamarajar_south" x="-100" y="-100" type="priority"/>
    <node id="wallajah_east" x="600" y="500" type="priority"/>
    <node id="wallajah_west" x="-200" y="500" type="priority"/>
</nodes>
'''

    # Edges representing roads
    edges_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <!-- Anna Salai (Main arterial road) - North-South -->
    <edge id="anna_salai_nb" from="junction_south" to="junction_main" numLanes="3" speed="13.89"/>
    <edge id="anna_salai_nb2" from="junction_main" to="junction_north" numLanes="3" speed="13.89"/>
    <edge id="anna_salai_sb" from="junction_north" to="junction_main" numLanes="3" speed="13.89"/>
    <edge id="anna_salai_sb2" from="junction_main" to="junction_south" numLanes="3" speed="13.89"/>

    <!-- Wallajah Road - East-West -->
    <edge id="wallajah_eb" from="junction_west" to="junction_main" numLanes="2" speed="11.11"/>
    <edge id="wallajah_eb2" from="junction_main" to="junction_east" numLanes="2" speed="11.11"/>
    <edge id="wallajah_wb" from="junction_east" to="junction_main" numLanes="2" speed="11.11"/>
    <edge id="wallajah_wb2" from="junction_main" to="junction_west" numLanes="2" speed="11.11"/>

    <!-- University roads -->
    <edge id="uni_entrance_in" from="junction_main" to="uni_east" numLanes="2" speed="8.33"/>
    <edge id="uni_entrance_out" from="uni_east" to="junction_main" numLanes="2" speed="8.33"/>
    <edge id="uni_internal_ns" from="uni_north" to="uni_south" numLanes="1" speed="5.56"/>
    <edge id="uni_internal_sn" from="uni_south" to="uni_north" numLanes="1" speed="5.56"/>
    <edge id="uni_north_conn" from="uni_north" to="junction_north" numLanes="1" speed="8.33"/>
    <edge id="uni_north_conn_rev" from="junction_north" to="uni_north" numLanes="1" speed="8.33"/>

    <!-- Stadium roads -->
    <edge id="stadium_approach_n" from="junction_north" to="stadium_north" numLanes="2" speed="11.11"/>
    <edge id="stadium_approach_n_rev" from="stadium_north" to="junction_north" numLanes="2" speed="11.11"/>
    <edge id="stadium_exit_s" from="stadium_south" to="junction_main" numLanes="2" speed="11.11"/>
    <edge id="stadium_exit_s_rev" from="junction_main" to="stadium_south" numLanes="2" speed="11.11"/>
    <edge id="stadium_internal" from="stadium_north" to="stadium_south" numLanes="2" speed="5.56"/>
    <edge id="stadium_internal_rev" from="stadium_south" to="stadium_north" numLanes="2" speed="5.56"/>
    <edge id="stadium_east_exit" from="stadium_south" to="junction_east" numLanes="2" speed="11.11"/>
    <edge id="stadium_east_entry" from="junction_east" to="stadium_south" numLanes="2" speed="11.11"/>

    <!-- Kamarajar Salai -->
    <edge id="kamarajar_nb" from="kamarajar_south" to="uni_south" numLanes="2" speed="11.11"/>
    <edge id="kamarajar_nb2" from="uni_south" to="kamarajar_north" numLanes="2" speed="11.11"/>
    <edge id="kamarajar_sb" from="kamarajar_north" to="uni_north" numLanes="2" speed="11.11"/>
    <edge id="kamarajar_sb2" from="uni_north" to="kamarajar_south" numLanes="2" speed="11.11"/>

    <!-- Connecting roads -->
    <edge id="connector_uw" from="uni_west" to="junction_west" numLanes="1" speed="8.33"/>
    <edge id="connector_uw_rev" from="junction_west" to="uni_west" numLanes="1" speed="8.33"/>
</edges>
'''

    with open(node_file, 'w') as f:
        f.write(nodes_xml)

    with open(edge_file, 'w') as f:
        f.write(edges_xml)

    # Run netconvert
    sumo_home = get_sumo_home()
    netconvert = os.path.join(sumo_home, "bin", "netconvert")
    if not os.path.exists(netconvert):
        netconvert = "netconvert"  # Try system PATH

    cmd = [
        netconvert,
        "--node-files", node_file,
        "--edge-files", edge_file,
        "--output-file", NET_FILE,
        "--tls.guess", "true",
        "--tls.default-type", "actuated"
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Clean up temp files
    os.remove(node_file)
    os.remove(edge_file)

    print(f"Synthetic network created: {NET_FILE}")

def convert_osm_to_sumo():
    """Convert OSM data to SUMO network format."""
    print("Converting OSM to SUMO network...")

    sumo_home = get_sumo_home()
    netconvert = os.path.join(sumo_home, "bin", "netconvert")
    if not os.path.exists(netconvert):
        netconvert = "netconvert"  # Try system PATH

    cmd = [
        netconvert,
        "--osm-files", OSM_FILE,
        "--output-file", NET_FILE,
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        "--junctions.join", "true",
        "--tls.guess", "true",
        "--tls.default-type", "actuated",
        "--tls.join", "true",
        "--sidewalks.guess", "true",
        "--crossings.guess", "true",
        "--osm.stop-output.length", "20",
        "--osm.turn-lanes", "true"
    ]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"netconvert warning/error: {result.stderr}")
        print(f"Network created: {NET_FILE}")
    except FileNotFoundError:
        print("ERROR: netconvert not found. Creating synthetic network instead.")
        create_synthetic_network()

def create_polygon_file():
    """Create polygon file marking key regions."""
    print("Creating polygon file for regions...")

    poly_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<additional xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/additional_file.xsd">
    <!-- University of Madras region -->
    <poly id="university" type="university" color="0,100,0,100" fill="1" layer="0"
          shape="-250,0 -250,550 50,550 50,0 -250,0"/>

    <!-- M.A. Chidambaram Stadium region -->
    <poly id="stadium" type="stadium" color="100,0,0,100" fill="1" layer="0"
          shape="300,50 300,450 650,450 650,50 300,50"/>

    <!-- Main junction region (Anna Salai / Wallajah intersection) -->
    <poly id="busy_junction" type="junction" color="0,0,100,100" fill="1" layer="0"
          shape="100,150 100,350 300,350 300,150 100,150"/>

    <!-- POI markers -->
    <poi id="poi_university_main_gate" type="gate" color="0,200,0" layer="10" x="0" y="250"/>
    <poi id="poi_stadium_main_entrance" type="entrance" color="200,0,0" layer="10" x="400" y="250"/>
    <poi id="poi_main_junction" type="junction" color="0,0,200" layer="10" x="200" y="250"/>

    <!-- Additional landmarks -->
    <poi id="poi_senate_house" type="landmark" color="0,150,0" layer="10" x="-100" y="300"/>
    <poi id="poi_chepauk_palace" type="landmark" color="150,100,0" layer="10" x="100" y="400"/>
</additional>
'''

    with open(POLY_FILE, 'w') as f:
        f.write(poly_xml)

    print(f"Polygon file created: {POLY_FILE}")

def create_routes_file():
    """Create routes file with traffic demand patterns."""
    print("Creating routes file with traffic demand...")

    # Get edge IDs - we'll use the ones from our synthetic network
    # In a real scenario, you'd extract these from the generated network

    rou_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">

    <!-- Vehicle types -->
    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="4.5" maxSpeed="50" guiShape="passenger"/>
    <vType id="bus" accel="1.2" decel="4.0" sigma="0.5" length="12" maxSpeed="30" guiShape="bus"/>
    <vType id="motorcycle" accel="4.0" decel="5.0" sigma="0.5" length="2.2" maxSpeed="40" guiShape="motorcycle"/>
    <vType id="auto" accel="2.0" decel="4.0" sigma="0.5" length="3.5" maxSpeed="35" guiShape="passenger/sedan"/>

    <!-- ============================================== -->
    <!-- UNIVERSITY TRAFFIC PATTERNS -->
    <!-- ============================================== -->

    <!-- Morning inflow to University (8:00 - 9:30) = 28800s - 34200s -->
    <flow id="uni_morning_in_1" type="car"
          from="anna_salai_nb" to="uni_entrance_in"
          begin="28800" end="34200" vehsPerHour="400"/>

    <flow id="uni_morning_in_2" type="car"
          from="wallajah_eb" to="uni_entrance_in"
          begin="28800" end="34200" vehsPerHour="300"/>

    <flow id="uni_morning_in_3" type="motorcycle"
          from="anna_salai_nb" to="uni_entrance_in"
          begin="28800" end="34200" vehsPerHour="600"/>

    <flow id="uni_morning_bus" type="bus"
          from="anna_salai_nb" to="uni_north_conn_rev"
          begin="28800" end="34200" vehsPerHour="20"/>

    <!-- Afternoon/Evening outflow from University (16:00 - 18:00) = 57600s - 64800s -->
    <flow id="uni_evening_out_1" type="car"
          from="uni_entrance_out" to="anna_salai_sb2"
          begin="57600" end="64800" vehsPerHour="350"/>

    <flow id="uni_evening_out_2" type="car"
          from="uni_entrance_out" to="wallajah_wb2"
          begin="57600" end="64800" vehsPerHour="250"/>

    <flow id="uni_evening_out_3" type="motorcycle"
          from="uni_entrance_out" to="anna_salai_sb2"
          begin="57600" end="64800" vehsPerHour="500"/>

    <!-- ============================================== -->
    <!-- STADIUM EVENT TRAFFIC (Match at 14:00 = 50400s) -->
    <!-- ============================================== -->

    <!-- Pre-match inflow (12:00 - 14:00) = 43200s - 50400s -->
    <flow id="stadium_prematch_1" type="car"
          from="anna_salai_nb" to="stadium_exit_s_rev"
          begin="43200" end="50400" vehsPerHour="800"/>

    <flow id="stadium_prematch_2" type="car"
          from="wallajah_eb" to="stadium_exit_s_rev"
          begin="43200" end="50400" vehsPerHour="600"/>

    <flow id="stadium_prematch_3" type="car"
          from="anna_salai_sb" to="stadium_approach_n"
          begin="43200" end="50400" vehsPerHour="500"/>

    <flow id="stadium_prematch_auto" type="auto"
          from="wallajah_wb" to="stadium_east_entry"
          begin="43200" end="50400" vehsPerHour="400"/>

    <!-- Post-match outflow burst (17:00 - 18:30) = 61200s - 66600s -->
    <flow id="stadium_postmatch_1" type="car"
          from="stadium_exit_s" to="anna_salai_sb2"
          begin="61200" end="66600" vehsPerHour="1200"/>

    <flow id="stadium_postmatch_2" type="car"
          from="stadium_exit_s" to="wallajah_wb2"
          begin="61200" end="66600" vehsPerHour="800"/>

    <flow id="stadium_postmatch_3" type="car"
          from="stadium_approach_n_rev" to="anna_salai_sb"
          begin="61200" end="66600" vehsPerHour="600"/>

    <flow id="stadium_postmatch_4" type="auto"
          from="stadium_east_exit" to="wallajah_eb2"
          begin="61200" end="66600" vehsPerHour="500"/>

    <!-- ============================================== -->
    <!-- BACKGROUND THROUGH TRAFFIC (All day) -->
    <!-- ============================================== -->

    <!-- Anna Salai through traffic -->
    <flow id="through_ns_1" type="car"
          from="anna_salai_nb" to="anna_salai_nb2"
          begin="0" end="86400" vehsPerHour="600"/>

    <flow id="through_sn_1" type="car"
          from="anna_salai_sb" to="anna_salai_sb2"
          begin="0" end="86400" vehsPerHour="600"/>

    <!-- Wallajah Road through traffic -->
    <flow id="through_ew_1" type="car"
          from="wallajah_eb" to="wallajah_eb2"
          begin="0" end="86400" vehsPerHour="400"/>

    <flow id="through_we_1" type="car"
          from="wallajah_wb" to="wallajah_wb2"
          begin="0" end="86400" vehsPerHour="400"/>

    <!-- Cross traffic patterns -->
    <flow id="cross_1" type="car"
          from="anna_salai_nb" to="wallajah_eb2"
          begin="0" end="86400" vehsPerHour="200"/>

    <flow id="cross_2" type="car"
          from="wallajah_eb" to="anna_salai_nb2"
          begin="0" end="86400" vehsPerHour="200"/>

    <flow id="cross_3" type="motorcycle"
          from="anna_salai_sb" to="wallajah_wb2"
          begin="0" end="86400" vehsPerHour="300"/>

    <!-- Kamarajar Salai traffic -->
    <flow id="kamarajar_1" type="car"
          from="kamarajar_nb" to="kamarajar_nb2"
          begin="0" end="86400" vehsPerHour="300"/>

    <flow id="kamarajar_2" type="car"
          from="kamarajar_sb" to="kamarajar_sb2"
          begin="0" end="86400" vehsPerHour="300"/>

    <!-- ============================================== -->
    <!-- PEAK HOUR BOOSTS -->
    <!-- ============================================== -->

    <!-- Morning peak (8:00 - 10:00) -->
    <flow id="peak_morning_1" type="car"
          from="anna_salai_nb" to="anna_salai_nb2"
          begin="28800" end="36000" vehsPerHour="400"/>

    <flow id="peak_morning_2" type="motorcycle"
          from="wallajah_eb" to="wallajah_eb2"
          begin="28800" end="36000" vehsPerHour="500"/>

    <!-- Evening peak (17:00 - 19:00) -->
    <flow id="peak_evening_1" type="car"
          from="anna_salai_sb" to="anna_salai_sb2"
          begin="61200" end="68400" vehsPerHour="500"/>

    <flow id="peak_evening_2" type="motorcycle"
          from="wallajah_wb" to="wallajah_wb2"
          begin="61200" end="68400" vehsPerHour="600"/>

</routes>
'''

    with open(ROU_FILE, 'w') as f:
        f.write(rou_xml)

    print(f"Routes file created: {ROU_FILE}")

def create_sumo_config():
    """Create SUMO configuration file."""
    print("Creating SUMO configuration...")

    cfg_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{NET_FILE}"/>
        <route-files value="{ROU_FILE}"/>
        <additional-files value="{POLY_FILE}"/>
    </input>

    <time>
        <begin value="0"/>
        <end value="86400"/>  <!-- 24 hours in seconds -->
        <step-length value="1.0"/>
    </time>

    <processing>
        <ignore-route-errors value="true"/>
        <time-to-teleport value="300"/>
        <time-to-teleport.highways value="0"/>
    </processing>

    <routing>
        <device.rerouting.probability value="0.8"/>
        <device.rerouting.period value="60"/>
    </routing>

    <report>
        <verbose value="true"/>
        <no-step-log value="true"/>
    </report>

    <gui_only>
        <gui-settings-file value=""/>
        <start value="true"/>
    </gui_only>
</configuration>
'''

    with open(CFG_FILE, 'w') as f:
        f.write(cfg_xml)

    print(f"SUMO config created: {CFG_FILE}")

def main():
    """Main function to generate all SUMO files."""
    print("=" * 60)
    print("SUMO Network Generator for Chepauk Area, Chennai")
    print("=" * 60)

    # Change to simulation directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")

    # Check SUMO
    sumo_home = get_sumo_home()
    print(f"SUMO_HOME: {sumo_home}")

    # Try to download OSM data and convert
    if download_osm_data():
        convert_osm_to_sumo()

    # Create additional files
    create_polygon_file()
    create_routes_file()
    create_sumo_config()

    print("=" * 60)
    print("Network generation complete!")
    print("=" * 60)
    print(f"\nGenerated files:")
    print(f"  - {NET_FILE} (network)")
    print(f"  - {ROU_FILE} (routes/demand)")
    print(f"  - {POLY_FILE} (polygons/POIs)")
    print(f"  - {CFG_FILE} (configuration)")
    print(f"\nTo test in SUMO GUI, run:")
    print(f"  sumo-gui -c {CFG_FILE}")

if __name__ == "__main__":
    main()
