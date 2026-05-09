import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os
import glob

print("🤖 ECOSPHERE — ML AQI Prediction Model")
print("=" * 45)

# ── STEP 1: Load all saved AQI CSV files ──
def load_all_aqi_data():
    print("\n📂 Loading AQI data from data/ folder...")
    all_files = glob.glob("data/*_aqi.csv")

    if not all_files:
        print("❌ No AQI data found!")
        print("💡 Run fetch_aqi.py first to download data")
        return None

    dfs = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
            print(f"   ✅ Loaded: {f} ({len(df)} rows)")
        except Exception as e:
            print(f"   ⚠️ Error loading {f}: {e}")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"\n✅ Total records: {len(combined)}")
    return combined

# ── STEP 2: Prepare features ──
def prepare_features(df):
    print("\n🔧 Preparing features...")

    df = df[df["parameter"] == "pm25"].copy()
    df = df[df["value"] > 0]
    df = df[df["value"] < 500]

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "value"])

    df["hour"]       = df["date"].dt.hour
    df["day"]        = df["date"].dt.day
    df["month"]      = df["date"].dt.month
    df["dayofweek"]  = df["date"].dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)

    # Encode country — save mapping for later
    df["country_code"], country_index = pd.factorize(df["country"])
    country_map = {name: code for code, name in enumerate(country_index)}

    print(f"   Countries: {list(country_map.keys())}")
    print(f"   Total rows for training: {len(df)}")
    return df, country_map

# ── STEP 3: Train model ──
def train_model(df):
    print("\n🏋️ Training Random Forest model...")

    features = ["hour", "day", "month", "dayofweek", "is_weekend", "country_code"]
    target   = "value"

    X = df[features]
    y = df[target]

    if len(X) < 10:
        print("❌ Not enough data to train! Search more countries first.")
        return None, None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    r2  = r2_score(y_test, predictions)

    print(f"\n📊 Model Performance:")
    print(f"   MAE (Mean Absolute Error) : {mae:.2f} µg/m³")
    print(f"   R² Score                  : {r2:.3f}")
    print(f"   Accuracy                  : {r2*100:.1f}%")

    return model, features

# ── STEP 4: Save model ──
def save_model(model, features, country_map):
    os.makedirs("models", exist_ok=True)
    joblib.dump(model,       "models/aqi_model.pkl")
    joblib.dump(features,    "models/features.pkl")
    joblib.dump(country_map, "models/country_map.pkl")
    print(f"\n✅ Model saved → models/aqi_model.pkl")
    print(f"✅ Country map saved → models/country_map.pkl")

# ── STEP 5: Predict for one country ──
def predict_aqi(model, hour, month, dayofweek, country_code):
    is_weekend = 1 if dayofweek in [5, 6] else 0
    input_data = pd.DataFrame([{
        "hour":         hour,
        "day":          15,
        "month":        month,
        "dayofweek":    dayofweek,
        "is_weekend":   is_weekend,
        "country_code": country_code
    }])
    return round(model.predict(input_data)[0], 2)

# ── STEP 6: Show predictions for ALL countries ──
def show_predictions(model, country_map):
    print("\n🔮 AQI Predictions (next 24 hours) for all countries:")
    print("=" * 45)

    now = pd.Timestamp.now()

    for country, code in country_map.items():
        print(f"\n🌍 {country}:")
        print("─" * 40)

        for i in range(0, 24, 4):  # every 4 hours
            future = now + pd.Timedelta(hours=i)
            pred = predict_aqi(
                model,
                hour=future.hour,
                month=future.month,
                dayofweek=future.dayofweek,
                country_code=code
            )
            status = "❌ UNSAFE" if pred > 15 else "✅ SAFE"
            bar    = "█" * min(int(pred / 10), 20)
            print(f"   {future.strftime('%H:%M')} → {pred:6.2f} µg/m³  {status}  {bar}")

# ── STEP 7: Predict any specific country interactively ──
def predict_for_country(model, country_map):
    print("\n" + "=" * 45)
    print("🔍 Predict AQI for a specific country")
    print("=" * 45)

    while True:
        query = input("\nEnter country name (or 'quit'): ").strip()
        if query.lower() == "quit":
            break

        matches = {n: c for n, c in country_map.items() if query.lower() in n.lower()}
        if not matches:
            print(f"❌ '{query}' not found!")
            print(f"Available: {list(country_map.keys())}")
            continue

        country = list(matches.keys())[0]
        code    = matches[country]
        now     = pd.Timestamp.now()

        print(f"\n🔮 24-hour AQI forecast for {country}:")
        print("─" * 40)
        for i in range(24):
            future = now + pd.Timedelta(hours=i)
            pred   = predict_aqi(
                model,
                hour=future.hour,
                month=future.month,
                dayofweek=future.dayofweek,
                country_code=code
            )
            status = "❌" if pred > 15 else "✅"
            bar    = "█" * min(int(pred / 10), 20)
            print(f"   {future.strftime('%H:%M')} → {pred:6.2f} µg/m³  {status}  {bar}")

# ── MAIN ──
def main():
    # Load data
    df = load_all_aqi_data()
    if df is None:
        return

    # Prepare
    df, country_map = prepare_features(df)
    if df.empty:
        print("❌ No PM2.5 data found!")
        return

    # Train
    model, features = train_model(df)
    if model is None:
        return

    # Save
    save_model(model, features, country_map)

    # Show all countries predictions
    show_predictions(model, country_map)

    # Interactive search
    predict_for_country(model, country_map)

    print("\n" + "=" * 45)
    print("✅ ML Model complete!")
    print("✅ Ready for dashboard integration!")
    print("=" * 45)

if __name__ == "__main__":
    main()