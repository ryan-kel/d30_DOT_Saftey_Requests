#!/usr/bin/env python3
"""Export the Folium consolidated map as a PNG screenshot with all layers enabled.

Usage:
    python export_map_png.py              # Default: all layers, 1920x1080
    python export_map_png.py --width 2560 --height 1440
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Inject extracted libs for headless Chromium on WSL2 (no sudo required)
_EXTRA_LIBS = "/tmp/chromium_libs/extracted/usr/lib/x86_64-linux-gnu"
if Path(_EXTRA_LIBS).exists():
    os.environ["LD_LIBRARY_PATH"] = (
        _EXTRA_LIBS + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    )

from playwright.sync_api import sync_playwright

MAP_HTML = Path("output/map_01_crash_denial_overlay.html")
OUTPUT_PNG = Path("output/map_01_all_layers.png")


def export_map(width=1920, height=1080, output=None):
    if not MAP_HTML.exists():
        print(f"ERROR: {MAP_HTML} not found. Run generate_maps.py first.")
        sys.exit(1)

    out_path = Path(output) if output else OUTPUT_PNG
    abs_path = MAP_HTML.resolve().as_uri()
    print(f"Opening {abs_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(abs_path, wait_until="networkidle")

        # Wait for the Leaflet layer control to render
        page.wait_for_selector(".leaflet-control-layers-overlays", timeout=15000)
        time.sleep(2)  # Let initial tiles load

        # Enable ALL layer checkboxes (some are off by default)
        unchecked = page.query_selector_all(
            ".leaflet-control-layers-overlays input[type='checkbox']:not(:checked)"
        )
        for cb in unchecked:
            cb.click()
            time.sleep(0.3)

        print(f"Enabled {len(unchecked)} additional layers")

        # Zoom to fit the CB5 boundary tightly
        page.evaluate("""
            (function() {
                var map = null;
                // Find the Leaflet map instance
                document.querySelectorAll('.folium-map').forEach(function(el) {
                    if (el._leaflet_id) {
                        for (var key in window) {
                            if (window[key] && window[key]._container === el) {
                                map = window[key]; break;
                            }
                        }
                    }
                });
                if (!map) {
                    // Fallback: search all window properties for a Leaflet map
                    for (var key in window) {
                        try {
                            if (window[key] && typeof window[key].getZoom === 'function') {
                                map = window[key]; break;
                            }
                        } catch(e) {}
                    }
                }
                if (map) {
                    // Allow fractional zoom for tightest possible fit
                    map.options.zoomSnap = 0;
                    map.options.zoomDelta = 0.25;
                    // Fit to exact CB5 polygon bounds, zero padding
                    map.fitBounds([
                        [40.6823, -73.9245],   // SW corner of CB5
                        [40.7351, -73.8553]    // NE corner of CB5
                    ], {padding: [0, 0], maxZoom: 18});
                }
            })();
        """)

        # Wait for new tiles and markers to render at new zoom
        page.wait_for_load_state("networkidle")
        time.sleep(5)  # Extra buffer for tile loading

        # Hide the layer control panel so it doesn't clutter the export
        page.evaluate("""
            var ctrl = document.querySelector('.leaflet-control-layers');
            if (ctrl) ctrl.style.display = 'none';
        """)

        # Take the screenshot
        page.screenshot(path=str(out_path), full_page=False)
        print(f"Saved: {out_path} ({width}x{height})")

        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Folium map as PNG")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    export_map(args.width, args.height, args.output)
