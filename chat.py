"""Interactive WhatsApp Chat Session with Vera."""

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.composer import compose
from app.state import store

DATASET_DIR = Path("magicpin-ai-challenge/expanded")


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


PRESETS = [
    {
        "name": "Mylari South Indian Cafe (Restaurant - Corporate Bulk Thali)",
        "merchant_id": "m_006_southindiancafe_restaurant_bangalore",
        "trigger_id": "trg_013_corporate_thali_planning",
        "customer_id": None,
    },
    {
        "name": "Dr. Meera's Dental Clinic (Dentist - JIDA Research Digest)",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "trigger_id": "trg_022_cde_webinar_dentists",
        "customer_id": None,
    },
    {
        "name": "Studio11 Family Salon (Salon - Curious Ask / Service Demand)",
        "merchant_id": "m_003_studio11_salon_hyderabad",
        "trigger_id": "trg_008_curious_ask_studio11",
        "customer_id": None,
    },
    {
        "name": "PowerHouse Fitness (Gym - Member Winback)",
        "merchant_id": "m_007_powerhouse_gym_bangalore",
        "trigger_id": "trg_015_winback_rashmi",
        "customer_id": "c_010_rashmi_for_m007",
    },
    {
        "name": "Apollo Health Plus Pharmacy (Pharmacy - Summer Demand Shift)",
        "merchant_id": "m_009_apollo_pharmacy_jaipur",
        "trigger_id": "trg_020_summer_demand_shift",
        "customer_id": None,
    },
    {
        "name": "SK Pizza Junction (Restaurant - IPL Match Day)",
        "merchant_id": "m_005_pizzajunction_restaurant_delhi",
        "trigger_id": "trg_010_ipl_match_delhi",
        "customer_id": None,
    },
]


def load_context(merchant_id: str, trigger_id: str, customer_id: str | None):
    m = json.loads((DATASET_DIR / "merchants" / f"{merchant_id}.json").read_text(encoding="utf-8"))
    trg = json.loads((DATASET_DIR / "triggers" / f"{trigger_id}.json").read_text(encoding="utf-8"))
    c = (
        json.loads((DATASET_DIR / "customers" / f"{customer_id}.json").read_text(encoding="utf-8"))
        if customer_id
        else None
    )
    cat_slug = m.get("category_slug", "restaurants")
    cat = json.loads((DATASET_DIR / "categories" / f"{cat_slug}.json").read_text(encoding="utf-8"))
    return cat, m, trg, c


def print_banner():
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 65}")
    print("        💬  VERA INTERACTIVE WHATSAPP SIMULATOR  💬        ")
    print(f"{'=' * 65}{Colors.RESET}\n")


def main():
    print_banner()
    print(f"{Colors.BOLD}Select a conversation scenario to start:{Colors.RESET}\n")
    for i, p in enumerate(PRESETS, start=1):
        print(f"  {Colors.GREEN}[{i}]{Colors.RESET} {p['name']}")
    print(f"  {Colors.DIM}[q] Quit{Colors.RESET}\n")

    choice = input(f"{Colors.BOLD}Choose scenario (1-{len(PRESETS)}): {Colors.RESET}").strip()
    if choice.lower() == "q":
        return

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(PRESETS)):
            print(f"{Colors.RED}Invalid choice.{Colors.RESET}")
            return
    except ValueError:
        print(f"{Colors.RED}Invalid input.{Colors.RESET}")
        return

    selected = PRESETS[idx]
    cat, m, trg, c = load_context(
        selected["merchant_id"], selected["trigger_id"], selected["customer_id"]
    )

    owner = m["identity"].get("owner_first_name", "Merchant")
    m_name = m["identity"].get("name", "Your Business")
    role_label = (
        f"Customer ({c['identity']['name']})" if c else f"Merchant ({owner} @ {m_name})"
    )

    # Initial composition
    composed = compose(cat, m, trg, c)
    conv_id = f"interactive_conv_{selected['merchant_id']}"

    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Conversation Started ---{Colors.RESET}")
    print(f"{Colors.DIM}Persona: {role_label}")
    print(f"Trigger: {trg.get('kind')} | Scope: {composed.send_as}{Colors.RESET}\n")

    # Initial Vera message
    sender_name = "Vera (AI Assistant)" if composed.send_as == "vera" else f"{m_name} (on-behalf)"
    print(f"{Colors.GREEN}{Colors.BOLD}{sender_name}:{Colors.RESET}")
    print(f"  {composed.body}\n")
    print(f"  {Colors.DIM}[CTA: {composed.cta} | Suppression: {composed.suppression_key}]{Colors.RESET}")
    print(f"  {Colors.DIM}Rationale: {composed.rationale}{Colors.RESET}\n")

    turn = 1
    while True:
        try:
            print(f"{Colors.YELLOW}{Colors.BOLD}You ({role_label}):{Colors.RESET}")
            user_msg = input("  > ").strip()

            if not user_msg:
                continue
            if user_msg.lower() in ("exit", "quit", "q"):
                print(f"\n{Colors.CYAN}Exiting interactive chat. Goodbye! 👋{Colors.RESET}\n")
                break

            turn += 1
            reply_res = store.handle_reply(
                conversation_id=conv_id,
                merchant_id=selected["merchant_id"],
                customer_id=selected["customer_id"],
                from_role="merchant" if not c else "customer",
                message=user_msg,
                turn_number=turn,
            )

            print(f"\n{Colors.GREEN}{Colors.BOLD}Vera:{Colors.RESET}")
            if reply_res.action == "send" and reply_res.body:
                print(f"  {reply_res.body}\n")
                print(f"  {Colors.DIM}[Action: SEND | CTA: {reply_res.cta}]{Colors.RESET}")
            elif reply_res.action == "wait":
                print(f"  {Colors.DIM}⏳ [Action: WAIT {reply_res.wait_seconds}s (e.g. Auto-reply cooldown)]{Colors.RESET}")
            elif reply_res.action == "end":
                print(f"  {Colors.RED}🛑 [Action: END — Conversation closed gracefully]{Colors.RESET}")

            print(f"  {Colors.DIM}Rationale: {reply_res.rationale}{Colors.RESET}\n")

            if reply_res.action == "end":
                print(f"{Colors.DIM}Conversation has ended. Type 'q' to exit or start another scenario.{Colors.RESET}\n")
                break

        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.CYAN}Session ended.{Colors.RESET}")
            break


if __name__ == "__main__":
    main()
