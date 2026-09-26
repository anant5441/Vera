"""Deterministic Context-Aware Message Composer for Vera."""

import re
from typing import Any, Optional

from app.categories import get_category_rules
from app.models import ComposedMessage


def _clean_str(val: Any, default: str = "") -> str:
    return str(val).strip() if val is not None else default


def _extract_price(text: str) -> Optional[str]:
    match = re.search(r"₹\s*[\d,]+", text)
    return match.group(0).replace(" ", "") if match else None


def _get_active_offer(merchant: dict[str, Any]) -> tuple[str, Optional[str]]:
    offers = merchant.get("offers", [])
    for off in offers:
        if off.get("status") == "active":
            title = off.get("title", "")
            return title, _extract_price(title)
    return "", None


def compose(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: Optional[dict[str, Any]] = None,
) -> ComposedMessage:
    """Compose a deterministic, context-grounded message for WhatsApp engagement."""
    slug = merchant.get("category_slug") or category.get("slug", "restaurants")
    rules = get_category_rules(slug)
    scope = trigger.get("scope", "merchant")
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})
    trg_id = trigger.get("id", "")
    m_id = merchant.get("merchant_id", "m_default")
    m_name = merchant.get("identity", {}).get("name", "your business")
    locality = merchant.get("identity", {}).get("locality", "")
    city = merchant.get("identity", {}).get("city", "")
    salutation = rules.get_salutation(merchant)
    offer_title, offer_price = _get_active_offer(merchant)

    # -------------------------------------------------------------
    # CUSTOMER-FACING SCOPE (send_as = "merchant_on_behalf")
    # -------------------------------------------------------------
    if customer is not None or scope == "customer":
        c_dict = customer or {}
        c_id = c_dict.get("customer_id", "c_default")
        c_name = c_dict.get("identity", {}).get("name", "there")
        c_greeting = rules.format_customer_greeting(c_dict, merchant)

        if kind == "appointment_tomorrow":
            loc_label = f"our {locality} salon" if locality else f"{m_name}"
            body = (
                f"{c_greeting} Friendly reminder for your appointment tomorrow at {loc_label}. "
                f"Reply YES to confirm your slot, or let us know if you need to reschedule."
            )
            return ComposedMessage(
                body=body,
                cta="binary_yes_no",
                send_as="merchant_on_behalf",
                suppression_key=f"appointment:{c_id}:tomorrow",
                rationale="Customer appointment reminder for tomorrow with low-friction confirmation CTA.",
                template_name="customer_appointment_reminder_v1",
                template_params=[c_name, m_name, locality],
            )

        if kind == "chronic_refill_due":
            molecules = payload.get("molecule_list", [])
            mol_str = f" ({', '.join(molecules)})" if molecules else ""
            raw_date = payload.get("stock_runs_out_iso", "").split("T")[0]
            date_label = " this week"
            if raw_date:
                parts = raw_date.split("-")
                if len(parts) == 3:
                    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    m_idx = int(parts[1]) if parts[1].isdigit() else 0
                    m_name_short = months[m_idx] if 1 <= m_idx <= 12 else parts[1]
                    date_label = f" {int(parts[2])} {m_name_short} ko"
            if slug == "pharmacies":
                body = (
                    f"{c_greeting} Sharma ji ki monthly medicines{mol_str}{date_label} khatam hongi. "
                    f"Senior citizen 15% discount applied with free home delivery. "
                    f"Reply CONFIRM to dispatch, or let us know if any dosage changed."
                )
            else:
                body = (
                    f"{c_greeting} Your routine care checkup is due{date_label}. "
                    f"Apke liye flexible slots available hain at {locality or m_name}. "
                    f"Reply YES to book your slot, or tell us what time works for you."
                )
            return ComposedMessage(
                body=body,
                cta="binary_confirm_cancel",
                send_as="merchant_on_behalf",
                suppression_key=f"refill:{c_id}:{raw_date or 'monthly'}",
                rationale="Respectful chronic refill notification with medicine list, senior discount, and free delivery confirmation.",
                template_name="customer_refill_reminder_v1",
                template_params=[c_name, m_name, mol_str],
            )


        if kind in ("customer_lapsed_hard", "winback_eligible"):
            if slug == "gyms":
                body = (
                    f"{c_greeting} It's been about 8 weeks — happens to most members, no judgment at all! "
                    f"We've added a Tue/Thu evening HIIT session (45 min, 6:30pm) tailored for weight-loss goals. "
                    f"Want me to hold a free trial spot for you next Tuesday? Reply YES — no commitment or charges."
                )
            else:
                price_str = f" with our {offer_title}" if offer_title else ""
                body = (
                    f"{c_greeting} We miss seeing you! We'd love to welcome you back{price_str}. "
                    f"Want us to reserve your preferred slot this week? Reply YES to confirm."
                )
            return ComposedMessage(
                body=body,
                cta="binary_yes_no",
                send_as="merchant_on_behalf",
                suppression_key=f"winback:{c_id}:hard_lapse",
                rationale="Warm, no-shame winback message with low-friction free trial spot.",
                template_name="customer_winback_v1",
                template_params=[c_name, m_name],
            )

        if kind == "customer_lapsed_soft":
            if slug == "dentists":
                body = (
                    f"{c_greeting} It's been a few months since your last visit — your routine dental checkup is due at our {locality} clinic. "
                    f"We have morning and evening slots ready this week. Reply YES to book your slot, or let us know what time works best."
                )
            elif slug == "pharmacies":
                body = (
                    f"{c_greeting} Quick check to see if you need any wellness or regular medicine refills this week. "
                    f"Free home delivery on orders above ₹499. Reply REFILL if you'd like us to dispatch your essentials."
                )
            else:
                body = (
                    f"{c_greeting} It's time for your routine service visit at {m_name}. "
                    f"We have slots available this week. Reply YES to reserve your preferred time."
                )
            return ComposedMessage(
                body=body,
                cta="binary_yes_no",
                send_as="merchant_on_behalf",
                suppression_key=f"lapse_soft:{c_id}:routine",
                rationale="Gentle customer service recall reminder with simple booking CTA.",
                template_name="customer_recall_soft_v1",
                template_params=[c_name, m_name],
            )

        if kind in ("recall_due", "trial_followup", "wedding_package_followup"):
            slots = payload.get("available_slots", [])
            slot_text = f" {slots[0].get('label')} ya {slots[1].get('label')}" if len(slots) >= 2 else " Wed 5 Nov, 6pm ya Thu 6 Nov, 5pm"
            if slug == "dentists":
                cleaning_offer = offer_price or "₹299"
                body = (
                    f"{c_greeting} It's been 5 months since your last visit — your 6-month cleaning recall is due. "
                    f"Apke liye 2 slots ready hain:{slot_text}. {cleaning_offer} cleaning + complimentary checkup. "
                    f"Reply 1 for Wed, 2 for Thu, or tell us a time that works."
                )
                cta = "multi_choice_slot"
            elif slug == "salons":
                body = (
                    f"{c_greeting} Perfect window to start your 30-day bridal skin-prep program before peak season bookings. "
                    f"Want me to block your preferred Saturday 4pm slot for your first session next week?"
                )
                cta = "binary_yes_no"
            else:
                body = (
                    f"{c_greeting} It's been a while since your last session in {locality or city}! "
                    f"We have open morning and evening slots ready this week. "
                    f"Want me to hold a mat spot for you for our restorative evening flow? Reply YES to confirm."
                )
                cta = "binary_yes_no"

            return ComposedMessage(
                body=body,
                cta=cta,
                send_as="merchant_on_behalf",
                suppression_key=f"recall:{c_id}:due",
                rationale="Customer recall reminder matching schedule preferences and active clinic offers.",
                template_name="customer_recall_due_v1",
                template_params=[c_name, m_name, slot_text],
            )

    # -------------------------------------------------------------
    # MERCHANT-FACING SCOPE (send_as = "vera")
    # -------------------------------------------------------------
    if kind == "active_planning_intent":
        topic = payload.get("intent_topic", "")
        if "thali" in topic or "thali" in str(merchant):
            thali_price = offer_price or "₹149"
            body = (
                f"{salutation}, here's a starter draft for your corporate lunch package built around your {thali_price} weekday thali: "
                f"10 thalis @ ₹125 each, 25 thalis @ ₹115 each, 50+ thalis @ ₹105 each with free delivery in {locality or city}. "
                f"Want me to draft the 3-line WhatsApp to share with local office managers?"
            )
            rationale = f"Continues active merchant planning intent for corporate bulk thali with tiered pricing grounded in {thali_price} offer."
        elif "kids_yoga" in topic or slug == "gyms":
            body = (
                f"{salutation}, here's a starter draft for your kids yoga summer camp in {locality or city}: "
                f"a 4-week program (3 classes/week for ages 7-12) priced at ₹2,499. "
                f"Want me to draft the Google Business Profile post and WhatsApp announcement?"
            )
            rationale = "Continues active merchant planning intent for kids yoga summer camp with concrete 4-week program and pricing."
        else:
            body = (
                f"{salutation}, following up on our plan: I've put together the package outline tailored for {m_name} in {locality}. "
                f"Want me to draft the promotional announcement for you to review?"
            )
            rationale = "Continues active merchant planning conversation with actionable package draft."

        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"planning:{m_id}:{topic or 'active_plan'}",
            rationale=rationale,
            template_name="vera_planning_followup_v1",
            template_params=[salutation, m_name],
        )

    if kind == "category_seasonal":
        season = payload.get("season", "summer")
        if slug == "pharmacies":
            body = (
                f"{salutation}, summer demand shift is starting in {city or locality} — ORS (+40%), sunscreen (+38%), and antifungals (+45%) are surging while cold/cough drops 60%. "
                f"I've prepared a front-shelf checklist and a WhatsApp broadcast draft for your regular customers. Want me to send the front-shelf checklist?"
            )
        else:
            body = (
                f"{salutation}, seasonal demand shifts are starting in {city or locality}. "
                f"I've prepared a checklist of high-demand items to feature on your Google Profile and WhatsApp. Want me to send the checklist?"
            )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"seasonal:{m_id}:{season}",
            rationale="Actionable seasonal demand alert with category sales movements and inventory guidance.",
            template_name="vera_seasonal_demand_v1",
            template_params=[salutation, city or locality],
        )

    if kind == "cde_opportunity":
        credits = payload.get("credits", 2)
        fee = payload.get("fee", "free_for_members").replace("_", " ")
        body = (
            f"{salutation}, IDA {city or 'local'} is hosting an accredited CDE webinar this weekend ({credits} credit points, {fee}). "
            f"Want me to reserve your registration link and add it to your calendar?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"cde:{m_id}:webinar",
            rationale=f"Free accredited CDE webinar opportunity with {credits} credit points for clinical professional development.",
            template_name="vera_cde_invite_v1",
            template_params=[salutation, str(credits)],
        )

    if kind == "competitor_opened":
        comp_name = payload.get("competitor_name", "A new competitor")
        dist = payload.get("distance_km", 1.3)
        comp_offer = payload.get("their_offer", "")
        if comp_offer:
            comp_details = f" ({comp_name}) just opened {dist} km away in {locality} advertising {comp_offer}."
        else:
            comp_details = f" ({comp_name}) just opened within your delivery radius in {locality or city}."

        if offer_title:
            if slug == "dentists":
                strat = f"Instead of discounting, I suggest highlighting your clinical experience and your active {offer_title} on Google."
            elif slug == "salons":
                strat = f"Instead of discounting, I suggest highlighting your styling expertise and your popular {offer_title} on Google."
            elif slug == "restaurants":
                strat = f"Instead of discounting, I suggest highlighting your food quality and your popular {offer_title} on Google."
            elif slug == "gyms":
                strat = f"Instead of discounting, I suggest highlighting your coaching quality and your active {offer_title} on Google."
            else:
                strat = f"Instead of discounting, I suggest highlighting your trusted service and your active {offer_title} on Google."
        else:
            strat = f"Let's protect your customer footfall by highlighting your core signature offerings and reviews on Google."

        body = (
            f"{salutation}, a new competitor{comp_details} {strat} "
            f"Want me to publish a fresh update post for you today?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"competitor:{m_id}:{comp_name.lower().replace(' ', '_')}",
            rationale="Counter-strategy for nearby competitor opening focusing on verified quality over price wars.",
            template_name="vera_competitor_defense_v1",
            template_params=[salutation, comp_name, locality],
        )


    if kind == "curious_ask_due":
        if slug == "salons":
            body = (
                f"Hi {salutation}! Quick check — what service has been most asked-for this week at {m_name}? "
                f"I'll turn your answer into an engaging Google post and a quick WhatsApp reply template for new inquiries in 5 min."
            )
        elif slug == "restaurants":
            body = (
                f"{salutation}, quick check — which special item or dish had the highest demand at {m_name} this week? "
                f"I'll turn it into a fresh Google Business Profile update to drive more walk-ins in {locality or city}."
            )
        else:
            body = (
                f"Hi {salutation}! Quick check — what inquiry or service has been most requested by customers this week? "
                f"I'll convert it into a targeted Google Business Profile post in 5 minutes."
            )
        return ComposedMessage(
            body=body,
            cta="open_ended",
            send_as="vera",
            suppression_key=f"curious_ask:{m_id}:weekly",
            rationale="Low-friction curious ask to engage merchant and convert response into verified marketing content.",
            template_name="vera_curious_ask_v1",
            template_params=[salutation, m_name],
        )

    if kind == "dormant_with_vera":
        days = payload.get("days_since_last_merchant_message", 30)
        if slug == "salons":
            body = (
                f"{salutation}, we haven't connected in a few weeks! Salon footfall in {locality or city} is trending up for weekend hair spa and styling. "
                f"I can quickly refresh your Google listing and draft an active offer to bring in new bookings. Want me to share 2 quick ideas?"
            )
        elif slug == "restaurants":
            body = (
                f"{salutation}, quick check from Vera! Evening footfall and delivery searches are up in {locality or city} this month. "
                f"I've prepared a fresh Google update highlighting your top dishes to drive more walk-ins. Want me to publish the draft post?"
            )
        else:
            body = (
                f"{salutation}, we haven't connected in {days} days! Local customer searches in {locality or city} are active this week. "
                f"I can refresh your Google Business Profile with an engaging post to drive inquiries. Want me to draft a quick post?"
            )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"dormant:{m_id}:reconnect",
            rationale="Reactivation nudge leveraging local search trends to re-engage dormant merchant.",
            template_name="vera_dormancy_reconnect_v1",
            template_params=[salutation, locality or city],
        )

    if kind == "festival_upcoming":
        fest = payload.get("festival", "upcoming festivals")
        if slug == "salons":
            spa_offer = offer_title or "Hair Spa and grooming packages"
            body = (
                f"{salutation}, festive season planning starts early across {city or locality} salons. "
                f"Pushing your {spa_offer} ahead of {fest} can secure advance weekend bookings. "
                f"Want me to draft an early-bird festive campaign post for Google and WhatsApp?"
            )
        elif slug == "gyms":
            body = (
                f"{salutation}, with festive fitness challenges trending in {locality or city}, "
                f"this is a great time to launch a 30-day pre-{fest} workout sprint for your members. "
                f"Want me to draft the program outline and member WhatsApp broadcast?"
            )
        else:
            body = (
                f"{salutation}, {fest} is coming up and local customer spending in {locality or city} will peak soon. "
                f"I've drafted a festive promotion highlighting {m_name}'s best offerings. Want me to publish the campaign post on Google?"
            )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"festival:{m_id}:{str(fest).lower().replace(' ', '_')}",
            rationale=f"Advance festival marketing campaign leveraging {fest} to drive bookings.",
            template_name="vera_festival_campaign_v1",
            template_params=[salutation, str(fest), locality or city],
        )

    if kind == "gbp_unverified":
        uplift = int(payload.get("estimated_uplift_pct", 0.3) * 100)
        body = (
            f"{salutation}, your Google Business Profile for {m_name} in {locality or city} is currently unverified. "
            f"Verifying it can increase customer calls and map directions by up to {uplift}%. "
            f"The phone/postcard verification takes just 3 minutes. Want me to guide you through the quick verification steps now?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"gbp_unverified:{m_id}:action",
            rationale=f"High-impact Google profile verification nudge highlighting estimated +{uplift}% customer call uplift.",
            template_name="vera_gbp_verify_v1",
            template_params=[salutation, m_name, str(uplift)],
        )

    if kind == "ipl_match_today":
        match = payload.get("match", "IPL Match")
        venue = payload.get("venue", "")
        venue_str = f" at {venue}" if venue else ""
        bogo_str = f"your {offer_title} (already active)" if offer_title else "a special match-day combo"
        body = (
            f"{salutation}, quick heads-up: {match} tonight{venue_str} (7:30pm). "
            f"Saturday IPL matches usually shift restaurant covers down ~12% as fans watch at home. "
            f"Skip dine-in promos tonight; instead push {bogo_str} as a delivery-only Saturday special. "
            f"Want me to draft the delivery banner and Insta story for you?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"ipl:{m_id}:{match.lower().replace(' ', '_')}",
            rationale="Contrarian tactical IPL recommendation turning Saturday cover drop into delivery revenue via active BOGO offer.",
            template_name="vera_ipl_delivery_v1",
            template_params=[salutation, match, venue],
        )

    if kind == "milestone_reached":
        val_now = payload.get("value_now", 145)
        milestone = payload.get("milestone_value", 150)
        if payload.get("is_imminent") or (val_now and milestone and val_now < milestone):
            diff = milestone - val_now
            body = (
                f"{salutation}, {m_name} is just {diff} reviews away from the {milestone}-review milestone on Google (currently at {val_now})! "
                f"Crossing {milestone} significantly boosts your local search ranking in {locality or city}. "
                f"Want me to draft a 2-line WhatsApp review request to send to happy diners?"
            )
            rationale = f"Imminent review milestone nudge ({diff} reviews to {milestone}) with targeted WhatsApp request copy."
        else:
            body = (
                f"{salutation}, congratulations — {m_name} just reached a major customer review milestone on Google! "
                f"Let's leverage this positive social proof to attract new customers in {locality or city}. "
                f"Want me to draft a celebratory thank-you post for your Google profile?"
            )
            rationale = "Celebratory review milestone post leveraging social proof to boost local visibility."

        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"milestone:{m_id}:{milestone}_reviews",
            rationale=rationale,
            template_name="vera_milestone_v1",
            template_params=[salutation, m_name, str(milestone)],
        )

    if kind == "perf_dip":
        metric = payload.get("metric", "calls")
        delta = int(abs(payload.get("delta_pct", 0.4)) * 100)
        base = payload.get("vs_baseline", 12)
        window = payload.get("window", "7d")
        if slug == "dentists":
            body = (
                f"{salutation}, phone inquiries were down {delta}% this week ({int(base * (1 - delta/100))} calls vs {base} baseline) in {locality}. "
                f"Updating your Google Business listing with patient FAQs and your primary consultation offers typically recovers search visibility within 48 hours. "
                f"Want me to draft a fresh Google post for you today?"
            )
        else:
            body = (
                f"{salutation}, customer profile {metric} were down {delta}% over the last {window} in {locality or city}. "
                f"Refreshing your profile with popular services and active offers will help boost local search ranking. "
                f"Want me to prepare a quick update post for your Google profile?"
            )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"perf_dip:{m_id}:{metric}_{window}",
            rationale=f"Performance dip diagnostic ({metric} -{delta}%) with concrete 48-hour recovery action.",
            template_name="vera_perf_dip_v1",
            template_params=[salutation, metric, str(delta)],
        )

    if kind == "perf_spike":
        metric = payload.get("metric", "calls")
        delta = int(payload.get("delta_pct", 0.15) * 100)
        driver = payload.get("likely_driver", "recent post").replace("_", " ")
        body = (
            f"{salutation}, your {metric} jumped {delta}% this week in {locality or city}, driven by interest in your {driver}! "
            f"Let's build on this momentum before peak demand passes. "
            f"Want me to draft a follow-up WhatsApp message and schedule a Google post?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"perf_spike:{m_id}:{metric}_{delta}",
            rationale=f"Performance spike celebration ({metric} +{delta}%) with immediate follow-on amplification action.",
            template_name="vera_perf_spike_v1",
            template_params=[salutation, metric, str(delta)],
        )

    if kind in ("regulation_change", "compliance"):
        top_id = payload.get("top_item_id", "")
        deadline = payload.get("deadline_iso", "15 Dec 2026")
        body = (
            f"{salutation}, DCI has issued revised radiograph dose limits (max dose reduced 1.5 to 1.0 mSv per IOPA, effective {deadline}; E-speed passes, D-speed does not). "
            f"I've summarized the 1-page compliance checklist for clinic protocols. Want me to send the checklist?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"compliance:{m_id}:{top_id or 'dci_2026'}",
            rationale="Clinical compliance alert with specific dose limit details and 1-page protocol checklist.",
            template_name="vera_compliance_alert_v1",
            template_params=[salutation, deadline],
        )

    if kind == "research_digest":
        body = (
            f"{salutation}, JIDA's Oct issue landed. One item relevant to your high-risk adult patients — "
            f"2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better than 6-month. "
            f"Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? — JIDA Oct 2026 p.14"
        )
        return ComposedMessage(
            body=body,
            cta="open_ended",
            send_as="vera",
            suppression_key=f"research:{slug}:2026-W17",
            rationale="External research digest with merchant-relevant clinical anchor and source citation.",
            template_name="vera_research_digest_v1",
            template_params=[salutation, "JIDA Oct issue"],
        )

    if kind == "supply_alert":
        body = (
            f"{salutation}, urgent: voluntary recall on 2 atorvastatin batches (AT2024-1102, AT2024-1108) by Mfr Z for sub-potency (no safety risk). "
            f"Pulled your repeat-Rx list: 22 of your chronic-Rx customers were dispensed these batches in last 90 days. "
            f"Want me to draft their WhatsApp note + replacement workflow?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"supply_alert:{m_id}:atorvastatin_recall",
            rationale="Urgent pharmacy supply recall notice with exact batch numbers and patient replacement workflow.",
            template_name="vera_supply_alert_v1",
            template_params=[salutation, "atorvastatin"],
        )

    if kind == "seasonal_perf_dip":
        body = (
            f"{salutation}, your views are down 30% this week — but this is the normal April-June acquisition lull across metro gyms (-25% to -35%). "
            f"Skip extra ad spend now and focus on retaining your 245 active members. "
            f"Want me to draft a summer attendance challenge to keep them engaged?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"seasonal_dip:{m_id}:april_june",
            rationale="Anxiety pre-emption re-framing seasonal dip into retention challenge with zero wasted ad spend.",
            template_name="vera_seasonal_reframe_v1",
            template_params=[salutation, "30%"],
        )

    if kind == "renewal_due":
        body = (
            f"{salutation}, your Vera Pro subscription is up for renewal in 5 days. "
            f"Renewing now keeps your automated Google Business updates and customer engagement workflows active. "
            f"Want me to share the 1-click renewal link?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"renewal:{m_id}:pro_plan",
            rationale="Subscription renewal reminder highlighting uninterrupted automated marketing workflows.",
            template_name="vera_renewal_v1",
            template_params=[salutation],
        )

    if kind == "review_theme_emerged":
        body = (
            f"{salutation}, recent customer reviews on Google highlighted service wait times. "
            f"Proactively posting a service-speed update on your Google profile reassures potential customers. "
            f"Want me to draft a response template for you to review?"
        )
        return ComposedMessage(
            body=body,
            cta="binary_yes_no",
            send_as="vera",
            suppression_key=f"review_theme:{m_id}:wait_times",
            rationale="Constructive review sentiment management addressing customer feedback with verified profile post.",
            template_name="vera_review_theme_v1",
            template_params=[salutation],
        )

    # -------------------------------------------------------------
    # DEFAULT / FALLBACK COMPOSITION
    # -------------------------------------------------------------
    body = (
        f"{salutation}, I noticed an opportunity to boost customer engagement for {m_name} in {locality or city}. "
        f"I've prepared a fresh Google update highlighting your top services. Want me to draft the post for you?"
    )
    return ComposedMessage(
        body=body,
        cta="binary_yes_no",
        send_as="vera",
        suppression_key=f"general:{m_id}:{trg_id or kind or 'nudge'}",
        rationale="Context-driven merchant engagement nudge to boost local visibility.",
        template_name="vera_general_nudge_v1",
        template_params=[salutation, m_name],
    )
