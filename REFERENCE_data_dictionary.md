# NYC DOT Safety Data - Data Dictionary

This document describes all datasets used in the CB5 safety infrastructure analysis.

---

## Quick Reference: Dataset URLs

| Dataset | NYC Open Data URL | Endpoint ID |
|---------|-------------------|-------------|
| Traffic Signal Studies | https://data.cityofnewyork.us/Transportation/Traffic-Signal-and-All-Way-Stop-Study-Requests/w76s-c5u4 | `w76s-c5u4` |
| Speed Reducer (SRTS) | https://data.cityofnewyork.us/Transportation/Speed-Reducer-Tracking-System-SRTS-/9n6h-pt9g | `9n6h-pt9g` |
| APS Installed | https://data.cityofnewyork.us/Transportation/Accessible-Pedestrian-Signal-Locations/de3m-c5p4 | `de3m-c5p4` |
| Motor Vehicle Crashes | https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95 | `h9gi-nx95` |
| 311 Service Requests | https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9 | `erm2-nwe9` |

---

## 1. Traffic Signal and All-Way Stop Study Requests

**Purpose**: Primary dataset for tracking formal infrastructure requests to NYC DOT for traffic signals, stop signs, APS, and related infrastructure.

**File**: `data_raw/signal_studies_citywide.csv`
**Records**: ~74,485 citywide
**Time Range**: 2006 - Present

### Key Fields

| Field | Description | Example Values |
|-------|-------------|----------------|
| `referencenumber` | Unique request ID | CQ25-3181, CM22-1234 |
| `daterequested` | Date request was submitted | 2025-10-06T00:00:00.000 |
| `statusdescription` | **CRITICAL** - Current outcome status | See status table below |
| `studystatus` | Open/Closed indicator | OPEN, CLOSED |
| `requesttype` | Type of infrastructure requested | Traffic Signal, All-Way Stop, APS |
| `borough` | Borough | Queens, Brooklyn, etc. |
| `mainstreet` | Primary street of intersection | METROPOLITAN AVENUE |
| `crossstreet1` | Cross street | 69 STREET |
| `crossstreet2` | Second cross street (if applicable) | |
| `schoolcrossing` | Near a school? | Yes, No |
| `schoolname` | Name of nearby school | P.S. 229 EMANUEL KAPLAN |
| `visionzero` | Vision Zero priority location? | Yes, No |

### Status Descriptions (statusdescription)

**DENIED statuses** (count as rejection):
| Status | Meaning |
|--------|---------|
| `Study Request Denial` | Rejected without full engineering study - did not meet preliminary criteria |
| `Engineering Study Completed (Signals Engineering)` | Study done, but NO approval given = implicit rejection |
| `Denial - Sent to Enhanced Intersection` | Rejected, referred elsewhere |

**APPROVED statuses** (count as success):
| Status | Meaning |
|--------|---------|
| `Signal Approval` | Traffic signal installation approved |
| `A/W Approval` | All-Way Stop approved |
| `L/T Approval` | Left Turn signal approved |
| `LPI Approval` | Leading Pedestrian Interval approved |
| `APS Ranking Completed; Awaiting Design` | APS approved, in installation queue |
| `APS Installed` | APS physically installed |

**PENDING statuses**:
| Status | Meaning |
|--------|---------|
| `Construction In-Progress; Study On-Hold` | Waiting for construction to complete |
| `Consultant Study In Progress / Under Review` | Still being evaluated |

### Request Types (requesttype)

| Type | Description | Citywide Count | Denial Rate |
|------|-------------|----------------|-------------|
| Traffic Signal | New traffic light | 28,626 | 85.2% |
| All-Way Stop | All-way stop sign at intersection | 21,682 | 86.3% |
| Accessible Pedestrian Signal | APS for visually impaired | 4,905 | 12.3%* |
| Left Turn Arrow/Signal | Dedicated left turn signal | 5,208 | 91.2% |
| Leading Pedestrian Interval | Head start for pedestrians | 2,379 | 88.6% |

*APS has special treatment due to federal lawsuit mandating installation

---

## 2. Speed Reducer Tracking System (SRTS)

**Purpose**: Tracks requests for speed bumps and speed humps/cushions.

**File**: `data_raw/srts_citywide.csv`
**Records**: ~58,198 citywide
**Time Range**: Ongoing

### Key Fields

| Field | Description | Example Values |
|-------|-------------|----------------|
| `projectcode` | Unique project ID | SR-20240212-31334 |
| `cb` | Community Board number | 405 (= Queens CB5) |
| `borough` | Borough | Queens |
| `segmentstatusdescription` | **CRITICAL** - Outcome | Not Feasible, Feasible |
| `denialreason` | Why request was denied | See denial reasons below |
| `onstreet` | Street where bump requested | 87 AVENUE |
| `fromstreet` / `tostreet` | Block boundaries | 144 STREET to 148 STREET |
| `speedcushion` | Cushion (bus-friendly) vs hump | Yes, No |
| `requestdate` | Date of original request | 2024-02-12 |
| `closeddate` | Date request was resolved | 2024-06-20 |

### Community Board Codes

Format: `[Borough Code][District Number]`
- Borough 1 = Manhattan
- Borough 2 = Bronx
- Borough 3 = Brooklyn
- Borough 4 = Queens
- Borough 5 = Staten Island

**CB5 Queens = 405**

### Denial Reasons (CB5 most common)

| Reason | Count | Notes |
|--------|-------|-------|
| Radar speeds BELOW criteria of 30.0 mph at 85% | 651 | Speed not high enough |
| Multiple impeding driveways / curb cuts | 259 | Physical constraints |
| Street too short | 113 | Not enough roadway |
| Stop controls at end of roadway | 49 | Already has stops |
| Bus route | 36 | Can't put humps on bus routes |
| Multi-lane roadway | 23 | Only for single-lane streets |

---

## 3. Accessible Pedestrian Signal (APS) Locations

**Purpose**: Shows INSTALLED APS devices (not requests - those are in Signal Studies).

**File**: `data_raw/aps_installed_citywide.csv`
**Records**: ~3,914 installed citywide

### Context

In 2017, Disability Rights Advocates filed a lawsuit against NYC requiring installation of at least 9,000 APS devices by 2031. APS devices provide audible and vibrotactile signals to assist blind/low-vision pedestrians at crosswalks.

### Key Fields

| Field | Description |
|-------|-------------|
| `location` | Intersection description (e.g., "Nostrand Avenue and Prospect Place") |
| `borough` | Borough |
| `borocd` | Community district code (405 = CB5 Queens) |
| `date_insta` | Installation date |
| `point_x` / `point_y` | Coordinates |

### APS by Borough (Installed)

| Borough | Installed |
|---------|-----------|
| Brooklyn | 978 |
| Queens | 917 |
| Bronx | 796 |
| Manhattan | 716 |
| Staten Island | 507 |
| **CB5 Queens** | **77** |

---

## 4. Motor Vehicle Collisions - Crashes

**Purpose**: All motor vehicle crashes reported by NYPD. Useful for correlating denied safety requests with actual crash locations.

**File**: `data_raw/crashes_queens_2020plus.csv`
**Records**: ~41,632 (Queens, 2020+, with injuries)

### Key Fields

| Field | Description |
|-------|-------------|
| `crash_date` | Date of crash |
| `borough` | Borough |
| `latitude` / `longitude` | Location |
| `on_street_name` | Street where crash occurred |
| `number_of_persons_injured` | Total injuries |
| `number_of_pedestrians_injured` | Pedestrian injuries |
| `number_of_cyclist_injured` | Cyclist injuries |
| `contributing_factor_vehicle_1` | Primary cause |

---

## 5. 311 Service Requests (DOT)

**Purpose**: Maintenance-focused complaints (broken lights, missing signs). Less reliable for formal infrastructure requests.

**File**: `data_raw/311_cb5_dot_2020plus.csv`
**Records**: ~31,205 (CB5, 2020+)

### Why 311 is Less Reliable for This Analysis

311 is primarily for **maintenance** issues:
- Broken traffic lights
- Street lights out
- Missing/damaged signs
- Pothole complaints

It does NOT reliably track **new infrastructure requests** like:
- New traffic signals
- New stop signs
- Speed bumps

For new infrastructure analysis, use the **Signal Studies** and **SRTS** datasets instead.

---

## CB5 Key Statistics Summary

### Traffic Signals & Stop Signs (from Signal Studies)

| Metric | CB5 | Citywide | Difference |
|--------|-----|----------|------------|
| Total Requests | ~939 | 74,485 | |
| Denial Rate | 84.2% | 83.3% | +0.9 pts |
| Batting Average | 15.8% | 16.7% | -0.9 pts |

### Speed Bumps (from SRTS)

| Metric | CB5 | Queens | Citywide |
|--------|-----|--------|----------|
| Total Requests | 1,988 | 24,632 | 58,198 |
| Denial Rate | **87.7%** | 87.4% | 84.7% |
| Batting Average | **12.3%** | 12.6% | 15.3% |

CB5 has one of the highest speed bump denial rates in the city.

---

## How to Use This Data

### API Access

All datasets can be accessed via the Socrata API:

```
https://data.cityofnewyork.us/resource/{ENDPOINT_ID}.json
```

Example - get all Queens signal studies:
```bash
curl "https://data.cityofnewyork.us/resource/w76s-c5u4.json?\$where=borough='Queens'&\$limit=50000"
```

### Local Files

After running `explore_all_data.py`, data is saved to:
- `data_raw/signal_studies_citywide.csv`
- `data_raw/srts_citywide.csv`
- `data_raw/aps_installed_citywide.csv`
- `data_raw/crashes_queens_2020plus.csv`
- `data_raw/311_cb5_dot_2020plus.csv`

---

## Additional Resources

- **Vision Zero View**: https://vzv.nyc/ - Interactive crash data map
- **NYC DOT Data Feeds**: https://www.nyc.gov/html/dot/html/about/datafeeds.shtml
- **NYC Open Data Portal**: https://opendata.cityofnewyork.us/
