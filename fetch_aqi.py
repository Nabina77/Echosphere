import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import time

load_dotenv()
API_KEY = os.getenv("OPENAQ_API_KEY")
headers = {"X-API-Key": API_KEY}

# ── Common name shortcuts ──
NAME_SHORTCUTS = {
    "usa": "United States", "us": "United States", "america": "United States",
    "uk": "United Kingdom", "britain": "United Kingdom", "england": "United Kingdom",
    "uae": "United Arab Emirates", "korea": "South Korea",
    "vietnam": "Viet Nam", "russia": "Russian Federation",
    "nepal": "Nepal", "india": "India", "china": "China",
    "japan": "Japan", "germany": "Germany", "france": "France",
    "brazil": "Brazil", "canada": "Canada", "australia": "Australia",
    "pakistan": "Pakistan", "mexico": "Mexico", "indonesia": "Indonesia",
    "thailand": "Thailand", "nigeria": "Nigeria", "egypt": "Egypt",
    "kenya": "Kenya", "ghana": "Ghana", "bangladesh": "Bangladesh",
}

# ── STEP 1: Load all countries ──
def get_all_countries():
    print("🌍 Loading countries from OpenAQ...")
    all_countries = {}
    for page in range(1, 4):
        try:
            r = requests.get(
                "https://api.openaq.org/v3/countries",
                headers=headers,
                params={"limit": 100, "page": page},
                timeout=15
            )
            if r.status_code != 200:
                break
            results = r.json().get("results", [])
            if not results:
                break
            for c in results:
                name = c.get("name", "")
                cid  = c.get("id")
                if name and cid:
                    all_countries[name] = cid
        except Exception as e:
            print(f"   ⚠️ Error loading page {page}: {e}")
            break
    print(f"✅ Loaded {len(all_countries)} countries!")
    return all_countries

COUNTRY_MAP = get_all_countries()

# ── STEP 2: Extract clean city name ──
def get_city_name(loc):
    # Try locality first
    city = loc.get("locality")
    if city and str(city) not in ["nan", "None", "null", "N/A", "n/a", ""]:
        return str(city)

    # Use station name as city fallback
    station = loc.get("name", "Unknown Station")

    # Clean up station name to extract city
    # Remove common prefixes like "US Embassy", "WHO", etc.
    city_keywords = [
        "Kathmandu", "Pokhara", "Lalitpur", "Bhaktapur", "Birgunj",
        "Biratnagar", "Butwal", "Dharan", "Hetauda", "Nepalgunj",
        "Delhi", "Mumbai", "Kolkata", "Chennai", "Bangalore",
        "Beijing", "Shanghai", "Guangzhou", "Shenzhen",
        "London", "Manchester", "Birmingham",
        "New York", "Los Angeles", "Chicago", "Houston",
        "Tokyo", "Osaka", "Kyoto",
        "Berlin", "Munich", "Hamburg",
        "Paris", "Lyon", "Marseille",
        "Sydney", "Melbourne", "Brisbane",
        "Toronto", "Vancouver", "Montreal",
        "Dubai", "Abu Dhabi",
        "Bangkok", "Chiang Mai",
        "Jakarta", "Surabaya",
        "Seoul", "Busan",
        "Cairo", "Alexandria",
        "Lagos", "Abuja",
        "Nairobi", "Mombasa",
        "Karachi", "Lahore", "Islamabad",
    ]

    for keyword in city_keywords:
        if keyword.lower() in station.lower():
            return keyword

    # Return station name if no city found
    return station

# ── STEP 3: Get sensor measurements with retry ──
def get_sensor_data(sensor_id, param, loc, country_name, city):
    data = []
    for endpoint in ["hours", "days", "measurements"]:
        if endpoint == "hours":
            params = {
                "date_from": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "date_to":   datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 24
            }
        else:
            params = {
                "date_from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "date_to":   datetime.now().strftime("%Y-%m-%d"),
                "limit": 7
            }

        try:
            time.sleep(0.2)  # avoid rate limiting
            url = f"https://api.openaq.org/v3/sensors/{sensor_id}/{endpoint}"
            r3  = requests.get(url, headers=headers, params=params, timeout=10)
            measurements = r3.json().get("results", [])

            if measurements:
                for m in measurements:
                    try:
                        date = (
                            m.get("period", {}).get("datetimeFrom", {}).get("utc") or
                            m.get("date", {}).get("utc") or
                            m.get("datetime", {}).get("utc") or
                            "Unknown"
                        )
                        value = m.get("value", 0)
                        if value and 0 < float(value) < 500:
                            data.append({
                                "country":   str(country_name),
                                "city":      str(city),
                                "station":   str(loc["name"]),
                                "parameter": str(param),
                                "value":     float(value),
                                "date":      str(date),
                                "source":    endpoint
                            })
                    except Exception:
                        pass
                break
        except Exception as e:
            print(f"      ⚠️ Retry error on {endpoint}: {e}")
            time.sleep(1)
            continue

    return data

# ── STEP 4: Fetch country AQI — each city separately ──
def fetch_country_aqi(country_name, country_id):
    print(f"\n📡 Fetching data for {country_name}...")

    try:
        r = requests.get(
            "https://api.openaq.org/v3/locations",
            headers=headers,
            params={"countries_id": country_id, "limit": 20},
            timeout=15
        )
    except Exception as e:
        print(f"   ❌ Connection error: {e}")
        return None

    if r.status_code != 200:
        print(f"   ❌ API error: {r.status_code}")
        return None

    locations = r.json().get("results", [])
    if not locations:
        print(f"   ⚠️ No stations found for {country_name}")
        return None

    print(f"   ✅ Found {len(locations)} stations")

    # Group stations by city
    city_stations = {}
    for loc in locations:
        city = get_city_name(loc)
        if city not in city_stations:
            city_stations[city] = []
        city_stations[city].append(loc)

    print(f"   🏙️  Cities: {list(city_stations.keys())}")

    all_data = []
    for city, stations in city_stations.items():
        for loc in stations:
            station_id = loc["id"]
            try:
                time.sleep(0.3)
                r2 = requests.get(
                    f"https://api.openaq.org/v3/locations/{station_id}/sensors",
                    headers=headers,
                    timeout=10
                )
                sensors = r2.json().get("results", [])
            except Exception as e:
                print(f"   ⚠️ Skipping station {loc['name']}: {e}")
                continue

            for sensor in sensors:
                param = sensor["parameter"]["name"]
                if param not in ["pm25", "pm10", "no2"]:
                    continue
                sensor_id = sensor["id"]
                all_data.extend(
                    get_sensor_data(sensor_id, param, loc, country_name, city)
                )

    return all_data

# ── STEP 5: Display each city separately ──
def display_aqi(country_name, data):
    if not data:
        print(f"\n❌ No data available for {country_name}")
        return

    df = pd.DataFrame(data)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["city"]  = df["city"].fillna("Unknown").astype(str)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df[(df["value"] > 0) & (df["value"] < 500)]

    if df.empty:
        print(f"\n❌ No valid data for {country_name}")
        return

    source       = df["source"].iloc[0] if "source" in df.columns else "days"
    period_label = "Last 24 hours (Hourly ⚡)" if source == "hours" else "Last 7 days"

    print(f"\n{'='*52}")
    print(f"🌍 AQI Report: {country_name}")
    print(f"{'='*52}")
    print(f"📅 Period : {period_label}")
    print(f"{'─'*52}")

    # Show each city separately
    cities = df["city"].unique()
    city_summaries = []

    for city in cities:
        city_df = df[df["city"] == city]

        pm25 = city_df[city_df["parameter"] == "pm25"]
        pm10 = city_df[city_df["parameter"] == "pm10"]
        no2  = city_df[city_df["parameter"] == "no2"]

        pm25_avg = round(pm25["value"].mean(), 2) if not pm25.empty else None
        pm10_avg = round(pm10["value"].mean(), 2) if not pm10.empty else None
        no2_avg  = round(no2["value"].mean(), 2)  if not no2.empty  else None

        print(f"\n🏙️  {city}")
        print(f"   {'─'*42}")

        if pm25_avg:
            status = "❌ UNSAFE" if pm25_avg > 15 else "✅ SAFE"
            bar    = "█" * min(int(pm25_avg / 8), 15)
            print(f"   💨 PM2.5 : {pm25_avg:6.2f} µg/m³  {status}  {bar}")
            city_summaries.append({"city": city, "pm25": pm25_avg})
        else:
            print(f"   💨 PM2.5 : No data")

        if pm10_avg:
            status = "❌ UNSAFE" if pm10_avg > 45 else "✅ SAFE"
            print(f"   🌫️  PM10  : {pm10_avg:6.2f} µg/m³  {status}")

        if no2_avg:
            status = "❌ UNSAFE" if no2_avg > 25 else "✅ SAFE"
            print(f"   🏭 NO2   : {no2_avg:6.2f} µg/m³  {status}")

    # City ranking
    if len(city_summaries) > 1:
        print(f"\n{'─'*52}")
        print(f"🏆 City Ranking (worst → best PM2.5):")
        ranked = sorted(city_summaries, key=lambda x: x["pm25"], reverse=True)
        for i, c in enumerate(ranked, 1):
            status = "❌" if c["pm25"] > 15 else "✅"
            bar    = "█" * min(int(c["pm25"] / 8), 15)
            print(f"   {i}. {c['city']:<25} {c['pm25']:6.2f} µg/m³  {status}  {bar}")

    print(f"\n{'─'*52}")
    print(f"⚠️  WHO Limits: PM2.5=15 | PM10=45 | NO2=25 µg/m³")

    # Save
    os.makedirs("data", exist_ok=True)
    filename = f"data/{country_name.lower().replace(' ', '_')}_aqi.csv"
    df.to_csv(filename, index=False)
    print(f"✅ Saved → {filename}")
    print(f"{'='*52}")

# ── STEP 6: Search by country ──
def search_country(query):
    normalized = NAME_SHORTCUTS.get(query.lower(), query)
    matches = {
        name: cid for name, cid in COUNTRY_MAP.items()
        if normalized.lower() in name.lower()
    }
    if not matches:
        print(f"\n❌ '{query}' not found!")
        print("💡 Try: Nepal, India, China, usa, uk, germany...")
        return

    exact        = {n: c for n, c in matches.items() if n.lower() == normalized.lower()}
    chosen       = exact if exact else matches
    country_name = list(chosen.keys())[0]
    country_id   = chosen[country_name]

    print(f"✅ Found: {country_name} (ID: {country_id})")
    data = fetch_country_aqi(country_name, country_id)
    display_aqi(country_name, data)

# ── STEP 7: Auto fetch top countries ──
def auto_fetch_all():
    print("\n🌍 Auto-fetching top 20 countries...")
    countries = [
        "nepal", "india", "china", "usa", "uk",
        "germany", "japan", "france", "brazil", "australia",
        "canada", "pakistan", "indonesia", "thailand",
        "korea", "nigeria", "egypt", "kenya", "mexico", "bangladesh"
    ]
    for c in countries:
        print(f"\n── Fetching {c}...")
        search_country(c)
        time.sleep(1)
    print("\n✅ All countries fetched!")

# ── STEP 8: Main loop ──
def main():
    print("=" * 52)
    print("🌿 ECOSPHERE — Global AQI Search by City")
    print("=" * 52)
    print("Commands:")
    print("  [country] → search country + all its cities")
    print("  auto      → fetch top 20 countries")
    print("  list      → show all countries")
    print("  quit      → exit")

    while True:
        print("\n" + "─" * 52)
        query = input("🔍 Search country: ").strip()

        if not query:
            print("⚠️ Please enter a country name!")
        elif query.lower() == "quit":
            print("👋 Goodbye!")
            break
        elif query.lower() == "auto":
            auto_fetch_all()
        elif query.lower() == "list":
            print(f"\n🌍 {len(COUNTRY_MAP)} countries available:")
            for i, name in enumerate(sorted(COUNTRY_MAP.keys()), 1):
                print(f"  {i:3}. {name}")
        else:
            search_country(query)

if __name__ == "__main__":
    main()