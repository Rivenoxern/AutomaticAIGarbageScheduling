"""
simulator/simulate.py
──────────────────────
Mock simulation loop that mimics real-world bin filling and truck breakdowns.

Usage:
    python simulator/simulate.py [--interval 5] [--breakdown-prob 0.05]

What it does every <interval> seconds:
  1. Picks 2-4 random bins and increases their capacity by a random 5-20%.
     Capacity is clamped to 100%.
  2. With probability <breakdown-prob>, marks a random active truck
     as "out_of_service" and prints a CRISIS alert.
  3. Prints a live status table to the console.

Stop with Ctrl+C.
"""
import argparse
import random
import sys
import os
import time
from datetime import datetime, timezone

# Allow running from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.core.database import SessionLocal
from app.models.trash_bin import TrashBin
from app.models.truck import Truck, TruckStatus
from app.models.crisis_event import CrisisEvent


# ── ANSI colours for console output ──────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

CAPACITY_THRESHOLD = 75.0  # % above which agent should respond


def capacity_colour(pct: float) -> str:
    if pct >= 90:
        return f"{RED}{pct:5.1f}%{RESET}"
    if pct >= CAPACITY_THRESHOLD:
        return f"{YELLOW}{pct:5.1f}%{RESET}"
    return f"{GREEN}{pct:5.1f}%{RESET}"


def run_simulation(interval: int, breakdown_prob: float):
    print(f"{CYAN}🚛  WasteWay Simulator started{RESET}")
    print(f"   Tick interval : {interval}s")
    print(f"   Breakdown prob: {breakdown_prob:.0%}")
    print(f"   Capacity alert: ≥ {CAPACITY_THRESHOLD}%\n")

    tick = 0
    while True:
        tick += 1
        db = SessionLocal()
        try:
            _tick_bins(db, tick)
            _tick_breakdowns(db, breakdown_prob)
            _print_status(db, tick)
        finally:
            db.close()

        time.sleep(interval)


def _tick_bins(db, tick: int):
    """Randomly fill 2-4 bins by 5-20%."""
    all_bins: list[TrashBin] = db.query(TrashBin).all()
    if not all_bins:
        print("⚠️  No bins found. Run `python simulator/seed.py` first.")
        return

    selected = random.sample(all_bins, k=min(random.randint(2, 4), len(all_bins)))
    for bin_obj in selected:
        increase = random.uniform(5.0, 20.0)
        bin_obj.current_capacity_pct = min(
            100.0, bin_obj.current_capacity_pct + increase
        )
        bin_obj.last_updated = datetime.now(timezone.utc)

    db.commit()


def _tick_breakdowns(db, breakdown_prob: float):
    """With small probability, trigger a truck breakdown."""
    if random.random() > breakdown_prob:
        return

    active_trucks: list[Truck] = (
        db.query(Truck)
        .filter(Truck.status.in_([TruckStatus.idle, TruckStatus.en_route]))
        .all()
    )
    if not active_trucks:
        return

    victim: Truck = random.choice(active_trucks)
    victim.status = TruckStatus.out_of_service

    # Log the crisis event
    crisis = CrisisEvent(
        truck_id=victim.id,
        issue_type="breakdown",
        resolved=False,
    )
    db.add(crisis)
    db.commit()

    print(
        f"\n{RED}🚨  CRISIS: Truck {victim.plate_number} (ID={victim.id}) "
        f"reported a breakdown! → out_of_service{RESET}\n"
    )


def _print_status(db, tick: int):
    """Pretty-print current bin and truck states."""
    bins: list[TrashBin] = db.query(TrashBin).order_by(
        TrashBin.current_capacity_pct.desc()
    ).all()
    trucks: list[Truck] = db.query(Truck).all()

    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"──── Tick #{tick:04d}  [{now} UTC] ────────────────────────────")

    # Bins table
    print(f"{'ID':>3}  {'Location':<28}  {'Capacity':>9}  Alert")
    for b in bins:
        alert = "⚠️ ALERT" if b.current_capacity_pct >= CAPACITY_THRESHOLD else ""
        cap   = capacity_colour(b.current_capacity_pct)
        print(f"{b.id:>3}  {b.location_name:<28}  {cap}  {alert}")

    # Trucks table
    print()
    print(f"{'ID':>3}  {'Plate':<14}  Status")
    for t in trucks:
        colour = GREEN if t.status == TruckStatus.idle else (
            YELLOW if t.status == TruckStatus.en_route else RED
        )
        print(f"{t.id:>3}  {t.plate_number:<14}  {colour}{t.status.value}{RESET}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WasteWay Mock Simulator")
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Seconds between simulation ticks (default: 5)"
    )
    parser.add_argument(
        "--breakdown-prob", type=float, default=0.05,
        help="Probability per tick that a truck breaks down (default: 0.05)"
    )
    args = parser.parse_args()

    try:
        run_simulation(args.interval, args.breakdown_prob)
    except KeyboardInterrupt:
        print(f"\n{CYAN}🛑  Simulator stopped.{RESET}")
