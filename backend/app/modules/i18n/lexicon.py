"""Seed Indic shopping lexicon for search-query normalisation (Phase 3H).

Maps common grocery/household terms written in the 11 supported Indian-language scripts
(and common romanised forms) to the English catalogue vocabulary. This is a
deterministic seed dictionary, not machine translation: unknown words pass
through unchanged. Entries should be reviewed and extended by native speakers;
admins can additionally attach translated product names via
``content_translations``, which the PostgreSQL search fallback also matches.
"""

from __future__ import annotations

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "native": "English", "script": "Latin"},
    "hi": {"name": "Hindi", "native": "हिन्दी", "script": "Devanagari"},
    "ta": {"name": "Tamil", "native": "தமிழ்", "script": "Tamil"},
    "te": {"name": "Telugu", "native": "తెలుగు", "script": "Telugu"},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "script": "Kannada"},
    "bn": {"name": "Bengali", "native": "বাংলা", "script": "Bengali"},
    "mr": {"name": "Marathi", "native": "मराठी", "script": "Devanagari"},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "script": "Gujarati"},
    "ml": {"name": "Malayalam", "native": "മലയാളം", "script": "Malayalam"},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "script": "Gurmukhi"},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ", "script": "Odia"},
    "ur": {"name": "Urdu", "native": "اردو", "script": "Perso-Arabic"},
}

# english term -> {lang: [native forms...]}
_TERMS: dict[str, dict[str, list[str]]] = {
    "milk": {
        "hi": ["दूध"],
        "mr": ["दूध"],
        "ta": ["பால்"],
        "te": ["పాలు"],
        "kn": ["ಹಾಲು"],
        "bn": ["দুধ"],
        "gu": ["દૂધ"],
        "rom": ["doodh", "dudh"],
    },
    "rice": {
        "hi": ["चावल"],
        "mr": ["तांदूळ"],
        "ta": ["அரிசி"],
        "te": ["బియ్యం"],
        "kn": ["ಅಕ್ಕಿ"],
        "bn": ["চাল"],
        "gu": ["ચોખા"],
        "rom": ["chawal", "chaval"],
    },
    "sugar": {
        "hi": ["चीनी"],
        "mr": ["साखर"],
        "ta": ["சர்க்கரை"],
        "te": ["చక్కెర"],
        "kn": ["ಸಕ್ಕರೆ"],
        "bn": ["চিনি"],
        "gu": ["ખાંડ"],
        "rom": ["cheeni", "chini", "shakkar"],
    },
    "salt": {
        "hi": ["नमक"],
        "mr": ["मीठ"],
        "ta": ["உப்பு"],
        "te": ["ఉప్పు"],
        "kn": ["ಉಪ್ಪು"],
        "bn": ["লবণ"],
        "gu": ["મીઠું"],
        "rom": ["namak"],
    },
    "oil": {
        "hi": ["तेल"],
        "mr": ["तेल"],
        "ta": ["எண்ணெய்"],
        "te": ["నూనె"],
        "kn": ["ಎಣ್ಣೆ"],
        "bn": ["তেল"],
        "gu": ["તેલ"],
        "rom": ["tel"],
    },
    "atta flour": {
        "hi": ["आटा"],
        "mr": ["पीठ"],
        "ta": ["மாவு"],
        "te": ["పిండి"],
        "kn": ["ಹಿಟ್ಟು"],
        "bn": ["আটা"],
        "gu": ["લોટ"],
        "rom": ["atta", "aata"],
    },
    "tea": {
        "hi": ["चाय"],
        "mr": ["चहा"],
        "ta": ["தேநீர்"],
        "te": ["టీ"],
        "kn": ["ಚಹಾ"],
        "bn": ["চা"],
        "gu": ["ચા"],
        "rom": ["chai", "chay"],
    },
    "soap": {
        "hi": ["साबुन"],
        "mr": ["साबण"],
        "ta": ["சோப்பு"],
        "te": ["సబ్బు"],
        "kn": ["ಸಾಬೂನು"],
        "bn": ["সাবান"],
        "gu": ["સાબુ"],
        "rom": ["sabun"],
    },
    "butter": {
        "hi": ["मक्खन"],
        "mr": ["लोणी"],
        "ta": ["வெண்ணெய்"],
        "te": ["వెన్న"],
        "kn": ["ಬೆಣ್ಣೆ"],
        "bn": ["মাখন"],
        "gu": ["માખણ"],
        "rom": ["makhan", "makkhan"],
    },
    "dal lentils": {
        "hi": ["दाल"],
        "mr": ["डाळ"],
        "ta": ["பருப்பு"],
        "te": ["పప్పు"],
        "kn": ["ಬೇಳೆ"],
        "bn": ["ডাল"],
        "gu": ["દાળ"],
        "rom": ["dal", "daal"],
    },
    "eggs": {
        "hi": ["अंडा", "अंडे"],
        "mr": ["अंडी"],
        "ta": ["முட்டை"],
        "te": ["గుడ్డు"],
        "kn": ["ಮೊಟ್ಟೆ"],
        "bn": ["ডিম"],
        "gu": ["ઈંડા"],
        "rom": ["anda", "ande"],
    },
    "ghee": {
        "hi": ["घी"],
        "mr": ["तूप"],
        "ta": ["நெய்"],
        "te": ["నెయ్యి"],
        "kn": ["ತುಪ್ಪ"],
        "bn": ["ঘি"],
        "gu": ["ઘી"],
        "rom": ["ghee", "ghi"],
    },
    "curd yogurt": {
        "hi": ["दही"],
        "mr": ["दही"],
        "ta": ["தயிர்"],
        "te": ["పెరుగు"],
        "kn": ["ಮೊಸರು"],
        "bn": ["দই"],
        "gu": ["દહીં"],
        "rom": ["dahi"],
    },
    "water": {
        "hi": ["पानी"],
        "mr": ["पाणी"],
        "ta": ["தண்ணீர்"],
        "te": ["నీళ్ళు"],
        "kn": ["ನೀರು"],
        "bn": ["জল"],
        "gu": ["પાણી"],
        "rom": ["paani", "pani"],
    },
    "onion": {
        "hi": ["प्याज"],
        "mr": ["कांदा"],
        "ta": ["வெங்காயம்"],
        "te": ["ఉల్లిపాయ"],
        "kn": ["ಈರುಳ್ಳಿ"],
        "bn": ["পেঁয়াজ"],
        "gu": ["ડુંગળી"],
        "rom": ["pyaz", "pyaaz", "kanda"],
    },
    "potato": {
        "hi": ["आलू"],
        "mr": ["बटाटा"],
        "ta": ["உருளைக்கிழங்கு"],
        "te": ["బంగాళాదుంప"],
        "kn": ["ಆಲೂಗಡ್ಡೆ"],
        "bn": ["আলু"],
        "gu": ["બટાકા"],
        "rom": ["aloo", "alu", "batata"],
    },
    "mobile phone": {
        "hi": ["मोबाइल", "फ़ोन", "फोन"],
        "mr": ["मोबाईल"],
        "ta": ["கைபேசி"],
        "te": ["మొబైల్"],
        "kn": ["ಮೊಬೈಲ್"],
        "bn": ["মোবাইল"],
        "gu": ["મોબાઇલ"],
    },
    "shirt": {
        "hi": ["कमीज़", "कमीज"],
        "mr": ["सदरा"],
        "ta": ["சட்டை"],
        "te": ["చొక్కా"],
        "kn": ["ಅಂಗಿ"],
        "bn": ["জামা"],
        "gu": ["શર્ટ"],
        "rom": ["kameez"],
    },
}

# Malayalam, Punjabi, Odia and Urdu seed forms (native review required).
_EXTRA_FORMS: dict[str, tuple[list[str], list[str], list[str], list[str]]] = {'milk': (['പാൽ'], ['ਦੁੱਧ'], ['କ୍ଷୀର', 'ଦୁଧ'], ['دودھ']),
    'rice': (['അരി'], ['ਚੌਲ'], ['ଚାଉଳ'], ['چاول']),
    'sugar': (['പഞ്ചസാര'], ['ਖੰਡ', 'ਚੀਨੀ'], ['ଚିନି'], ['چینی']),
    'salt': (['ഉപ്പ്'], ['ਲੂਣ'], ['ଲୁଣ'], ['نمک']),
    'oil': (['എണ്ണ'], ['ਤੇਲ'], ['ତେଲ'], ['تیل']),
    'atta flour': (['ഗോതമ്പ് പൊടി'], ['ਆਟਾ'], ['ଅଟା'], ['آٹا']),
    'tea': (['ചായ'], ['ਚਾਹ'], ['ଚା'], ['چائے']),
    'soap': (['സോപ്പ്'], ['ਸਾਬਣ'], ['ସାବୁନ'], ['صابن']),
    'butter': (['വെണ്ണ'], ['ਮੱਖਣ'], ['ଲହୁଣି'], ['مکھن']),
    'dal lentils': (['പരിപ്പ്'], ['ਦਾਲ'], ['ଡାଲି'], ['دال']),
    'eggs': (['മുട്ട'], ['ਆਂਡੇ'], ['ଅଣ୍ଡା'], ['انڈے']),
    'ghee': (['നെയ്യ്'], ['ਘਿਉ'], ['ଘିଅ'], ['گھی']),
    'curd yogurt': (['തൈര്'], ['ਦਹੀਂ'], ['ଦହି'], ['دہی']),
    'water': (['വെള്ളം'], ['ਪਾਣੀ'], ['ପାଣି'], ['پانی']),
    'onion': (['ഉള്ളി'], ['ਪਿਆਜ਼'], ['ପିଆଜ'], ['پیاز']),
    'potato': (['ഉരുളക്കിഴങ്ങ്'], ['ਆਲੂ'], ['ଆଳୁ'], ['آلو']),
    'mobile phone': (['മൊബൈൽ'], ['ਮੋਬਾਈਲ'], ['ମୋବାଇଲ'], ['موبائل']),
    'shirt': (['ഷർട്ട്'], ['ਕਮੀਜ਼'], ['ସାର୍ଟ'], ['قمیض'])}
for _english, (_ml, _pa, _or, _ur) in _EXTRA_FORMS.items():
    _TERMS.setdefault(_english, {}).update({"ml": _ml, "pa": _pa, "or": _or, "ur": _ur})

TERM_INDEX: dict[str, str] = {}
for _english, _forms in _TERMS.items():
    for _lang_forms in _forms.values():
        for _form in _lang_forms:
            TERM_INDEX[_form.casefold()] = _english

# Unicode block ranges -> language guess (Devanagari is shared by hi/mr).
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0600, 0x06FF, "ur"),
    (0x0900, 0x097F, "hi"),
    (0x0980, 0x09FF, "bn"),
    (0x0A00, 0x0A7F, "pa"),
    (0x0B00, 0x0B7F, "or"),
    (0x0D00, 0x0D7F, "ml"),
    (0x0A80, 0x0AFF, "gu"),
    (0x0B80, 0x0BFF, "ta"),
    (0x0C00, 0x0C7F, "te"),
    (0x0C80, 0x0CFF, "kn"),
]


def detect_script_language(text: str) -> str:
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for lo, hi, lang in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return "en"
    return max(counts, key=counts.get)
