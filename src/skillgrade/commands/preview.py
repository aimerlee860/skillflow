"""Preview command module."""

from __future__ import annotations

import json
from pathlib import Path


def run_preview(
    results_dir: Path | None = None,
    mode: str = "cli",
    port: int = 3847,
) -> None:
    """Preview evaluation results.

    Args:
        results_dir: Directory containing result JSON files
        mode: Preview mode - 'cli' or 'browser'
        port: Port for browser preview (default: 3847)
    """
    if results_dir is None:
        import tempfile

        results_dir = Path(tempfile.gettempdir()) / "skillgrade"

    results_dir = results_dir.resolve()

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        print("Run 'skillgrade smoke' first to generate results.")
        return

    json_files = sorted(results_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not json_files:
        print(f"No results found in {results_dir}")
        print("Run 'skillgrade smoke' first to generate results.")
        return

    if mode == "cli":
        _run_cli_preview(json_files)
    elif mode == "browser":
        _run_browser_preview(results_dir, port)
    else:
        print(f"Unknown preview mode: {mode}")


def _run_cli_preview(json_files: list[Path]) -> None:
    """Run CLI preview of results."""
    print(f"\n{'=' * 60}")
    print("SKILLGRADE RESULTS")
    print(f"{'=' * 60}\n")

    for json_file in json_files:
        try:
            report = json.loads(json_file.read_text())

            print(f"Task: {report.get('taskName', 'unknown')}")
            print(f"Pass Rate: {report.get('passRate', 0):.2%}")
            print(f"Pass@K:   {report.get('passAtK', 0):.4f}")
            print(f"Pass^K:   {report.get('passPowK', 0):.4f}")
            print(f"Trials:   {len(report.get('trials', []))}")
            print(f"Timestamp: {report.get('timestamp', 'N/A')}")
            print()

            for i, trial in enumerate(report.get("trials", [])):
                reward = trial.get("reward", 0)
                status = "✓" if reward >= 0.5 else "✗"
                print(f"  Trial {i + 1}: {status} {reward:.2%}")

                for grader in trial.get("graders", []):
                    score = grader.get("score", 0)
                    details = grader.get("details", "")
                    gtype = grader.get("graderType", "unknown")
                    print(f"    - {gtype}: {score:.2%} ({details})")

            print("-" * 60)
            print()

        except Exception as e:
            print(f"Error reading {json_file}: {e}\n")


def _run_browser_preview(results_dir: Path, port: int) -> None:
    """Start a browser preview server."""
    import http.server
    import socketserver
    import threading
    import webbrowser

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Skillgrade Results</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        .report {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
        .report h2 {{ margin-top: 0; }}
        .metric {{ display: inline-block; margin-right: 24px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ color: #666; font-size: 12px; }}
        .pass {{ color: #22c55e; }}
        .fail {{ color: #ef4444; }}
        .trial {{ margin-left: 16px; padding: 8px; border-left: 2px solid #eee; }}
    </style>
</head>
<body>
    <h1>Skillgrade Results</h1>
    <div id="results">Loading...</div>
    <script>
    async function loadResults() {{
        const response = await fetch('file://{results_dir}/*.json'.replace('*', 'report'));
        const reports = [];
        // Load all JSON files from directory listing
        const container = document.getElementById('results');
        
        fetch('http://localhost:{port}/files')
            .then(r => r.json())
            .then(files => {{
                container.innerHTML = '';
                files.forEach(file => {{
                    fetch(file.url)
                        .then(r => r.json())
                        .then(report => {{
                            const div = document.createElement('div');
                            div.className = 'report';
                            div.innerHTML = `
                                <h2>${{report.taskName}}</h2>
                                <div class="metric">
                                    <div class="metric-value ${{report.passRate >= 0.8 ? 'pass' : 'fail'}}">${{(report.passRate * 100).toFixed(1)}}%</div>
                                    <div class="metric-label">Pass Rate</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">${{report.passAtK.toFixed(4)}}</div>
                                    <div class="metric-label">Pass@K</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">${{report.passPowK.toFixed(4)}}</div>
                                    <div class="metric-label">Pass^K</div>
                                </div>
                                <p>Trials: ${{report.trials.length}} | Avg Time: ${{(report.avgDurationMs/1000).toFixed(1)}}s</p>
                            `;
                            container.appendChild(div);
                        }});
                }});
            }});
    }}
    loadResults();
    </script>
</body>
</html>
"""

    html_file = results_dir / "preview.html"
    html_file.write_text(html_content)

    url = f"http://localhost:{port}"
    print(f"Starting browser preview at {url}")
    print(f"Open the URL in your browser to view results.")
    print(f"Results directory: {results_dir}")

    webbrowser.open(url)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(results_dir), **kwargs)

    with socketserver.TCPServer(("", port), Handler) as httpd:
        httpd.serve_forever()
