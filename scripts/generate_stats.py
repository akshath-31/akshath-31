"""
Generates a self-hosted GitHub stats SVG card.
Reads GITHUB_TOKEN and GH_USERNAME from environment variables.
Writes the result to Assets/stats.svg
"""

import os
import requests
from datetime import date, timedelta

TOKEN = os.environ["STATS_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]

HEADERS = {"Authorization": f"bearer {TOKEN}"}

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""


def fetch_data():
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": GRAPHQL_QUERY, "variables": {"login": USERNAME}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]["user"]


def compute_streaks(weeks):
    days = []
    for week in weeks:
        for d in week["contributionDays"]:
            days.append((date.fromisoformat(d["date"]), d["contributionCount"]))
    days.sort(key=lambda x: x[0])

    # Longest streak
    longest = 0
    current_run = 0
    for _, count in days:
        if count > 0:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 0

    # Current streak: walk backwards from today (or yesterday if today has no contributions yet)
    today = date.today()
    day_map = {d: c for d, c in days}
    current = 0
    cursor = today
    # allow today to be a zero-contribution day without breaking the streak (day not finished yet)
    if day_map.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)
    while day_map.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    return current, longest


def compute_top_languages(repos):
    totals = {}
    colors = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#858585"
    ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]
    total_size = sum(v for _, v in ranked) or 1
    return [(name, size / total_size, colors[name]) for name, size in ranked]


def render_svg(total_contribs, current_streak, longest_streak, top_langs):
    bg = "#1a1b27"
    border = "#2e2f3e"
    accent = "#7aa2f7"
    text_main = "#c0caf5"
    text_dim = "#565f89"

    lang_rows = ""
    y = 235
    for name, frac, color in top_langs:
        pct = round(frac * 100, 1)
        bar_width = int(frac * 300)
        lang_rows += f"""
        <text x="30" y="{y}" fill="{text_main}" font-size="12" font-family="Segoe UI, sans-serif">{name}</text>
        <text x="440" y="{y}" fill="{text_dim}" font-size="12" font-family="Segoe UI, sans-serif" text-anchor="end">{pct}%</text>
        <rect x="30" y="{y+8}" width="410" height="6" rx="3" fill="#292a3a"/>
        <rect x="30" y="{y+8}" width="{bar_width}" height="6" rx="3" fill="{color}"/>
        """
        y += 34

    svg = f"""<svg width="470" height="{y+20}" viewBox="0 0 470 {y+20}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0.5" y="0.5" width="469" height="{y+19}" rx="12" fill="{bg}" stroke="{border}"/>
  <text x="30" y="40" fill="{text_main}" font-size="18" font-weight="600" font-family="Segoe UI, sans-serif">GitHub Stats</text>

  <text x="30" y="90" fill="{accent}" font-size="26" font-weight="700" font-family="Segoe UI, sans-serif">{total_contribs}</text>
  <text x="30" y="112" fill="{text_dim}" font-size="12" font-family="Segoe UI, sans-serif">Total Contributions</text>

  <text x="180" y="90" fill="{accent}" font-size="26" font-weight="700" font-family="Segoe UI, sans-serif">{current_streak}</text>
  <text x="180" y="112" fill="{text_dim}" font-size="12" font-family="Segoe UI, sans-serif">Current Streak</text>

  <text x="330" y="90" fill="{accent}" font-size="26" font-weight="700" font-family="Segoe UI, sans-serif">{longest_streak}</text>
  <text x="330" y="112" fill="{text_dim}" font-size="12" font-family="Segoe UI, sans-serif">Longest Streak</text>

  <line x1="30" y1="140" x2="440" y2="140" stroke="{border}" stroke-width="1"/>

  <text x="30" y="170" fill="{text_main}" font-size="15" font-weight="600" font-family="Segoe UI, sans-serif">Top Languages</text>
  {lang_rows}
</svg>"""
    return svg


def main():
    data = fetch_data()
    calendar = data["contributionsCollection"]["contributionCalendar"]
    total_contribs = calendar["totalContributions"]
    current_streak, longest_streak = compute_streaks(calendar["weeks"])
    top_langs = compute_top_languages(data["repositories"]["nodes"])

    svg = render_svg(total_contribs, current_streak, longest_streak, top_langs)

    os.makedirs("Assets", exist_ok=True)
    with open("Assets/stats.svg", "w") as f:
        f.write(svg)

    print(f"Wrote Assets/stats.svg — {total_contribs} contributions, streak {current_streak}/{longest_streak}")


if __name__ == "__main__":
    main()
