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

The `cb` field in SRTS data contains some misattributed records. To ensure accuracy, we apply the following filtering logic:

### Exclusion Criteria

Records labeled `cb=405` are **excluded** if they have cross streets that indicate locations **north of the LIE** (in CB2/CB4 Elmhurst/Woodside):

**Excluded cross streets:**
- 51 Road, 51 Street
- 52 Avenue, 52 Drive, 52 Road, 52 Court
- 53 Avenue, 53 Drive, 53 Road
- Calamus Avenue
- Queens Boulevard
- Any street containing "Woodside"

**Excluded main streets:**
- Maurice Avenue (boundary street, not inside CB5)

### Inclusion Criteria

All other records with `cb=405` are included, specifically:

**Definitely CB5:**
- Caldwell Avenue (Maspeth, along LIE)
- Queens Midtown Expressway Service Roads (LIE service roads)
- Metropolitan Avenue corridor
- Myrtle Avenue corridor
- Fresh Pond Road corridor
- Cooper Avenue
- All numbered streets (60s-80s) with cross streets south of LIE

## Key CB5 Streets (Reference)

**Major Avenues (East-West):**
- Metropolitan Avenue
- Myrtle Avenue
- Cooper Avenue
- Eliot Avenue
- Juniper Valley Road
- 60 Avenue through 80 Avenue

**Major Streets (North-South):**
- Fresh Pond Road
- Forest Avenue
- Woodhaven Boulevard (eastern boundary)
- 60 Street through 88 Street

**Maspeth Area:**
- Caldwell Avenue
- Grand Avenue
- 54 Street through 58 Street area

## Filtering Results

| Metric | Count |
|--------|-------|
| Raw records (cb=405) | 1,988 |
| After cross-street filter | 1,913 |
| Excluded | 75 |

The 75 excluded records are demonstrably north of the LIE based on their cross streets (52nd Ave, 53rd Ave, Calamus Ave, etc.).

## Sources

- [Queens Community Board 5 Official Website](https://www.nyc.gov/site/queenscb5/about/about-qcb5.page)
- [Wikipedia - Queens Community Board 5](https://en.wikipedia.org/wiki/Queens_Community_Board_5)
- NYC Open Data - Speed Reducer Tracking System (9n6h-pt9g)
