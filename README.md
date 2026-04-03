# Twin Cities of the World

**[Live demo](https://ashoksivathayalan.github.io/city-families/)**

An interactive map and network explorer for twin/sister city relationships worldwide. Data is sourced from [Wikidata](https://www.wikidata.org/) (property [P190](https://www.wikidata.org/wiki/Property:P190)), covering thousands of twinning relationships with geographic coordinates.

## Features

### Map View
- Great-circle paths between twin cities on a dark world map (Deck.gl + MapLibre)
- Arcs hidden by default for a clean view; toggle them on with controls for color mode (community, continent, distance), opacity, width, and a **min-twins filter** to cut noise
- Hover tooltips on cities and connections

### Pathfinder
- Find the shortest "sibling path" between any two cities through the twin-city network
- Autocomplete city search, BFS shortest path, highlighted route on the map

### Explorer
- Enter a city to see its ego-network: direct twins (1st degree) and their twins (2nd degree)
- Each ring rendered with decreasing prominence (bright/thick to faint/thin)

### Families
- Browse connected components ("sibling families") in the network
- Filter by size: pairs, small (3-10), medium (11-50), large (50+)
- Click any family to highlight it on the map

## Setup

### Requirements

- Python 3.10+
- [NetworkX](https://networkx.org/) (for graph analysis and community detection)

```bash
pip install -r requirements.txt
```

### Fetch data

```bash
python fetch_data.py
```

This queries the Wikidata SPARQL endpoint for all twin city pairs with coordinates, builds the network graph, detects communities and connected components, and exports `twin_cities_data.json`. Takes 30-60 seconds depending on network speed.

### Run

Serve the directory with any static file server:

```bash
python -m http.server 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Project Structure

```
fetch_data.py           # Data pipeline: Wikidata SPARQL -> NetworkX -> JSON
index.html              # Self-contained frontend (Deck.gl, MapLibre, vanilla JS)
twin_cities_data.json   # Generated data file (not committed)
requirements.txt        # Python dependencies
```

## Data Source

All twin city relationships come from Wikidata's [P190 (twinned administrative body)](https://www.wikidata.org/wiki/Property:P190) property. The dataset is community-maintained and may not be exhaustive. Results can vary slightly between fetches due to ongoing edits and Wikidata query service caching.
