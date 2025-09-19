import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, date, timedelta
import re
from dateutil import parser as dateparser
from ics import Calendar, Event

# -------------------------
# Helper: parse "September 11, 2025" from text
# -------------------------
def parse_date_from_text(text):
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if match:
        try:
            return dateparser.parse(match.group(1)).date().isoformat()
        except:
            return None
    return None

# -------------------------
# Scrapers
# -------------------------

def scrape_emerald_guild():
    url = "https://emeraldguild.org/events/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    for ev in soup.select("div.tribe-events-calendar-list__event-row"):
        title_el = ev.select_one("h3 a")
        date_el = ev.select_one("time")

        title = title_el.get_text(strip=True) if title_el else "Event"
        link = title_el["href"] if title_el else url
        date = (
            date_el["datetime"].split("T")[0]
            if date_el and date_el.has_attr("datetime")
            else None
        )

        # Drill into detail page for location
        location = "N/A"
        if link:
            try:
                detail_html = requests.get(link).text
                detail_soup = BeautifulSoup(detail_html, "html.parser")
                loc_el = detail_soup.select_one(
                    "div.tribe-events-venue-details, "
                    "div.tribe-events-calendar-list__event-venue, "
                    "span.tribe-address"
                )
                if loc_el:
                    location = loc_el.get_text(" ", strip=True)
            except Exception as ex:
                print(f"⚠️ Could not fetch Emerald Guild location: {ex}")

        events.append({
            "club": "Emerald Guild",
            "title": title,
            "location": location,
            "date": date,
            "source_url": link
        })
    return events


def scrape_ibma():
    url = "https://www.ibmanyc.com/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text(" ", strip=True)
    date = parse_date_from_text(text)

    return [{
        "club": "Illyrian BMA",
        "title": "Monthly Meeting",
        "location": "St. Pats Bar & Grill, 22 West 46th Street, New York, NY",
        "date": date,
        "source_url": url
    }]


def scrape_nybma():
    url = "https://nybma.org/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text(" ", strip=True)
    date = parse_date_from_text(text)

    return [{
        "club": "NYBMA",
        "title": "Business Meeting",
        "location": "Connolly’s Pub & Restaurant, 121 West 45th St, New York, NY 10036",
        "date": date,
        "source_url": url
    }]

# -------------------------
# Manhattan Resident Managers Club (first Thursday logic)
# -------------------------
def first_thursday(year, month):
    d = date(year, month, 1)
    while d.weekday() != 3:  # 3 = Thursday
        d += timedelta(days=1)
    return d

def scrape_mrmclub():
    url = "http://mrmclub.com/news-events/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    # Generate Oct 2025 – Jun 2026
    months = [
        (2025, 10), (2025, 11), (2025, 12),
        (2026, 1), (2026, 2), (2026, 3),
        (2026, 4), (2026, 5), (2026, 6),
    ]

    for year, month in months:
        d = first_thursday(year, month)
        events.append({
            "club": "Manhattan Resident Managers Club",
            "title": "Monthly Meeting",
            "location": "Connolly’s Pub & Restaurant, 121 West 45th St, New York, NY 10036",
            "date": d.isoformat(),
            "source_url": "https://mrmclub.com/"
        })
    return events

# -------------------------
# Main runner
# -------------------------

if __name__ == "__main__":
    all_events = []
    all_events.extend(scrape_emerald_guild())
    all_events.extend(scrape_ibma())
    all_events.extend(scrape_nybma())
    all_events.extend(scrape_mrmclub())

    df = pd.DataFrame(all_events)

    # Filter out past events
    today = date.today().isoformat()
    df = df[df["date"].notna() & (df["date"] >= today)]

    # Save CSV
    df.to_csv("events.csv", index=False)

    # Save HTML report
    with open("report.html", "w") as f:
        f.write("<h2>Upcoming NYC Property Manager Meetings</h2>\n<ul>\n")
        for _, row in df.iterrows():
            f.write("<li>\n")
            f.write(f"<b>{row['club']}</b> — {row['date']}<br>\n")
            f.write(f"Title: {row['title']}<br>\n")
            f.write(f"Location: {row['location']}<br>\n")
            f.write(f"Link: <a href='{row['source_url']}' target='_blank'>{row['source_url']}</a>\n")
            f.write("</li><br>\n")
        f.write("</ul>\n")

    # Save ICS calendar file
    cal = Calendar()
    for _, row in df.iterrows():
        try:
            e = Event()
            e.name = f"{row['club']} — {row['title']}"
            e.begin = row["date"]
            if row["location"] != "N/A":
                e.location = row["location"]
            if row["source_url"]:
                e.url = row["source_url"]
            cal.events.add(e)
        except Exception as ex:
            print(f"⚠️ Could not add event: {ex}")

    with open("events.ics", "w") as f:
        f.writelines(cal)

    print("✅ Scraping complete. See events.csv, report.html, and events.ics")
