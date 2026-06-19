"""
Feature:  Supplier & Factory Network — curated reference seed
Layer:    Script
Purpose:  Idempotently seed `reference_factories` with REAL, publicly-documented
          European manufacturers of electronics / home appliances / kitchen / garden,
          with real city-level coordinates and real websites. No mock data.
          Logos are derived from each real website domain via Google's favicon service.

Run (from project root):
    DATABASE_URL=postgresql+asyncpg://mawrid:password@localhost:5433/mawrid \
        uv run python scripts/seed_factories.py
"""

from __future__ import annotations

import asyncio
import hashlib
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# name, category, subcategory, country, city, lat, lon, website-domain, offering, condition
FACTORIES: list[tuple[str, str, str, str, str, float, float, str, str, str]] = [
    ("BSH Hausgeräte (Bosch · Siemens)", "appliances", "major", "Germany", "Munich", 48.1351, 11.5820, "bosch-home.com", "Washing machines, refrigeration, dishwashers, ovens", "both"),
    ("Miele", "appliances", "major", "Germany", "Gütersloh", 51.9069, 8.3786, "miele.com", "Premium washing, refrigeration, cooking & vacuum", "both"),
    ("Liebherr-Hausgeräte", "refrigeration", "major", "Germany", "Ochsenhausen", 48.0689, 9.9530, "home.liebherr.com", "Refrigerators & freezers", "new"),
    ("Whirlpool EMEA", "appliances", "major", "Italy", "Pero (Milan)", 45.5089, 9.0900, "whirlpool.eu", "Washing, refrigeration, cooking, dishwashers", "both"),
    ("Candy · Haier Europe", "appliances", "major", "Italy", "Brugherio", 45.5450, 9.2980, "haier-europe.com", "Washing machines, refrigeration, ovens", "new"),
    ("Electrolux", "appliances", "major", "Sweden", "Stockholm", 59.3293, 18.0686, "electrolux.com", "Washing, refrigeration, cooking (AEG, Zanussi)", "both"),
    ("Gorenje (Hisense)", "appliances", "major", "Slovenia", "Velenje", 46.3592, 15.1100, "gorenje.com", "Washing, refrigeration, cooking", "new"),
    ("Smeg", "appliances", "cooking", "Italy", "Guastalla", 44.9230, 10.6560, "smeg.com", "Retro cookers, ovens, small appliances", "new"),
    ("De'Longhi", "small-appliances", "coffee", "Italy", "Treviso", 45.6669, 12.2430, "delonghi.com", "Coffee machines, kitchen & comfort appliances", "new"),
    ("Indesit (Whirlpool)", "appliances", "major", "Italy", "Fabriano", 43.3360, 12.9050, "indesit.com", "Washing, refrigeration, cooking", "new"),
    ("Hotpoint (Whirlpool)", "appliances", "major", "United Kingdom", "Peterborough", 52.5695, -0.2405, "hotpoint.co.uk", "Washing, refrigeration, cooking", "new"),
    ("Teka", "kitchen", "appliances", "Spain", "Santander", 43.4623, -3.8100, "teka.com", "Kitchen sinks, hobs, ovens, hoods", "new"),
    ("Fagor", "appliances", "major", "Spain", "Mondragón", 43.0660, -2.4920, "fagor.com", "Cooking, washing, refrigeration", "new"),
    ("Gaggenau (BSH)", "appliances", "premium-cooking", "France", "Lipsheim", 48.5170, 7.6900, "gaggenau.com", "Premium built-in ovens & cooking", "new"),
    ("AEG (Electrolux)", "appliances", "major", "Germany", "Nuremberg", 49.4521, 11.0767, "aeg.com", "Washing, cooking, refrigeration", "new"),
    ("Zanussi (Electrolux)", "appliances", "major", "Italy", "Porcia", 45.9580, 12.6170, "zanussi.com", "Washing, refrigeration, cooking", "new"),
    ("Bauknecht (Whirlpool)", "appliances", "major", "Germany", "Stuttgart", 48.7758, 9.1829, "bauknecht.de", "Washing, refrigeration, cooking", "new"),
    ("V-ZUG", "appliances", "premium", "Switzerland", "Zug", 47.1662, 8.5155, "vzug.com", "Premium washing & cooking", "new"),
    ("Bertazzoni", "appliances", "cooking", "Italy", "Guastalla", 44.9230, 10.6560, "bertazzoni.com", "Ranges, ovens, hoods", "new"),
    ("Rational", "appliances", "commercial-cooking", "Germany", "Landsberg am Lech", 48.0480, 10.8700, "rational-online.com", "Commercial combi ovens", "new"),
    ("Franke", "kitchen", "systems", "Switzerland", "Aarburg", 47.3210, 7.9000, "franke.com", "Kitchen sinks, hoods, taps", "new"),
    ("Elica", "kitchen", "hoods", "Italy", "Fabriano", 43.3360, 12.9050, "elica.com", "Cooker hoods & ventilation", "new"),
    ("Groupe SEB (Tefal · Moulinex · Krups)", "small-appliances", "kitchen", "France", "Écully", 45.7740, 4.7770, "groupeseb.com", "Cookware & kitchen small appliances", "new"),
    ("Philips Domestic Appliances (Versuni)", "small-appliances", "kitchen", "Netherlands", "Amsterdam", 52.3676, 4.9041, "versuni.com", "Airfryers, kitchen & home appliances", "new"),
    ("Jura", "small-appliances", "coffee", "Switzerland", "Niederbuchsiten", 47.2640, 7.6720, "jura.com", "Automatic coffee machines", "new"),
    ("Dyson", "small-appliances", "floorcare", "United Kingdom", "Malmesbury", 51.5840, -2.0990, "dyson.com", "Vacuums, fans, hair & air care", "both"),
    ("Vorwerk (Thermomix)", "kitchen", "appliances", "Germany", "Wuppertal", 51.2562, 7.1508, "vorwerk.com", "Thermomix & kitchen systems", "new"),
    ("Kärcher", "garden", "cleaning", "Germany", "Winnenden", 48.8770, 9.3990, "kaercher.com", "Pressure washers & cleaning", "new"),
    ("STIHL", "garden", "power-tools", "Germany", "Waiblingen", 48.8310, 9.3160, "stihl.com", "Chainsaws, trimmers, garden power tools", "new"),
    ("Gardena (Husqvarna)", "garden", "tools", "Germany", "Ulm", 48.4011, 9.9876, "gardena.com", "Garden tools, watering, robotic mowers", "both"),
    ("Husqvarna", "garden", "power-tools", "Sweden", "Husqvarna", 57.7920, 14.1100, "husqvarna.com", "Mowers, chainsaws, garden equipment", "both"),
    ("Einhell", "garden", "tools", "Germany", "Landau an der Isar", 48.6750, 12.6940, "einhell.com", "Cordless garden & power tools", "new"),
    ("Makita Europe", "garden", "power-tools", "Germany", "Ratingen", 51.2970, 6.8490, "makita.de", "Power & garden tools", "new"),
    ("Bosch Power Tools & Garden", "garden", "power-tools", "Germany", "Leinfelden-Echterdingen", 48.6920, 9.1660, "bosch-garden.com", "Garden & DIY power tools", "both"),
    ("Samsung Electronics Europe", "electronics", "consumer", "Netherlands", "Amsterdam", 52.3080, 4.7640, "samsung.com", "TVs, appliances & electronics", "new"),
    ("LG Electronics Europe", "electronics", "consumer", "Germany", "Eschborn", 50.1390, 8.5700, "lg.com", "TVs, appliances & electronics", "new"),
    ("Sony Europe", "electronics", "consumer", "United Kingdom", "Weybridge", 51.3740, -0.4570, "sony.co.uk", "TVs, audio & imaging", "new"),
    ("Panasonic Europe", "electronics", "consumer", "Germany", "Wiesbaden", 50.0826, 8.2400, "panasonic.eu", "TVs, appliances & electronics", "new"),
    ("Philips", "electronics", "consumer", "Netherlands", "Amsterdam", 52.3676, 4.9041, "philips.com", "Consumer electronics & personal health", "new"),
    ("TCL Europe", "electronics", "consumer", "Poland", "Warsaw", 52.2297, 21.0122, "tcl.com", "TVs & consumer electronics", "new"),
    ("Sharp Europe", "electronics", "consumer", "United Kingdom", "Wrexham", 53.0430, -2.9920, "sharpconsumer.com", "TVs, appliances & electronics", "new"),
    ("Vestfrost", "refrigeration", "commercial", "Denmark", "Esbjerg", 55.4760, 8.4590, "vestfrost.com", "Commercial & domestic refrigeration", "new"),
    ("Gram", "refrigeration", "commercial", "Denmark", "Vojens", 55.2510, 9.3030, "gram-commercial.com", "Refrigerators & freezers", "new"),
    ("Ariston", "appliances", "heating", "Italy", "Fabriano", 43.3360, 12.9050, "ariston.com", "Water heaters & heating", "new"),
    ("Hansgrohe", "kitchen", "fittings", "Germany", "Schiltach", 48.2890, 8.3430, "hansgrohe.com", "Kitchen & bath taps", "new"),
    ("BLANCO", "kitchen", "sinks", "Germany", "Oberderdingen", 49.0640, 8.8000, "blanco.com", "Kitchen sinks & taps", "new"),
    ("Villeroy & Boch", "kitchen", "ceramics", "Germany", "Mettlach", 49.4940, 6.5960, "villeroyboch.com", "Kitchen & tableware ceramics", "new"),
    ("KitchenAid (Whirlpool EMEA)", "small-appliances", "kitchen", "Italy", "Pero (Milan)", 45.5089, 9.0900, "kitchenaid.eu", "Stand mixers & kitchen appliances", "both"),
    ("Nivona", "small-appliances", "coffee", "Germany", "Nuremberg", 49.4521, 11.0767, "nivona.com", "Coffee machines", "new"),
    ("Severin", "small-appliances", "kitchen", "Germany", "Sundern", 51.3270, 7.9870, "severin.com", "Small kitchen & household appliances", "new"),
    ("WMF", "kitchen", "cookware", "Germany", "Geislingen", 48.6240, 9.8300, "wmf.com", "Cookware & kitchen tools", "new"),
    ("Fissler", "kitchen", "cookware", "Germany", "Idar-Oberstein", 49.7110, 7.3050, "fissler.com", "Pots, pans & pressure cookers", "new"),
    ("Zwilling", "kitchen", "cutlery", "Germany", "Solingen", 51.1710, 7.0830, "zwilling.com", "Knives & cookware", "new"),
    ("Beko · Arçelik (EU plant)", "appliances", "major", "Romania", "Ulmi", 44.9000, 25.9000, "beko.com", "Washing, refrigeration, cooking", "new"),
    ("Electrolux Professional", "appliances", "commercial", "Italy", "Pordenone", 45.9560, 12.6600, "electroluxprofessional.com", "Commercial kitchen & laundry", "both"),
]


def _fid(name: str) -> str:
    return "ref_" + hashlib.sha256(name.encode()).hexdigest()[:16]


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://mawrid:password@localhost:5433/mawrid")
    engine = create_async_engine(url)
    upsert = text(
        """
        INSERT INTO reference_factories
          (factory_id, name, category, subcategory, country, city, latitude, longitude,
           website, logo_url, offering, condition, region)
        VALUES
          (:fid, :name, :category, :subcategory, :country, :city, :lat, :lon,
           :website, :logo_url, :offering, :condition, 'europe')
        ON CONFLICT (factory_id) DO UPDATE SET
          name=EXCLUDED.name, category=EXCLUDED.category, subcategory=EXCLUDED.subcategory,
          country=EXCLUDED.country, city=EXCLUDED.city, latitude=EXCLUDED.latitude,
          longitude=EXCLUDED.longitude, website=EXCLUDED.website, logo_url=EXCLUDED.logo_url,
          offering=EXCLUDED.offering, condition=EXCLUDED.condition, region='europe'
        """
    )
    async with engine.begin() as conn:
        for name, cat, sub, country, city, lat, lon, domain, offering, cond in FACTORIES:
            await conn.execute(
                upsert,
                {
                    "fid": _fid(name), "name": name, "category": cat, "subcategory": sub,
                    "country": country, "city": city, "lat": lat, "lon": lon,
                    "website": f"https://{domain}",
                    "logo_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                    "offering": offering, "condition": cond,
                },
            )
    await engine.dispose()
    print(f"seeded {len(FACTORIES)} real European manufacturers into reference_factories")


if __name__ == "__main__":
    asyncio.run(main())
