"""Export current database results to JSON for backup."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/results.db")
OUTPUT_DIR = Path("data/exports")

def export_to_json():
    if not DB_PATH.exists():
        print("No database found at", DB_PATH)
        return
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        
        # Export search results
        results = conn.execute("SELECT * FROM search_results ORDER BY score DESC").fetchall()
        results_data = [dict(row) for row in results]
        
        results_file = OUTPUT_DIR / f"results_{timestamp}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        print(f"Exported {len(results_data)} results to {results_file}")
        
        # Export funders
        try:
            funders = conn.execute("SELECT * FROM funders").fetchall()
            funders_data = [dict(row) for row in funders]
            
            funders_file = OUTPUT_DIR / f"funders_{timestamp}.json"
            with open(funders_file, "w", encoding="utf-8") as f:
                json.dump(funders_data, f, indent=2, ensure_ascii=False)
            print(f"Exported {len(funders_data)} funders to {funders_file}")
        except:
            print("No funders table found (ok if first run)")
        
        # Export pivot suggestions
        try:
            pivots = conn.execute("SELECT * FROM pivot_suggestions").fetchall()
            pivots_data = [dict(row) for row in pivots]
            
            pivots_file = OUTPUT_DIR / f"pivots_{timestamp}.json"
            with open(pivots_file, "w", encoding="utf-8") as f:
                json.dump(pivots_data, f, indent=2, ensure_ascii=False)
            print(f"Exported {len(pivots_data)} pivot suggestions to {pivots_file}")
        except:
            pass
    
    print(f"\nBackup complete! Files saved to {OUTPUT_DIR}/")

if __name__ == "__main__":
    export_to_json()
