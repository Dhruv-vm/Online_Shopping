"""Assistant message templates (English and Hindi; other languages fall back to English).

The negotiator is a deterministic, rule-bound engine. No large language model is
called: prices are computed from retailer rules and messages are templates.
"""

from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "opening": "Your basket lists at ₹{list}. I can offer ₹{offer} right now.",
        "nothing": "These sellers have not enabled negotiation for the items in your basket. The listed price of ₹{list} is the best available.",
        "counter": "I can't go to ₹{proposed}, but I can improve my offer to ₹{offer}.",
        "final": "₹{offer} is the best price the sellers allow. Accept it or keep the listed price.",
        "agree": "Deal! ₹{agreed} works. Tap accept to lock it in for 15 minutes.",
        "already_better": "My current offer of ₹{offer} is already lower than ₹{proposed}. Tap accept to lock it in.",
        "over_budget": "Even the best price (₹{offer}) is above your budget of ₹{budget}. Consider substitutes for some items.",
        "accepted": "Locked in at ₹{agreed}. Proceed to checkout before the quote expires.",
    },
    "hi": {
        "opening": "आपकी टोकरी की सूची कीमत ₹{list} है। मैं अभी ₹{offer} दे सकता हूँ।",
        "nothing": "इन विक्रेताओं ने आपकी टोकरी के सामान पर मोलभाव चालू नहीं किया है। ₹{list} ही सबसे अच्छी कीमत है।",
        "counter": "₹{proposed} संभव नहीं है, लेकिन मैं अपना ऑफ़र ₹{offer} कर सकता हूँ।",
        "final": "₹{offer} विक्रेताओं द्वारा अनुमत सबसे अच्छी कीमत है। स्वीकार करें या सूची कीमत रखें।",
        "agree": "सौदा पक्का! ₹{agreed} ठीक है। 15 मिनट के लिए लॉक करने हेतु स्वीकार करें।",
        "already_better": "मेरा मौजूदा ऑफ़र ₹{offer} पहले से ₹{proposed} से कम है। लॉक करने के लिए स्वीकार करें।",
        "over_budget": "सबसे अच्छी कीमत (₹{offer}) भी आपके बजट ₹{budget} से अधिक है। कुछ सामान के विकल्प देखें।",
        "accepted": "₹{agreed} पर लॉक हो गया। कोटेशन समाप्त होने से पहले चेकआउट करें।",
    },
}


def render(language: str, key: str, **amounts_paise: int) -> tuple[str, bool]:
    table = TEMPLATES.get(language)
    fallback = table is None
    table = table or TEMPLATES["en"]
    fmt = {k: f"{v / 100:,.2f}" for k, v in amounts_paise.items()}
    return table[key].format(**fmt), fallback
