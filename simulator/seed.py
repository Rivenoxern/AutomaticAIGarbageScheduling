"""
simulator/seed.py
──────────────────
One-time seed script: populates the database with realistic mock data.

Run ONCE before starting the simulator:
    python simulator/seed.py

What it creates:
  • 3 Drivers
  • 3 Trucks (each linked to a driver)
  • 12 Trash Bins spread across a fictional city grid
"""
import sys
import os

# Allow running from the project root: python simulator/seed.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.core.database import SessionLocal, Base, engine
import app.models  # ensure all models are registered  # noqa: F401
from app.models.driver import Driver
from app.models.truck import Truck, TruckStatus
from app.models.trash_bin import TrashBin


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Guard: skip if data already exists ────────────────────────────────
        if db.query(Driver).count() > 0:
            print("⚠️  Seed data already present. Skipping.")
            return

        # ── Drivers ───────────────────────────────────────────────────────────
        drivers = [
            Driver(name="Budi Santoso",   license_number="SIM-001", phone="081234567890"),
            Driver(name="Agus Wijaya",    license_number="SIM-002", phone="081234567891"),
            Driver(name="Dewi Rahayu",    license_number="SIM-003", phone="081234567892"),
        ]
        db.add_all(drivers)
        db.flush()  # get driver IDs without committing

        # ── Trucks ────────────────────────────────────────────────────────────
        trucks = [
            Truck(plate_number="B-1234-WW", driver_id=drivers[0].id,
                  status=TruckStatus.idle, current_gps_location="-6.2000,106.8166"),
            Truck(plate_number="B-5678-WW", driver_id=drivers[1].id,
                  status=TruckStatus.idle, current_gps_location="-6.2100,106.8200"),
            Truck(plate_number="B-9012-WW", driver_id=drivers[2].id,
                  status=TruckStatus.idle, current_gps_location="-6.1900,106.8100"),
        ]
        db.add_all(trucks)

        # ── Trash Bins (12 bins across a fictional 10×10 grid) ───────────────
        bin_data = [
            ("Jl. Sudirman Blok A",   -6.2088, 106.8227,  10.0),
            ("Jl. Sudirman Blok B",   -6.2095, 106.8240,  45.0),
            ("Jl. Thamrin Blok A",    -6.1944, 106.8229,  80.0),  # will trigger agent
            ("Jl. Thamrin Blok B",    -6.1950, 106.8235,  20.0),
            ("Pasar Minggu Utara",    -6.2600, 106.8420,  65.0),
            ("Pasar Minggu Selatan",  -6.2650, 106.8430,  90.0),  # will trigger agent
            ("Kebayoran Baru A",      -6.2383, 106.7971,  30.0),
            ("Kebayoran Baru B",      -6.2390, 106.7980,  55.0),
            ("Tebet Timur",           -6.2250, 106.8500,  78.0),  # will trigger agent
            ("Tebet Barat",           -6.2260, 106.8490,   5.0),
            ("Cawang Junction",       -6.2426, 106.8706,  40.0),
            ("Cawang Interchange",    -6.2430, 106.8710,  12.0),
        ]

        bins = [
            TrashBin(
                location_name=name,
                latitude=lat,
                longitude=lng,
                current_capacity_pct=cap,
            )
            for name, lat, lng, cap in bin_data
        ]
        db.add_all(bins)
        db.commit()

        print("✅  Seed complete!")
        print(f"   Drivers : {len(drivers)}")
        print(f"   Trucks  : {len(trucks)}")
        print(f"   Bins    : {len(bins)}")

    except Exception as exc:
        db.rollback()
        print(f"❌  Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
