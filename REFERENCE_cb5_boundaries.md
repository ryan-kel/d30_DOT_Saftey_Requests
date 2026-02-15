# Queens Community Board 5 - Boundary Definition

## Official Boundaries

Per NYC official documentation, Queens Community Board 5 includes:

**Neighborhoods:**
- Ridgewood
- Glendale
- Middle Village
- Maspeth
- Fresh Pond
- Liberty Park

**Boundary Streets:**
- **North:** Maurice Avenue and the Long Island Expressway (I-495)
- **West:** Brooklyn borough line
- **South:** Brooklyn borough line
- **East:** Woodhaven Boulevard

## Data Filtering Methodology

The `cb` field in SRTS data contains some misattributed records. The **official CB5 polygon** (`data_raw/cb5_boundary.geojson`) is the **sole geographic authority** for determining whether a record falls within CB5.

### Filtering Pipeline

1. **`cb=405`** — Initial filter (Queens borough 4, district 05)
2. **Polygon boundary filter** — Shapely point-in-polygon test against the official CB5 GeoJSON

No street-name heuristics are used. An earlier cross-street exclusion approach (targeting 52 Ave, 53 Ave, Calamus Ave, etc.) was removed after audit revealed it wrongly excluded 67 records that fall inside the official CB5 polygon boundary, particularly in northern Maspeth where these streets run through CB5 territory.

## Key CB5 Streets (Reference)

**Major Avenues (East-West):**
- Metropolitan Avenue
- Myrtle Avenue
- Cooper Avenue
- Eliot Avenue
- Juniper Valley Road
- 52 Avenue through 80 Avenue (northern Maspeth through Glendale)

**Major Streets (North-South):**
- Fresh Pond Road
- Forest Avenue
- Woodhaven Boulevard (eastern boundary)
- 60 Street through 88 Street

**Maspeth Area:**
- Caldwell Avenue
- Grand Avenue
- Maurice Avenue (boundary street — some segments inside polygon)
- 54 Street through 74 Street area

## Filtering Results

SRTS records pass through two filtering layers:

| Step | Metric | Count |
|------|--------|-------|
| 1 | Raw records (cb=405) | 1,988 |
| 2 | After polygon boundary filter | 1,962 |
| — | Excluded by polygon filter | 26 |

The 26 excluded records have coordinates that fall outside the official CB5 boundary geometry. **The polygon is the sole authority** — see `_load_cb5_srts_full()` in `generate_maps.py`.

## Sources

- [Queens Community Board 5 Official Website](https://www.nyc.gov/site/queenscb5/about/about-qcb5.page)
- [Wikipedia - Queens Community Board 5](https://en.wikipedia.org/wiki/Queens_Community_Board_5)
- NYC Open Data - Speed Reducer Tracking System (9n6h-pt9g)
