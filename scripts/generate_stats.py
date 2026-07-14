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

    first_date = days[0][0] if days else date.today()

    # Longest streak (track its start/end dates too)
    longest = 0
    longest_start = longest_end = None
    current_run = 0
    run_start = None
    for d, count in days:
        if count > 0:
            if current_run == 0:
                run_start = d
            current_run += 1
            if current_run > longest:
                longest = current_run
                longest_start = run_start
                longest_end = d
        else:
            current_run = 0

    # Current streak: walk backwards from today (or yesterday if today has no contributions yet)
    today = date.today()
    day_map = {d: c for d, c in days}
    current = 0
    cursor = today
    if day_map.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)
    last_active_day = cursor
    while day_map.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    return {
        "current": current,
        "longest": longest,
        "longest_start": longest_start,
        "longest_end": longest_end,
        "current_last_day": last_active_day if current > 0 else None,
        "first_date": first_date,
        "today": today,
    }


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


def fmt_date(d):
    return d.strftime("%b %-d, %Y") if d else ""


def fmt_short_date(d):
    return d.strftime("%b %-d") if d else ""


def render_svg(total_contribs, streak_info, top_langs):
    bg = "#0d1117"
    border = "#30363d"
    purple = "#c084fc"
    text_main = "#e6edf3"
    text_dim = "#8b949e"
    ring_color = "#39d353"
    flame_color = "#a855f7"
    blue = "#58a6ff"

    first_date_str = fmt_date(streak_info["first_date"])
    today_str = "Present"
    longest_range = f'{fmt_date(streak_info["longest_start"])} - {fmt_date(streak_info["longest_end"])}' if streak_info["longest"] > 0 else "—"
    current_last_day_str = fmt_short_date(streak_info["current_last_day"]) if streak_info["current"] > 0 else "—"

    current = streak_info["current"]
    longest = streak_info["longest"]

    # Top card: contributions / streak ring / longest streak
    top_card_height = 220
    top_card = f"""
  <rect x="0.5" y="0.5" width="669" height="{top_card_height}" rx="12" fill="{bg}" stroke="{border}"/>

  <line x1="223" y1="30" x2="223" y2="{top_card_height - 20}" stroke="{border}" stroke-width="1"/>
  <line x1="446" y1="30" x2="446" y2="{top_card_height - 20}" stroke="{border}" stroke-width="1"/>

  <text x="111" y="60" fill="{purple}" font-size="30" font-weight="700" font-family="Segoe UI, sans-serif" text-anchor="middle">{total_contribs:,}</text>
  <text x="111" y="85" fill="{text_main}" font-size="13" font-family="Segoe UI, sans-serif" text-anchor="middle">Total Contributions</text>
  <text x="111" y="103" fill="{text_dim}" font-size="11" font-family="Segoe UI, sans-serif" text-anchor="middle">{first_date_str} - {today_str}</text>

  <circle cx="335" cy="90" r="34" fill="none" stroke="{ring_color}" stroke-width="4"/>
  <text x="335" y="72" fill="{flame_color}" font-size="16" text-anchor="middle" font-family="Segoe UI, sans-serif">&#128293;</text>
  <text x="335" y="98" fill="{text_main}" font-size="22" font-weight="700" font-family="Segoe UI, sans-serif" text-anchor="middle">{current}</text>
  <text x="335" y="150" fill="{blue}" font-size="13" font-weight="600" font-family="Segoe UI, sans-serif" text-anchor="middle">Current Streak</text>
  <text x="335" y="168" fill="{text_dim}" font-size="11" font-family="Segoe UI, sans-serif" text-anchor="middle">{current_last_day_str}</text>

  <text x="558" y="60" fill="{purple}" font-size="30" font-weight="700" font-family="Segoe UI, sans-serif" text-anchor="middle">{longest}</text>
  <text x="558" y="85" fill="{text_main}" font-size="13" font-family="Segoe UI, sans-serif" text-anchor="middle">Longest Streak</text>
  <text x="558" y="103" fill="{text_dim}" font-size="11" font-family="Segoe UI, sans-serif" text-anchor="middle">{longest_range}</text>
"""

    # Bottom card: top languages
    lang_rows = ""
    y = 45
    for name, frac, color in top_langs:
        pct = round(frac * 100, 1)
        bar_width = int(frac * 590)
        lang_rows += f"""
        <text x="30" y="{y}" fill="{text_main}" font-size="12" font-family="Segoe UI, sans-serif">{name}</text>
        <text x="640" y="{y}" fill="{text_dim}" font-size="12" font-family="Segoe UI, sans-serif" text-anchor="end">{pct}%</text>
        <rect x="30" y="{y+8}" width="610" height="6" rx="3" fill="#21262d"/>
        <rect x="30" y="{y+8}" width="{bar_width}" height="6" rx="3" fill="{color}"/>
        """
        y += 36

    lang_card_height = y + 20
    lang_card_y = top_card_height + 16
    bottom_card = f"""
  <rect x="0.5" y="{lang_card_y}" width="669" height="{lang_card_height}" rx="12" fill="{bg}" stroke="{border}"/>
  <text x="30" y="{lang_card_y + 28}" fill="{text_main}" font-size="15" font-weight="600" font-family="Segoe UI, sans-serif">Top Languages</text>
  <g transform="translate(0, {lang_card_y})">
    {lang_rows}
  </g>
"""

    total_height = lang_card_y + lang_card_height + 10
    svg = f"""<svg width="670" height="{total_height}" viewBox="0 0 670 {total_height}" xmlns="http://www.w3.org/2000/svg">
{top_card}
{bottom_card}
</svg>"""
    return svg


def main():
    data = fetch_data()
    calendar = data["contributionsCollection"]["contributionCalendar"]
    total_contribs = calendar["totalContributions"]
    streak_info = compute_streaks(calendar["weeks"])
    top_langs = compute_top_languages(data["repositories"]["nodes"])

    svg = render_svg(total_contribs, streak_info, top_langs)

    os.makedirs("Assets", exist_ok=True)
    with open("Assets/stats.svg", "w") as f:
        f.write(svg)

    print(f"Wrote Assets/stats.svg — {total_contribs} contributions, streak {streak_info['current']}/{streak_info['longest']}")


if __name__ == "__main__":
    main()
