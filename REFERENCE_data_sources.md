# Data Sources

This analysis relies on public datasets provided by **NYC Open Data**.

## 1. 311 Service Requests from 2010 to Present
*   **Source**: NYC Open Data
*   **Agency**: Department of Information Technology & Telecommunications (DoITT)
*   **URL**: [https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9)
*   **Description**: Contains all 311 service requests.
    *   **Usage**: 
        1.  **Maintenance**: `agency`='DOT' + 'Traffic Signal Condition', 'Street Light Condition', 'Sign Missing'.
        2.  **Speed Camera Proxy**: Filtered for `descriptor`='Traffic Camera' (as no public "Camera Request" dataset exists).

## 2. Motor Vehicle Collisions - Crashes
*   **Source**: NYC Open Data
*   **Agency**: New York City Police Department (NYPD)
*   **URL**: [https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95)
*   **Description**: Details on crash events.
    *   **Usage**: Filtered for `borough`='QUEENS' and spatial join to CB5. Used to verify "Danger" hypothesis.

## 3. Traffic Signal and All-Way Stop Study Requests
*   **Source**: NYC Open Data
*   **Agency**: DOT
*   **URL**: [https://data.cityofnewyork.us/Transportation/Traffic-Signal-and-All-Way-Stop-Study-Requests/w76s-c5u4](https://data.cityofnewyork.us/Transportation/Traffic-Signal-and-All-Way-Stop-Study-Requests/w76s-c5u4)
*   **Description**: Tracks "New Infrastructure" requests (Studies).
    *   **Usage**: Primary source for Denial Rate analysis.
    *   **Logic**: 
        *   **Core Traffic Control**: Filtered OUT `Accessible Pedestrian Signal` to focus on Stop Signs/Signals.
        *   **Denial Rate**: `(Study Request Denial + Engineering Study Completed)` / `Total Resolved`.

## 4. Speed Reducer Tracking System (SRTS)
*   **Source**: NYC Open Data
*   **Agency**: DOT
*   **URL**: [https://data.cityofnewyork.us/Transportation/Speed-Reducer-Tracking-System/9n6h-pt9g](https://data.cityofnewyork.us/Transportation/Speed-Reducer-Tracking-System/9n6h-pt9g)
*   **Description**: Tracks requests for Speed Bumps / Humps.
    *   **Key Fields**: `segmentstatusdescription` (e.g., "Not Feasible", "Feasible").
    *   **Usage**: Used to identify the high rejection rate of traffic calming measures in CB5.

## 5. Accessible Pedestrian Signal (APS) Locations
*   **Source**: NYC DOT Website / NYC Open Data
*   **Description**: Ground truth for installed APS units. used to calculate "Realized Installation Rate".

---

## Data Dictionary & Status Definitions

### Traffic Signal Studies
*   **Engineering Study Completed**: The technical analysis is finished. If not followed by "Approval", this implies **No Action Warranted** (Rejection).
*   **Study Request Denial**: Explicit rejection. Did not meet preliminary criteria.
*   **Signal Approval**: Study confirmed signal is warranted; installation approved.
*   **APS Ranking Completed**: Assessment for APS is done; added to priority list (does not guarantee immediate install).

### Speed Reducers (SRTS)
*   **Not Feasible**: Request evaluated and rejected (e.g., street too wide, fire route, etc.).
*   **Feasible**: Approved for installation pending funding/schedule.
