"""Generate a readable HTML report of funding results."""

import sqlite3
import webbrowser
from pathlib import Path
from datetime import datetime

DB_PATH = Path("data/results.db")
OUTPUT_PATH = Path("data/results_report.html")


def get_results():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM search_results 
        ORDER BY 
            CASE WHEN is_open IN ('True', 'true') THEN 0 ELSE 1 END,
            score DESC
    """)
    
    return [dict(r) for r in cur.fetchall()]


def generate_html(results: list[dict]) -> str:
    # Group by project
    projects = {}
    for r in results:
        pid = r["project_id"]
        if pid not in projects:
            projects[pid] = []
        projects[pid].append(r)
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Funding Results Report</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 40px; }
        .stats { 
            background: #fff; 
            padding: 20px; 
            border-radius: 8px; 
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats span { 
            display: inline-block; 
            margin-right: 30px; 
            padding: 8px 16px;
            background: #ecf0f1;
            border-radius: 4px;
        }
        .filters {
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .filters label { margin-right: 20px; }
        .filters select, .filters input { 
            padding: 8px; 
            border: 1px solid #ddd; 
            border-radius: 4px;
            margin-right: 10px;
        }
        .result { 
            background: #fff; 
            padding: 20px; 
            margin-bottom: 15px; 
            border-radius: 8px;
            border-left: 4px solid #bdc3c7;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .result.open { border-left-color: #27ae60; }
        .result.closed { border-left-color: #e74c3c; }
        .result.high-score { border-left-color: #f39c12; }
        .result h3 { margin: 0 0 10px 0; }
        .result h3 a { color: #2980b9; text-decoration: none; }
        .result h3 a:hover { text-decoration: underline; }
        .meta { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 10px; 
            margin-bottom: 10px; 
        }
        .tag { 
            display: inline-block; 
            padding: 4px 10px; 
            border-radius: 12px; 
            font-size: 12px; 
            font-weight: 500;
        }
        .tag.score { background: #3498db; color: white; }
        .tag.open { background: #27ae60; color: white; }
        .tag.closed { background: #e74c3c; color: white; }
        .tag.unknown { background: #95a5a6; color: white; }
        .tag.funder { background: #9b59b6; color: white; }
        .tag.deadline { background: #e67e22; color: white; }
        .tag.amount { background: #1abc9c; color: white; }
        .snippet { 
            color: #555; 
            font-size: 14px; 
            line-height: 1.6;
            margin: 10px 0;
        }
        .summary { 
            font-style: italic; 
            color: #666;
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .details { font-size: 13px; color: #777; }
        .topics { margin-top: 8px; }
        .topics span { 
            display: inline-block;
            background: #e8f4f8;
            color: #2980b9;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin-right: 5px;
        }
        .project-section { margin-bottom: 50px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <h1>Funding Discovery Report</h1>
    <p>Generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """</p>
    
    <div class="stats">
        <span><strong>Total Results:</strong> """ + str(len(results)) + """</span>
        <span><strong>Open:</strong> """ + str(sum(1 for r in results if r.get("is_open") in ("True", "true"))) + """</span>
        <span><strong>With Deadlines:</strong> """ + str(sum(1 for r in results if r.get("deadline"))) + """</span>
        <span><strong>With Amounts:</strong> """ + str(sum(1 for r in results if r.get("grant_amount"))) + """</span>
    </div>
    
    <div class="filters">
        <label>Min Score: <input type="range" id="minScore" min="0" max="100" value="50" oninput="filterResults()"> <span id="scoreVal">0.5</span></label>
        <label>Status: 
            <select id="statusFilter" onchange="filterResults()">
                <option value="all">All</option>
                <option value="open">Open Only</option>
                <option value="closed">Closed Only</option>
            </select>
        </label>
        <label>Search: <input type="text" id="searchBox" placeholder="Type to filter..." oninput="filterResults()"></label>
    </div>
"""

    for project_id, proj_results in projects.items():
        html += f"""
    <div class="project-section">
        <h2>Project: {project_id.replace('_', ' ').title()}</h2>
        <p>{len(proj_results)} results</p>
"""
        for r in proj_results:
            score = r.get("score") or 0
            is_open = r.get("is_open", "").lower() if r.get("is_open") else "unknown"
            
            open_class = ""
            if is_open in ("true",):
                open_class = "open"
            elif is_open in ("false",):
                open_class = "closed"
            elif score >= 0.85:
                open_class = "high-score"
            
            # Status tag
            status_tag = ""
            if is_open == "true":
                status_tag = '<span class="tag open">OPEN</span>'
            elif is_open == "false":
                status_tag = '<span class="tag closed">CLOSED</span>'
            else:
                status_tag = '<span class="tag unknown">STATUS UNKNOWN</span>'
            
            # Parse topics
            topics_html = ""
            if r.get("topic_match"):
                try:
                    import json
                    topics = json.loads(r["topic_match"].replace("'", '"'))
                    topics_html = '<div class="topics">' + ''.join(f'<span>{t}</span>' for t in topics) + '</div>'
                except:
                    pass
            
            html += f"""
        <div class="result {open_class}" data-score="{score}" data-status="{is_open}">
            <h3><a href="{r.get('url', '#')}" target="_blank">{r.get('title', 'Untitled')}</a></h3>
            <div class="meta">
                <span class="tag score">Score: {score}</span>
                {status_tag}
                {f'<span class="tag funder">{r.get("funder_type")}</span>' if r.get("funder_type") else ''}
                {f'<span class="tag deadline">Deadline: {r.get("deadline")}</span>' if r.get("deadline") else ''}
                {f'<span class="tag amount">{r.get("grant_amount")}</span>' if r.get("grant_amount") else ''}
            </div>
            {f'<div class="summary">{r.get("summary")}</div>' if r.get("summary") else ''}
            <div class="snippet">{r.get("snippet") or "No description available."}</div>
            {f'<div class="details"><strong>Eligibility:</strong> {r.get("eligibility_notes")}</div>' if r.get("eligibility_notes") else ''}
            {topics_html}
            <div class="details"><strong>Query:</strong> {r.get("query")}</div>
        </div>
"""
        html += "    </div>\n"

    html += """
    <script>
        function filterResults() {
            const minScore = document.getElementById('minScore').value / 100;
            document.getElementById('scoreVal').textContent = minScore.toFixed(2);
            const statusFilter = document.getElementById('statusFilter').value;
            const searchText = document.getElementById('searchBox').value.toLowerCase();
            
            document.querySelectorAll('.result').forEach(el => {
                const score = parseFloat(el.dataset.score);
                const status = el.dataset.status;
                const text = el.textContent.toLowerCase();
                
                let show = score >= minScore;
                if (statusFilter === 'open') show = show && status === 'true';
                if (statusFilter === 'closed') show = show && status === 'false';
                if (searchText) show = show && text.includes(searchText);
                
                el.classList.toggle('hidden', !show);
            });
        }
    </script>
</body>
</html>"""
    
    return html


def main():
    print("Loading results from database...")
    results = get_results()
    print(f"Found {len(results)} results")
    
    print("Generating HTML report...")
    html = generate_html(results)
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Report saved to: {OUTPUT_PATH.absolute()}")
    
    # Open in browser
    webbrowser.open(OUTPUT_PATH.absolute().as_uri())
    print("Opened in browser!")


if __name__ == "__main__":
    main()
