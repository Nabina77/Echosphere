import pandas as pd

print("🌍 Downloading global CO2 data...")
url = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
df = pd.read_csv(url)
print(f"✅ Downloaded! Total rows: {len(df)}")

# Save full dataset locally so we don't download every time
df.to_csv("data/global_co2.csv", index=False)
print("✅ Saved to data/global_co2.csv")

# ── LIST ALL AVAILABLE COUNTRIES ──
all_countries = df['country'].unique()
print(f"\n🌍 Total countries available: {len(all_countries)}")

# ── SEARCH ANY COUNTRY FUNCTION ──
def search_country(country_name):
    # Find matching countries (case insensitive)
    matches = [c for c in all_countries if country_name.lower() in c.lower()]
    
    if not matches:
        print(f"\n❌ No country found matching '{country_name}'")
        print("💡 Try a different spelling")
        return None
    
    if len(matches) > 1:
        print(f"\n🔍 Multiple matches found: {matches}")
        print(f"Using: {matches[0]}")
    
    country = matches[0]
    data = df[df['country'] == country][[
        'year', 'co2', 'co2_per_capita',
        'share_global_co2', 'energy_per_capita'
    ]].dropna(subset=['co2'])
    
    print(f"\n📊 CO2 Data for {country}:")
    print(f"   Latest year: {data['year'].max()}")
    print(f"   Latest CO2 total: {data[data['year'] == data['year'].max()]['co2'].values[0]:.2f} million tons")
    print(f"   Latest CO2 per capita: {data[data['year'] == data['year'].max()]['co2_per_capita'].values[0]:.3f} tons/person")
    print(f"   Share of global CO2: {data[data['year'] == data['year'].max()]['share_global_co2'].values[0]:.4f}%")
    print(f"\n   Last 5 years trend:")
    print(data.tail(5).to_string(index=False))
    
    # Save country data
    filename = f"data/{country.lower().replace(' ', '_')}_co2.csv"
    data.to_csv(filename, index=False)
    print(f"\n✅ Saved to {filename}")
    return data

# ── COMPARE MULTIPLE COUNTRIES ──
def compare_countries(country_list, start_year=2000):
    print(f"\n📊 Comparing: {', '.join(country_list)}")
    results = []
    for c in country_list:
        matches = [x for x in all_countries if c.lower() in x.lower()]
        if matches:
            data = df[(df['country'] == matches[0]) & (df['year'] >= start_year)][[
                'country', 'year', 'co2_per_capita'
            ]].dropna()
            results.append(data)
    
    if results:
        combined = pd.concat(results)
        summary = combined.groupby('country')['co2_per_capita'].agg(['mean', 'max', 'min']).round(3)
        summary.columns = ['Average', 'Highest', 'Lowest']
        print(summary)
        combined.to_csv("data/comparison_co2.csv", index=False)
        print("\n✅ Saved to data/comparison_co2.csv")
    return combined

# ── INTERACTIVE SEARCH LOOP ──
def main():
    print("\n" + "="*50)
    print("🌿 ECOSPHERE — Global Carbon Search")
    print("="*50)
    print("Commands:")
    print("  search  → search a country")
    print("  compare → compare multiple countries")
    print("  list    → show all countries")
    print("  quit    → exit")
    
    while True:
        print("\n" + "-"*40)
        command = input("Enter command: ").strip().lower()
        
        if command == "quit":
            print("👋 Goodbye!")
            break
            
        elif command == "search":
            country = input("Enter country name: ").strip()
            search_country(country)
            
        elif command == "compare":
            countries_input = input("Enter countries (comma separated): ").strip()
            country_list = [c.strip() for c in countries_input.split(",")]
            compare_countries(country_list)
            
        elif command == "list":
            print("\n🌍 All available countries/regions:")
            # Show only actual countries (exclude regions)
            actual = [c for c in sorted(all_countries) 
                     if not any(x in c for x in ['World','Asia','Europe','Africa','America','income','G20','OECD'])]
            for i, c in enumerate(actual, 1):
                print(f"  {i:3}. {c}")
                
        else:
            print("❌ Unknown command. Try: search, compare, list, quit")

if __name__ == "__main__":
    main()