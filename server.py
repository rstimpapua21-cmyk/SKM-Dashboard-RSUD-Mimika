#!/usr/bin/env python3
"""
SKM Dashboard Server — Pre-computes SKM metrics and serves lightweight JSON API.
No need to send 12K+ raw rows to client — server does all analysis.
"""
import http.server
import json
import urllib.request
import os
import sys
import webbrowser
import threading
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

PORT = 8000
PUB_CSV_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTEKRFBkIZHy-c8Es94dcyMg43OocyUvcOFJgB8i0zpjLALZdG4cjJzohb0jzdPZs6cqubhVnkLI1NL/pub?output=csv'
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))
cached_metrics = None
last_fetch_time = None
FETCH_INTERVAL = 300

SKM_SCALE = {'A':(3.51,4.00,'Sangat Baik'),'B':(3.01,3.50,'Baik'),'C':(2.51,3.00,'Cukup'),'D':(2.00,2.50,'Kurang')}
RATING_MAP = {'a':1,'b':2,'c':3,'d':4,'e':5}

def extract_rating(text):
    if isinstance(text, (int, float)) and 1 <= text <= 5: return text
    if not text or not isinstance(text, str): return None
    t = text.strip().lower()
    if not t: return None
    if t[0] in RATING_MAP and (len(t)==1 or t[1] in '. '): return RATING_MAP[t[0]]
    try:
        v = int(t)
        if 1 <= v <= 5: return v
    except: pass
    return None

def parse_csv(csv_text):
    lines = csv_text.split('\n')
    def parse_line(line):
        fields = []; i = 0; field = ''; in_q = False
        while i < len(line):
            ch = line[i]
            if in_q:
                if ch == '"' and i+1 < len(line) and line[i+1] == '"': field += '"'; i += 2
                elif ch == '"': in_q = False; i += 1
                else: field += ch; i += 1
            else:
                if ch == '"': in_q = True; i += 1
                elif ch == ',': fields.append(field.strip()); field = ''; i += 1
                else: field += ch; i += 1
        fields.append(field.strip())
        return fields

    headers = parse_line(lines[0])
    # Identify columns
    question_cols = [i for i, h in enumerate(headers) if h and len(h) > 2 and h[0].isdigit() and h[1] == '.']
    sub_cols = [i for i, h in enumerate(headers) if h and len(h) > 2 and h[0] in 'abcde' and h[1] == '.']

    rows = []
    for r in range(1, len(lines)):
        line = lines[r].strip()
        if not line: continue
        vals = parse_line(line)
        row = {}
        has_rating = False
        for i, h in enumerate(headers):
            v = vals[i] if i < len(vals) else ''
            if i in question_cols:
                rating = extract_rating(v)
                if rating is not None:
                    row[h] = rating
                    has_rating = True
                else:
                    row[h] = v
            else:
                row[h] = v
        if has_rating:
            rows.append(row)

    return headers, rows, [headers[i] for i in question_cols]


def compute_metrics(headers, rows, question_cols):
    """Pre-compute all SKM metrics for dashboard."""
    ts = datetime.now().strftime('%H:%M:%S')

    # Determine max rating
    all_ratings = []
    for r in rows:
        for c in question_cols:
            v = r.get(c)
            if isinstance(v, (int, float)) and v > 0: all_ratings.append(v)
    max_rating = 4
    if all_ratings:
        mx = max(all_ratings)
        max_rating = 4 if mx <= 4 else min(int(mx), 5)

    # NPU per question
    npu = {}
    for c in question_cols:
        vals = [r[c] for r in rows if isinstance(r.get(c), (int, float)) and r[c] > 0]
        npu[c] = sum(vals)/len(vals) if vals else 0

    # IKM
    npu_vals = [v for v in npu.values() if v > 0]
    ikm = sum(npu_vals)/len(npu_vals) if npu_vals else 0

    # Quality grade
    quality_grade = 'D'
    for g, (lo, hi, label) in SKM_SCALE.items():
        if lo <= ikm <= hi: quality_grade = g; break
    if ikm > 4.0: quality_grade = 'A'

    # Distribution per question
    distribution = {}
    for c in question_cols:
        distribution[c] = {}
        for i in range(1, max_rating+1): distribution[c][i] = 0
        for r in rows:
            v = r.get(c)
            if isinstance(v, (int, float)) and 1 <= v <= max_rating: distribution[c][int(v)] += 1

    # Group analysis (Unit column)
    group_analysis = {}
    unit_col = 'Unit' if 'Unit' in headers else None
    if unit_col:
        units = sorted(set(r.get(unit_col, '') for r in rows if r.get(unit_col, '') and str(r.get(unit_col, '')).strip()))
        for unit in units:
            g_rows = [r for r in rows if str(r.get(unit_col, '')).strip() == unit]
            g_npu = {}
            for c in question_cols:
                vals = [r[c] for r in g_rows if isinstance(r.get(c), (int, float)) and r[c] > 0]
                g_npu[c] = sum(vals)/len(vals) if vals else 0
            g_vals = [v for v in g_npu.values() if v > 0]
            g_ikm = sum(g_vals)/len(g_vals) if g_vals else 0
            g_grade = 'D'
            for g, (lo, hi, label) in SKM_SCALE.items():
                if lo <= g_ikm <= hi: g_grade = g; break
            if g_ikm > 4: g_grade = 'A'
            group_analysis[unit] = {'ikm': round(g_ikm, 3), 'npu': {short_name(c): round(v, 3) for c, v in g_npu.items()}, 'count': len(g_rows), 'grade': g_grade}

    # Trend (by date)
    trend = []
    ts_col = headers[0] if headers else None  # Timestamp
    if ts_col and rows:
        by_date = {}
        for r in rows:
            d_raw = r.get(ts_col, '')
            if not d_raw: continue
            try:
                from datetime import datetime as dt
                # Try parsing the timestamp
                d = dt.strptime(str(d_raw).split('.')[0], '%m/%d/%Y %H:%M:%S')
                d_key = d.strftime('%Y-%m')
            except:
                try:
                    d = dt.strptime(str(d_raw), '%Y-%m-%dT%H:%M:%S')
                    d_key = d.strftime('%Y-%m')
                except:
                    d_key = str(d_raw)[:7] if len(str(d_raw)) >= 7 else str(d_raw)
            if d_key not in by_date: by_date[d_key] = []
            by_date[d_key].append(r)

        for d_key in sorted(by_date.keys()):
            d_rows = by_date[d_key]
            d_npu = {}
            for c in question_cols:
                vals = [r[c] for r in d_rows if isinstance(r.get(c), (int, float)) and r[c] > 0]
                d_npu[c] = sum(vals)/len(vals) if vals else 0
            d_vals = [v for v in d_npu.values() if v > 0]
            d_ikm = sum(d_vals)/len(d_vals) if d_vals else 0
            trend.append({'date': d_key, 'ikm': round(d_ikm, 3), 'count': len(d_rows)})

    # Short names for questions
    q_short = {c: short_name(c) for c in question_cols}

    # Respondent demographics
    demographics = {}
    demo_cols = ['Jenis Kelamin', 'Pendidikan', 'Pekerjaan']
    for col in demo_cols:
        if col in headers:
            vals = {}
            for r in rows:
                v = str(r.get(col, '')).strip()
                if v: vals[v] = vals.get(v, 0) + 1
            demographics[col] = vals

    metrics = {
        'totalRespondents': len(rows),
        'ikm': round(ikm, 3),
        'qualityGrade': quality_grade,
        'qualityLabel': SKM_SCALE.get(quality_grade, (0, 0, 'Sangat Baik'))[2],
        'maxRating': max_rating,
        'ikmPercent': round(ikm / max_rating * 100, 1),
        'npu': {short_name(c): round(v, 3) for c, v in npu.items()},
        'npuRaw': {c: round(v, 3) for c, v in npu.items()},
        'distribution': {short_name(c): v for c, v in distribution.items()},
        'questionCols': question_cols,
        'questionShort': q_short,
        'groupAnalysis': group_analysis,
        'trend': trend,
        'demographics': demographics,
    }

    print(f"  [{ts}] Metrics computed: IKM={ikm:.3f}, Grade={quality_grade}, Rows={len(rows)}")
    return metrics


def short_name(col):
    """Shorten SKM question column name."""
    s = col.strip()
    # Remove number prefix: "1. " -> ""
    if s and s[0].isdigit() and '.' in s[:3]:
        s = s[s.index('.')+1:].strip()
    # Remove "Bagaimana pendapat Bapak/Ibu tentang" prefix
    for prefix in ['Bagaimana pendapat Bapak/Ibu tentang ', 'Bagaimana pendapat Bapak/Ibu tentang kesesuaian ']:
        if s.startswith(prefix): s = s[len(prefix):]
    # Truncate
    if len(s) > 50: s = s[:47] + '...'
    return s


def fetch_and_compute():
    """Fetch CSV from Google Sheets and pre-compute all metrics."""
    global cached_metrics, last_fetch_time

    ts = datetime.now().strftime('%H:%M:%S')
    print(f"  [{ts}] Fetching CSV...")
    try:
        req = urllib.request.Request(PUB_CSV_URL, headers={
            'User-Agent': 'Mozilla/5.0 SKM-Dashboard',
            'Accept': 'text/csv',
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            csv_text = resp.read().decode('utf-8')
            if len(csv_text) < 100:
                print(f"  [{ts}] Empty response")
                return None

            headers, rows, question_cols = parse_csv(csv_text)
            if not rows:
                print(f"  [{ts}] No valid rows")
                return None

            print(f"  [{ts}] Parsed {len(rows)} valid rows, {len(question_cols)} questions")
            cached_metrics = compute_metrics(headers, rows, question_cols)
            last_fetch_time = datetime.now().isoformat()
            return cached_metrics
    except Exception as e:
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"  [{ts}] Fetch error: {type(e).__name__}: {e}")
        return None


def auto_refresh():
    import time
    while True:
        time.sleep(FETCH_INTERVAL)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-refresh...")
        fetch_and_compute()


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path == '/' or path == '/dashboard':
            return os.path.join(SERVE_DIR, 'SKM Dashboard RSUD Mimika.html')
        resolved = os.path.normpath(os.path.join(SERVE_DIR, path.lstrip('/')))
        if not resolved.startswith(SERVE_DIR):
            return os.path.join(SERVE_DIR, 'index.html')
        return resolved

    def do_GET(self):
        if self.path == '/api/metrics':
            self.handle_metrics()
        elif self.path == '/api/refresh':
            self.handle_refresh()
        else:
            super().do_GET()

    def handle_metrics(self):
        if cached_metrics is None:
            result = fetch_and_compute()
            if result is None:
                self.send_json({'status':'error','message':'Failed to fetch data'}, 503)
                return
        self.send_json({'status':'ok', 'method':'server-proxy', 'last_update':last_fetch_time, **cached_metrics})

    def handle_refresh(self):
        result = fetch_and_compute()
        if result:
            self.send_json({'status':'ok','message':f'Refreshed - {cached_metrics["totalRespondents"]} rows','last_update':last_fetch_time, **cached_metrics})
        else:
            self.send_json({'status':'error','message':'Refresh failed'}, 503)

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:%d' % PORT)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress verbose HTTP logs


def main():
    print("=" * 55)
    print("  SKM Dashboard Server - RSUD Mimika")
    print("=" * 55)
    print(f"  Port: {PORT}  Dir: {SERVE_DIR}")
    print()

    print("Fetching & computing SKM metrics...")
    result = fetch_and_compute()
    if result:
        print(f"  IKM: {result['ikm']} ({result['qualityGrade']} - {result['qualityLabel']})")
        print(f"  Respondents: {result['totalRespondents']}")
        print(f"  Questions: {len(result['questionCols'])}")
        for q in result['questionCols'][:5]:
            print(f"    - {q[:55]}")
        print(f"  Units: {len(result['groupAnalysis'])}")
    else:
        print("  Initial fetch failed")
    print()

    threading.Thread(target=auto_refresh, daemon=True).start()

    server = http.server.HTTPServer(('127.0.0.1', PORT), DashboardHandler)
    print(f"  http://localhost:{PORT}/  (Dashboard)")
    print(f"  http://localhost:{PORT}/api/metrics  (JSON)")
    print("  Ctrl+C to stop")
    print()

    webbrowser.open(f'http://localhost:{PORT}/')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.server_close()


if __name__ == '__main__':
    main()
