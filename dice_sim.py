#!/usr/bin/env python3
"""
Betfury-style Dice Simulator — casino table edition
====================================================
1% house edge, 0.00-99.99 rolls, payout = 99 / win-chance.

Modes:
  python3 dice_sim.py            -> batch stats for all strategies
  python3 dice_sim.py live       -> play-by-play casino table, watch the dice
  python3 dice_sim.py live 5     -> live mode with a chosen strategy id
  python3 dice_sim.py live 5 500 -> live mode, strategy 5, 500 bets
"""
import os
import random
import shutil
import sys
import time

# ── casino colors ──────────────────────────────────────────────
R = "\033[31m"   # red
G = "\033[32m"   # green
Y = "\033[33m"   # yellow
C = "\033[36m"   # cyan
B = "\033[1m"    # bold
DIM = "\033[2m"
W = "\033[97m"
RESET = "\033[0m"

PIP = "●"
DIE_FACES = [
    [[0,0,0],[0,1,0],[0,0,0]],  # 1
    [[1,0,0],[0,0,0],[0,0,1]],  # 2
    [[1,0,0],[0,1,0],[0,0,1]],  # 3
    [[1,0,1],[0,0,0],[1,0,1]],  # 4
    [[1,0,1],[0,1,0],[1,0,1]],  # 5
    [[1,0,1],[1,0,1],[1,0,1]],  # 6
]

def die_face(n, color=W, width=9):
    """ASCII dice face for pip value 1-6."""
    f = DIE_FACES[(n - 1) % 6]
    lines = []
    lines.append(f"{color}┌{'─'*(width-2)}┐")
    for row in f:
        cell = f"{PIP} " if row == [0,0,0] else f"{PIP} {PIP} {PIP}"
        # build row: positions left, mid, right
        left = PIP if row[0] else " "
        mid  = PIP if row[1] else " "
        right= PIP if row[2] else " "
        lines.append(f"{color}│  {left}  {mid}  {right}  │")
    lines.append(f"{color}└{'─'*(width-2)}┘{RESET}")
    return lines

def roll_track(roll, chance, win, width=51):
    """Visual 0-100 track with the roll marker and the win zone."""
    pos = int(roll / 100 * (width - 1))
    line = ["─"] * width
    # win zone (roll under `chance`)
    zEnd = int(chance / 100 * (width - 1))
    for i in range(zEnd):
        line[i] = f"{G}·{RESET}" if not win else line[i]
    line[pos] = f"{B}{W}●{RESET}"
    bar = "".join(line)
    return f"{DIM}0{RESET}{bar}{DIM}100{RESET}"

def banner():
    cols = shutil.get_terminal_size((80, 24)).columns
    art = f"""{C}{B}
    ╔════════════════════════════════════════════════════╗
    ║  🎲  D I C E   T A B L E  —  House Edge 1%  🎲   ║
    ╚════════════════════════════════════════════════════╝{RESET}"""
    print(art)

# ── strategies ─────────────────────────────────────────────────
# Each strategy: make(bankroll) -> step(balance, last_result) -> (chance, bet)

def flat(chance=49.5, bet_frac=0.01):
    return lambda bal, last: (chance, bal * bet_frac)

def tiny_flat(chance=49.5, bet_frac=0.005):
    return lambda bal, last: (chance, bal * bet_frac)

def martingale(chance=49.5, base_frac=0.002):
    st = {"n": 0}
    def step(bal, last):
        if last: st["n"] = 0
        elif last is False: st["n"] += 1
        return chance, bal * base_frac * (2 ** st["n"])
    return step

def martingale_cap(chance=49.5, base_frac=0.004, max_steps=6):
    st = {"n": 0}
    def step(bal, last):
        if last: st["n"] = 0
        elif last is False: st["n"] += 1
        return chance, bal * base_frac * (2 ** min(st["n"], max_steps))
    return step

def ladder(chance=60.0, bet_frac=0.01, up=1.5):
    st = {"m": 1.0}
    def step(bal, last):
        if last is True: st["m"] *= up
        elif last is False: st["m"] = 1.0
        return chance, bal * bet_frac * st["m"]
    return step

def dalembert(chance=49.5, base_frac=0.005, unit=0.002):
    """+1 unit after loss, -1 after win (classic casino system)."""
    st = {"u": 1}
    def step(bal, last):
        if last is False: st["u"] += 1
        elif last is True: st["u"] = max(1, st["u"] - 1)
        return chance, bal * base_frac * st["u"]
    return step

def fibonacci(chance=49.5, base_frac=0.004):
    """Fibonacci progression on losses, reset 2 steps on win."""
    fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
    st = {"i": 0}
    def step(bal, last):
        if last is False: st["i"] = min(st["i"] + 1, len(fib) - 1)
        elif last is True: st["i"] = max(0, st["i"] - 2)
        return chance, bal * base_frac * fib[st["i"]]
    return step

def vault_streak(streak_goal=10, chance=50.0):
    """★ Kalenzi's vault strategy: base = 0.1% bankroll, roll every win
    forward, bank the streak at N wins, reset on loss. Direction follows
    the previous roll (over/under) — odds identical either way."""
    state = {"bet": None, "streak": 0}
    def step(bal, last):
        if state["bet"] is None or state["streak"] >= streak_goal:
            state["bet"] = bal / 1000.0
            state["streak"] = 0
        if state["bet"] > bal:
            state["bet"] = bal
        return chance, state["bet"]
    # wrap: after result, update streak & rolled bet
    def wrapped(bal, last):
        chance_pct, bet = step(bal, last)
        return chance_pct, bet
    return wrapped, state, streak_goal

STRATEGIES = [
    ("1", "Flat 1% @49.5%",              lambda: flat()),
    ("2", "Tiny flat 0.5% @49.5%",       lambda: tiny_flat()),
    ("3", "Martingale uncapped",         lambda: martingale()),
    ("4", "Martingale 6-step cap",       lambda: martingale_cap()),
    ("5", "Vault streak-10 (yours)",     "vault"),
    ("6", "Ladder x1.5 @60%",            lambda: ladder()),
    ("7", "D'Alembert",                  lambda: dalembert()),
    ("8", "Fibonacci",                  lambda: fibonacci()),
]

def make_strategy(s_id):
    if s_id == "vault":
        return "vault"
    for sid, name, fn in STRATEGIES:
        if sid == s_id:
            return "vault" if fn == "vault" else fn()
    return flat()

# ── game engine ─────────────────────────────────────────────────
def play(chance, bet, rng):
    roll = rng.uniform(0, 100)
    win = roll < chance           # "roll under" direction; 50/50 either way
    payout = bet * (99.0 / chance) if win else 0.0
    return roll, win, payout

def batch(n_sessions=200, max_bets=10_000, bankroll=1000, seed=42):
    print(f"\n{B}BATCH MODE{RESET} — {n_sessions} sessions × {max_bets:,} bets, bankroll {bankroll}\n")
    hdr = f"{'strategy':<26} {'bust':>5} {'median':>9} {'best':>9} {'worst':>8} {'profit':>7}"
    print(f"{B}{hdr}{RESET}\n{'─'*len(hdr)}")
    for sid, name, fn in STRATEGIES:
        rng = random.Random(seed + int(sid))
        finals, busts = [], 0
        for _ in range(n_sessions):
            bal, step = bankroll, (fn() if fn != "vault" else None)
            if fn == "vault":
                st = {"bet": None, "streak": 0}
            last = None
            for _ in range(max_bets):
                if fn == "vault":
                    if st["bet"] is None or st["streak"] >= 10:
                        st["bet"] = bal / 1000.0
                        st["streak"] = 0
                    if st["bet"] > bal: st["bet"] = bal
                    chance, bet = 50.0, st["bet"]
                else:
                    chance, bet = step(bal, last)
                if bet <= 0 or bet > bal: bet = max(min(bet, bal), 0)
                if bet <= 0: break
                bal -= bet
                roll, win, payout = play(chance, bet, rng)
                last = win
                bal += payout
                if fn == "vault":
                    st["streak"] = st["streak"] + 1 if win else 0
                    if win and st["streak"] >= 10:
                        st["bet"] = None
                    elif win:
                        st["bet"] = min(payout, bal)
                    else:
                        st["bet"] = None
                if bal <= 0:
                    busts += 1
                    break
            finals.append(bal)
        finals.sort()
        print(f"{name:<26} {100*busts/n_sessions:>4.0f}% {finals[len(finals)//2]:>9.1f} "
              f"{finals[-1]:>9.1f} {finals[0]:>8.1f} "
              f"{100*sum(1 for f in finals if f > bankroll)/n_sessions:>6.0f}%")
    print(f"\n{DIM}House edge eats every strategy long-run. Sizing changes the ride, not the destination.{RESET}\n")

def live(s_id="5", max_bets=200, bankroll=1000, delay=0.12):
    banner()
    name = next((n for i, n, f in STRATEGIES if i == s_id), "Vault streak-10")
    print(f"  Table: {B}{name}{RESET}   Bankroll: {B}{bankroll}{RESET}   Bets: {max_bets}\n")
    rng = random.Random()
    bal = bankroll
    st = {"bet": None, "streak": 0}
    step = make_strategy(s_id)
    last, peak, bets, wins, biggest = None, bankroll, 0, 0, 0

    for i in range(max_bets):
        if step == "vault":
            if st["bet"] is None or st["streak"] >= 10:
                st["bet"] = bal / 1000.0
                st["streak"] = 0
            if st["bet"] > bal: st["bet"] = bal
            chance, bet = 50.0, st["bet"]
        else:
            chance, bet = step(bal, last)
        if bet <= 0: break
        bal -= bet
        roll, win, payout = play(chance, bet, rng)
        last = win
        bal += payout
        if step == "vault":
            if win:
                st["streak"] += 1
                st["bet"] = None if st["streak"] >= 10 else min(payout, bal)
            else:
                st["streak"] = 0
                st["bet"] = None
        bets += 1
        wins += win
        peak = max(peak, bal)
        biggest = max(biggest, payout)

        die_val = int(roll) % 6 + 1
        d1 = die_face(int(roll) % 6 + 1, G if win else R)
        d2 = die_face((int(roll * 10)) % 6 + 1, G if win else R)
        tag = f"{G}{B} WIN  {RESET}" if win else f"{R}{B} LOSE {RESET}"
        streak_s = f"streak {B}{st['streak']}{RESET}/10" if step == "vault" else ""
        print(f"\r{DIM}bet {i+1:>4}{RESET}  {tag} roll {B}{roll:>5.2f}{RESET}  "
              f"stake {Y}{bet:>8.2f}{RESET}  balance {B}{bal:>9.2f}{RESET}  {streak_s}")
        # print dice + track every 10 bets
        if (i + 1) % 10 == 0 or (step == "vault" and win):
            print(roll_track(roll, chance, win))
            for a, b2 in zip(d1, d2):
                print(f"   {a}   {b2}")
        if bal <= 0:
            print(f"\n{R}{B}BUSTED!{RESET}")
            break
        if delay and not os.environ.get("NO_DELAY"):
            time.sleep(delay)

    print(f"\n{C}{'═'*50}{RESET}")
    print(f"  Session over.  Bets: {bets}   Wins: {wins} ({100*wins/max(bets,1):.0f}%)")
    print(f"  Peak balance: {peak:.2f}   Biggest win: {biggest:.2f}")
    print(f"  Final balance: {B}{bal:.2f}{RESET}  ({G if bal>=bankroll else R}{bal-bankroll:+.2f}{RESET})")
    print(f"{C}{'═'*50}{RESET}\n")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "batch"
    if mode == "live":
        s_id = sys.argv[2] if len(sys.argv) > 2 else "5"
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
        live(s_id, n)
    else:
        batch()
