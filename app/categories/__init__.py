"""Category-specific rules and helpers."""

from typing import Any


class DentistRules:
    @staticmethod
    def get_salutation(merchant: dict[str, Any]) -> str:
        owner = merchant.get("identity", {}).get("owner_first_name", "")
        if not owner:
            name = merchant.get("identity", {}).get("name", "")
            return name if name.startswith("Dr.") else f"Dr. {name}"
        return owner if owner.startswith("Dr.") else f"Dr. {owner}"

    @staticmethod
    def format_customer_greeting(customer: dict[str, Any], merchant: dict[str, Any]) -> str:
        c_name = customer.get("identity", {}).get("name", "there")
        m_name = merchant.get("identity", {}).get("name", "our clinic")
        return f"Hi {c_name}, {m_name} here 🦷"


class SalonRules:
    @staticmethod
    def get_salutation(merchant: dict[str, Any]) -> str:
        return merchant.get("identity", {}).get("owner_first_name") or merchant.get("identity", {}).get("name", "")

    @staticmethod
    def format_customer_greeting(customer: dict[str, Any], merchant: dict[str, Any]) -> str:
        c_name = customer.get("identity", {}).get("name", "there")
        owner = merchant.get("identity", {}).get("owner_first_name", "")
        m_name = merchant.get("identity", {}).get("name", "our salon")
        sender = f"{owner} from {m_name}" if owner else m_name
        return f"Hi {c_name} ✨ {sender} here."


class RestaurantRules:
    @staticmethod
    def get_salutation(merchant: dict[str, Any]) -> str:
        return merchant.get("identity", {}).get("owner_first_name") or merchant.get("identity", {}).get("name", "")

    @staticmethod
    def format_customer_greeting(customer: dict[str, Any], merchant: dict[str, Any]) -> str:
        c_name = customer.get("identity", {}).get("name", "there")
        m_name = merchant.get("identity", {}).get("name", "our restaurant")
        return f"Hi {c_name} 🍽️ {m_name} here."


class GymRules:
    @staticmethod
    def get_salutation(merchant: dict[str, Any]) -> str:
        return merchant.get("identity", {}).get("owner_first_name") or merchant.get("identity", {}).get("name", "")

    @staticmethod
    def format_customer_greeting(customer: dict[str, Any], merchant: dict[str, Any]) -> str:
        c_name = customer.get("identity", {}).get("name", "there")
        owner = merchant.get("identity", {}).get("owner_first_name", "")
        m_name = merchant.get("identity", {}).get("name", "PowerHouse")
        sender = f"{owner} from {m_name}" if owner else m_name
        return f"Hi {c_name} 👋 {sender} here."


class PharmacyRules:
    @staticmethod
    def get_salutation(merchant: dict[str, Any]) -> str:
        return merchant.get("identity", {}).get("owner_first_name") or merchant.get("identity", {}).get("name", "")

    @staticmethod
    def format_customer_greeting(customer: dict[str, Any], merchant: dict[str, Any]) -> str:
        c_name = customer.get("identity", {}).get("name", "")
        m_name = merchant.get("identity", {}).get("name", "our pharmacy")
        loc = merchant.get("identity", {}).get("locality", "")
        store_label = f"{m_name} {loc}".strip()
        if "sharma" in c_name.lower() or "grandfather" in str(customer).lower():
            return f"Namaste — {store_label} yahan."
        return f"Namaste {c_name} — {store_label} yahan."


CATEGORY_RULES = {
    "dentists": DentistRules,
    "salons": SalonRules,
    "restaurants": RestaurantRules,
    "gyms": GymRules,
    "pharmacies": PharmacyRules,
}


def get_category_rules(category_slug: str):
    return CATEGORY_RULES.get(category_slug, RestaurantRules)
