"""
Link water filter consumables to refrigerator models by model-number prefix.

Uses the data from the Excel spreadsheet (Refrigerator_Water_Filters_By_Model_Expanded)
to create prefix-based mappings between water filters and fridge models in the database.

Usage:
    py link_filters_by_prefix.py --dry-run    # preview what would be linked
    py link_filters_by_prefix.py              # actually create the linkages
"""

import argparse
import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# PREFIX-TO-FILTER MAPPING
# ---------------------------------------------------------------------------
# Derived from: excel_data/Refrigerator_Water_Filters_By_Model_Expanded (1).xlsx
#
# Each entry maps:
#   brand  -> list of (prefix, filter_sku, filter_name)
#
# The Excel groups filters by series prefixes. Where a single filter covers
# broad series (e.g. "WRS, WRF, WRX"), we list each prefix individually.
# More specific prefixes (e.g. "WRF736") override broader ones when the
# Excel explicitly calls them out under a different filter.
#
# Ordering matters: more-specific (longer) prefixes are checked first so that
# e.g. "WRS588" matches EDR4RXD1 before the generic "WRS" matches EDR1RXD1.
# ---------------------------------------------------------------------------

PREFIX_FILTER_MAP = {
    "Whirlpool": [
        # EDR4RXD1 (Filter 4) - specific series
        ("WRS588", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        ("WRS973", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        ("WRF757", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        # EDR3RXD1 (Filter 3) - specific series
        ("WRS321", "EDR3RXD1", "EveryDrop Filter 3 (EDR3RXD1)"),
        ("WRF535", "EDR3RXD1", "EveryDrop Filter 3 (EDR3RXD1)"),
        ("WRF560", "EDR3RXD1", "EveryDrop Filter 3 (EDR3RXD1)"),
        # EDR2RXD1 (Filter 2) - specific series
        ("WRF736", "EDR2RXD1", "EveryDrop Filter 2 (EDR2RXD1)"),
        # EDR1RXD1 (Filter 1) - broad WRS/WRF/WRX series (catch-all after specifics)
        ("WRS", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        ("WRF", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        ("WRX", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        # EDR5RXD1 (Filter 5) - bottom-freezer & side-by-side select
        ("WRB", "EDR5RXD1", "EveryDrop Filter 5 (EDR5RXD1)"),
        ("WRT", "EDR5RXD1", "EveryDrop Filter 5 (EDR5RXD1)"),
        ("WRV", "EDR5RXD1", "EveryDrop Filter 5 (EDR5RXD1)"),
    ],
    "KitchenAid": [
        # KitchenAid is a Whirlpool Corp brand using EveryDrop filters
        # KRFC300 -> EDR2RXD1 per Excel
        ("KRFC300", "EDR2RXD1", "EveryDrop Filter 2 (EDR2RXD1)"),
        ("KRFF302", "EDR2RXD1", "EveryDrop Filter 2 (EDR2RXD1)"),
        # Broader KitchenAid series -> EDR4RXD1 per existing DB mapping
        ("KRFC", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        ("KRFF", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        ("KRMF", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        # Other KitchenAid models using various EveryDrop filters
        ("KFIS", "EDR4RXD1", "EveryDrop Filter 4 (EDR4RXD1)"),
        ("KBFS", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        ("KSSC", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        ("KSBP", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
        ("KSSO", "EDR1RXD1", "EveryDrop Filter 1 (EDR1RXD1)"),
    ],
    "Samsung": [
        # HAF-CIN (DA29-00020B) - RF23, RF28, RS25 French Door & Side-by-Side
        ("RF23", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RF28", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RF25", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RS25", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RS27", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        # HAF-QIN (DA29-00003G) - older French Door models
        ("RF26", "DA29-00003G", "Samsung HAF-QIN Water Filter (DA29-00003G)"),
        ("RF22", "DA29-00003G", "Samsung HAF-QIN Water Filter (DA29-00003G)"),
        ("RF24", "DA29-00003G", "Samsung HAF-QIN Water Filter (DA29-00003G)"),
        ("RF27", "DA29-00003G", "Samsung HAF-QIN Water Filter (DA29-00003G)"),
        ("RFG", "DA29-00003G", "Samsung HAF-QIN Water Filter (DA29-00003G)"),
        # DA29-00012A - legacy side-by-side
        ("RS26", "DA29-00012A", "Samsung Water Filter (DA29-00012A)"),
        # RH series (Food Showcase)
        ("RH22", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RH25", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
        ("RH29", "DA29-00020B", "Samsung HAF-CIN Water Filter (DA29-00020B)"),
    ],
    "GE": [
        # RPWFE - newer GE Profile French Door
        ("PFE", "RPWFE", "GE RPWFE Water Filter"),
        ("PYE", "RPWFE", "GE RPWFE Water Filter"),
        ("PWE", "RPWFE", "GE RPWFE Water Filter"),
        ("PYD", "RPWFE", "GE RPWFE Water Filter"),
        ("PVD", "RPWFE", "GE RPWFE Water Filter"),
        ("CFE", "RPWFE", "GE RPWFE Water Filter"),
        ("CYE", "RPWFE", "GE RPWFE Water Filter"),
        ("CWE", "RPWFE", "GE RPWFE Water Filter"),
        ("CZS", "RPWFE", "GE RPWFE Water Filter"),
        # XWFE - GE models requiring RFID-enabled filters
        ("GNE", "XWFE", "GE XWFE Water Filter"),
        ("GFE", "XWFE", "GE XWFE Water Filter"),
        ("GDE", "XWFE", "GE XWFE Water Filter"),
        ("GWE", "XWFE", "GE XWFE Water Filter"),
        ("GYE", "XWFE", "GE XWFE Water Filter"),
        # MWF / MWFP - GE French Door & Side-by-Side (broader/older)
        ("GSS", "MWF", "GE MWF Water Filter"),
        ("GSE", "MWF", "GE MWF Water Filter"),
        ("GBE", "MWF", "GE MWF Water Filter"),
        ("GBS", "MWF", "GE MWF Water Filter"),
        # MSWF - older side-by-side
        ("GSH", "MSWF", "GE MSWF Water Filter"),
        # GTS / top-freezer models - these generally use MWF
        ("GTS", "MWF", "GE MWF Water Filter"),
        ("GTE", "MWF", "GE MWF Water Filter"),
        ("GIE", "MWF", "GE MWF Water Filter"),
        ("GTT", "MWF", "GE MWF Water Filter"),
    ],
    "Frigidaire": [
        # ULTRAWF - Gallery & Professional French Door
        ("FGHB", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FGHS", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FGSS", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FGHT", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FPBS", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FPHB", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("LGHB", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("LGHS", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        # EPTWFU01 - PureSource Ultra II (side-by-side)
        ("FFSS", "EPTWFU01", "Frigidaire PureSource Ultra II (EPTWFU01)"),
        ("LFSS", "EPTWFU01", "Frigidaire PureSource Ultra II (EPTWFU01)"),
        # FFHB, FFHS - these typically use ULTRAWF as well
        ("FFHB", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FFHS", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("FFHD", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
        ("LFHB", "ULTRAWF", "Frigidaire PureSource Ultra (ULTRAWF)"),
    ],
    "Bosch": [
        # UltraClarity Pro 11032531 (BORPLFTR55 / BORPLFTR50)
        ("B36", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
        ("B26", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
        ("B21", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
        ("B22", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
        ("B20", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
        ("B30", "BORPLFTR50", "Bosch UltraClarity Pro Water Filter (BORPLFTR50)"),
    ],
    "LG": [
        # LT1000P - newer French Door models (LSXS, LFXS, LMXS per Excel)
        ("LFXS", "LT1000P", "LG LT1000P Water Filter"),
        ("LMXS", "LT1000P", "LG LT1000P Water Filter"),
        ("LFXC", "LT1000P", "LG LT1000P Water Filter"),
        ("LRFC", "LT1000P", "LG LT1000P Water Filter"),
        ("LRFD", "LT1000P", "LG LT1000P Water Filter"),
        ("LFCS", "LT1000P", "LG LT1000P Water Filter"),
        ("LRSP", "LT1000P", "LG LT1000P Water Filter"),
        # LT800P - premium InstaView & Door-in-Door
        ("LMXC", "LT800P", "LG LT800P Water Filter"),
        # LT700P - older side-by-side models (LSC, LSXS per Excel)
        ("LSXS", "LT700P", "LG LT700P Water Filter"),
        ("LSC2", "LT700P", "LG LT700P Water Filter"),
        ("LRSC", "LT700P", "LG LT700P Water Filter"),
        ("LRBN", "LT700P", "LG LT700P Water Filter"),
        ("LRDN", "LT700P", "LG LT700P Water Filter"),
        ("LRTN", "LT700P", "LG LT700P Water Filter"),
        # LT600P - older bottom freezer & side-by-side
        ("LFX2", "LT600P", "LG LT600P Water Filter"),
        ("LFX3", "LT600P", "LG LT600P Water Filter"),
        ("LFC2", "LT600P", "LG LT600P Water Filter"),
        ("LMX2", "LT600P", "LG LT600P Water Filter"),
        ("LFD2", "LT600P", "LG LT600P Water Filter"),
        ("LBC2", "LT600P", "LG LT600P Water Filter"),
        ("LDC2", "LT600P", "LG LT600P Water Filter"),
        # LT500P - compact LG refrigerators
        ("LTCS", "LT500P", "LG LT500P Water Filter"),
    ],
    "Thermador": [
        # UltraClarity Pro 11032531 (REPLFLTR55) - newer models
        ("T36", "REPLFLTR55", "Thermador UltraClarity Pro Water Filter (REPLFLTR55)"),
        ("T30", "REPLFLTR55", "Thermador UltraClarity Pro Water Filter (REPLFLTR55)"),
        ("T42", "REPLFLTR55", "Thermador UltraClarity Pro Water Filter (REPLFLTR55)"),
        ("T48", "REPLFLTR55", "Thermador UltraClarity Pro Water Filter (REPLFLTR55)"),
        # UltraClarity 11034152 (REPLFLTR30) - older models
        ("T24", "REPLFLTR30", "Thermador UltraClarity Water Filter (REPLFLTR30)"),
        ("T18", "REPLFLTR30", "Thermador UltraClarity Water Filter (REPLFLTR30)"),
    ],
}


def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    return psycopg2.connect(db_url, sslmode="require")


def ensure_consumable(cur, sku, name, filter_type="Water Filter"):
    """Insert or get the consumable by SKU. Returns consumable id."""
    cur.execute("SELECT id FROM consumables WHERE sku = %s", (sku,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO consumables (name, type, sku) VALUES (%s, %s, %s) RETURNING id",
        (name, filter_type, sku),
    )
    return cur.fetchone()[0]


def find_models_by_prefix(cur, brand, prefix):
    """Find all refrigerator model IDs matching a brand + prefix."""
    cur.execute(
        """
        SELECT m.id, m.model_number
        FROM models m
        JOIN brands b ON m.brand_id = b.id
        JOIN categories c ON m.category_id = c.id
        WHERE c.name = 'refrigerator'
          AND b.name = %s
          AND UPPER(m.model_number) LIKE %s
        """,
        (brand, prefix.upper() + "%"),
    )
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Link water filters to fridge models by prefix")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    total_links = 0
    new_links = 0
    skipped_existing = 0

    for brand, mappings in PREFIX_FILTER_MAP.items():
        print(f"\n{'='*60}")
        print(f"  {brand}")
        print(f"{'='*60}")

        # Track which model IDs have already been matched by a more-specific prefix
        matched_model_ids = set()

        for prefix, sku, filter_name in mappings:
            models = find_models_by_prefix(cur, brand, prefix)

            # Filter out models already matched by a more-specific (longer) prefix
            unmatched = [(mid, mnum) for mid, mnum in models if mid not in matched_model_ids]

            if not unmatched:
                continue

            # Mark these model IDs as matched
            for mid, _ in unmatched:
                matched_model_ids.add(mid)

            if not args.dry_run:
                consumable_id = ensure_consumable(cur, sku, filter_name)
            else:
                consumable_id = None

            print(f"\n  {prefix}* -> {sku} ({filter_name})")
            print(f"    {len(unmatched)} models to link")

            if len(unmatched) <= 5:
                for _, mnum in unmatched:
                    print(f"      {mnum}")
            else:
                for _, mnum in unmatched[:3]:
                    print(f"      {mnum}")
                print(f"      ... and {len(unmatched) - 3} more")

            total_links += len(unmatched)
            if not args.dry_run:
                note = f"Matched by prefix {prefix}*"
                rows = [(mid, consumable_id, note) for mid, _ in unmatched]
                # Batch insert in chunks of 500
                for i in range(0, len(rows), 500):
                    chunk = rows[i : i + 500]
                    try:
                        execute_values(
                            cur,
                            """
                            INSERT INTO model_consumables (model_id, consumable_id, notes)
                            VALUES %s
                            ON CONFLICT (model_id, consumable_id) DO NOTHING
                            """,
                            chunk,
                        )
                        conn.commit()
                    except Exception as e:
                        print(f"      ERROR batch insert for {prefix}*: {e}")
                        conn.rollback()
                new_links += len(unmatched)
            else:
                new_links += len(unmatched)

        print(f"\n  {brand} subtotal: {len(matched_model_ids)} models matched")

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total links processed: {total_links}")
    print(f"  New links created:     {new_links}")
    if args.dry_run:
        print(f"\n  *** DRY RUN - no changes written ***")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
