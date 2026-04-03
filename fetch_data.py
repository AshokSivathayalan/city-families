"""
Fetch twin/sister city data from Wikidata and build a sibling network.

Queries Wikidata for all twin city relationships (property P190),
pulls coordinates, builds a NetworkX graph, detects communities,
and exports everything as JSON for the map visualization.
"""

import csv
import io
import json
import urllib.request
import urllib.parse
from collections import defaultdict

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Skipping community detection.")
    print("Install with: pip install networkx")


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?city ?cityLabel ?twin ?twinLabel ?cityLat ?cityLon ?twinLat ?twinLon WHERE {
  ?city wdt:P190 ?twin.
  ?city p:P625/psv:P625 [
    wikibase:geoLatitude ?cityLat;
    wikibase:geoLongitude ?cityLon
  ].
  ?twin p:P625/psv:P625 [
    wikibase:geoLatitude ?twinLat;
    wikibase:geoLongitude ?twinLon
  ].
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def fetch_twin_cities():
    """Query Wikidata SPARQL endpoint for twin city pairs with coordinates."""
    print("Querying Wikidata for twin city relationships...")

    # Use POST + CSV format to avoid JSON encoding issues on large result sets
    post_data = urllib.parse.urlencode({
        "query": QUERY,
    }).encode("utf-8")

    req = urllib.request.Request(SPARQL_ENDPOINT, data=post_data, headers={
        "User-Agent": "TwinCitiesViz/1.0 (https://github.com/twin-cities-viz)",
        "Accept": "text/csv",
        "Content-Type": "application/x-www-form-urlencoded",
    })

    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read()

    text = raw.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    results = list(reader)
    print(f"  Got {len(results)} raw twin-city pairs from Wikidata.")
    return results


def parse_results(results):
    """Parse SPARQL CSV results into nodes and edges."""
    nodes = {}
    edges = []
    seen_edges = set()
    skipped = 0

    for row in results:
        try:
            # CSV format: flat columns with direct values
            # city/twin columns contain full URIs like http://www.wikidata.org/entity/Q64
            city_id = row["city"].split("/")[-1]
            twin_id = row["twin"].split("/")[-1]

            city_label = row.get("cityLabel", "") or city_id
            twin_label = row.get("twinLabel", "") or twin_id

            city_lat = float(row["cityLat"])
            city_lon = float(row["cityLon"])
            twin_lat = float(row["twinLat"])
            twin_lon = float(row["twinLon"])
        except (ValueError, KeyError, TypeError, AttributeError):
            skipped += 1
            continue

        # Store nodes
        if city_id not in nodes:
            nodes[city_id] = {
                "id": city_id,
                "name": city_label,
                "lat": city_lat,
                "lon": city_lon,
            }
        if twin_id not in nodes:
            nodes[twin_id] = {
                "id": twin_id,
                "name": twin_label,
                "lat": twin_lat,
                "lon": twin_lon,
            }

        # Deduplicate edges (A->B and B->A are the same twinning)
        edge_key = tuple(sorted([city_id, twin_id]))
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append({
                "source": city_id,
                "target": twin_id,
            })

    if skipped:
        print(f"  Skipped {skipped} rows with missing/invalid data.")
    print(f"  Parsed {len(nodes)} unique cities and {len(edges)} unique twinning relationships.")
    return nodes, edges


def get_continent(lat, lon):
    """Rough continent classification based on coordinates."""
    if lat > 35 and -25 < lon < 60:
        return "Europe"
    elif lat > 10 and 60 < lon < 150:
        return "Asia"
    elif lat < -10 and 100 < lon < 180:
        return "Oceania"
    elif -35 < lat < 35 and -20 < lon < 55:
        return "Africa"
    elif lat > 10 and -170 < lon < -30:
        return "North America"
    elif lat <= 10 and -90 < lon < -30:
        return "South America"
    elif lat < -10 and lon < 100:
        return "Africa"
    else:
        return "Other"


def analyze_graph(nodes, edges):
    """Build NetworkX graph, find connected components and communities."""
    if not HAS_NETWORKX:
        for node in nodes.values():
            node["community"] = 0
            node["family"] = 0
            node["familySize"] = 0
            node["continent"] = get_continent(node["lat"], node["lon"])
        return nodes, edges

    print("Building graph and analyzing network structure...")

    G = nx.Graph()
    for node_id, node_data in nodes.items():
        G.add_node(node_id, **node_data)
    for edge in edges:
        G.add_edge(edge["source"], edge["target"])

    # Connected components — these are the "sibling families"
    components = list(nx.connected_components(G))
    components.sort(key=len, reverse=True)
    print(f"  Found {len(components)} sibling families (connected components).")
    print(f"  Largest family: {len(components[0])} cities")
    if len(components) > 1:
        print(f"  Second largest: {len(components[1])} cities")

    # Community detection for coloring
    try:
        communities = nx.community.greedy_modularity_communities(G)
        community_map = {}
        for i, comm in enumerate(communities):
            for node_id in comm:
                community_map[node_id] = i
        print(f"  Detected {len(communities)} communities via modularity optimization.")
    except Exception as e:
        print(f"  Community detection failed ({e}), falling back to components.")
        community_map = {}
        for i, comp in enumerate(components):
            for node_id in comp:
                community_map[node_id] = i

    # Build family (connected component) map
    family_map = {}
    family_size_map = {}
    for i, comp in enumerate(components):
        for node_id in comp:
            family_map[node_id] = i
            family_size_map[node_id] = len(comp)

    # Attach community, family, continent to nodes
    for node_id, node_data in nodes.items():
        node_data["community"] = community_map.get(node_id, 0)
        node_data["family"] = family_map.get(node_id, 0)
        node_data["familySize"] = family_size_map.get(node_id, 1)
        node_data["continent"] = get_continent(node_data["lat"], node_data["lon"])
        node_data["degree"] = G.degree(node_id)

    # Some fun stats
    degrees = sorted([(G.degree(n), nodes[n]["name"]) for n in G.nodes()], reverse=True)
    print("\n  Top 10 most-twinned cities:")
    for deg, name in degrees[:10]:
        print(f"    {name}: {deg} twins")

    return nodes, edges


def export_json(nodes, edges, filename="twin_cities_data.json"):
    """Export nodes and edges as JSON for the frontend."""
    # Build arc data directly for Deck.gl
    arcs = []
    for edge in edges:
        src = nodes[edge["source"]]
        tgt = nodes[edge["target"]]
        arcs.append({
            "sourcePosition": [src["lon"], src["lat"]],
            "targetPosition": [tgt["lon"], tgt["lat"]],
            "sourceName": src["name"],
            "targetName": tgt["name"],
            "sourceCommunity": src.get("community", 0),
            "targetCommunity": tgt.get("community", 0),
            "sourceContinent": src.get("continent", "Other"),
            "targetContinent": tgt.get("continent", "Other"),
        })

    # Build named edge list for client-side pathfinding
    named_edges = []
    for edge in edges:
        src = nodes[edge["source"]]
        tgt = nodes[edge["target"]]
        named_edges.append({
            "source": src["name"],
            "target": tgt["name"],
        })

    node_list = list(nodes.values())

    output = {
        "nodes": node_list,
        "arcs": arcs,
        "edges": named_edges,
        "stats": {
            "totalCities": len(node_list),
            "totalConnections": len(arcs),
            "communities": len(set(n.get("community", 0) for n in node_list)),
        },
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"\nExported {len(node_list)} cities and {len(arcs)} arcs to {filename}")
    return output


def main():
    results = fetch_twin_cities()
    nodes, edges = parse_results(results)
    nodes, edges = analyze_graph(nodes, edges)
    export_json(nodes, edges)


if __name__ == "__main__":
    main()
