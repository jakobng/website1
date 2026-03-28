"""Canonical country list with ISO 3166-1 alpha-2 codes and common aliases.

Every country reference in the database and user input resolves to a standard
code via resolve(). This prevents "UK" vs "United Kingdom" mismatches.
"""
from __future__ import annotations

# (code, display_name, aliases)
# Aliases are lowercase. The resolver checks display_name and all aliases.
_COUNTRIES: list[tuple[str, str, list[str]]] = [
    # --- Europe ---
    ("AL", "Albania", ["alb", "shqipëri"]),
    ("AD", "Andorra", ["and"]),
    ("AM", "Armenia", ["arm", "hayastan"]),
    ("AT", "Austria", ["aut"]),
    ("AZ", "Azerbaijan", ["aze"]),
    ("BY", "Belarus", ["blr"]),
    ("BE", "Belgium", ["bel", "belgique", "belgie"]),
    ("BA", "Bosnia and Herzegovina", ["bih", "bosnia"]),
    ("BG", "Bulgaria", ["bgr"]),
    ("HR", "Croatia", ["hrv"]),
    ("CY", "Cyprus", ["cyp"]),
    ("CZ", "Czech Republic", ["cze", "czechia"]),
    ("DK", "Denmark", ["dnk", "danmark"]),
    ("EE", "Estonia", ["est"]),
    ("FI", "Finland", ["fin", "suomi"]),
    ("FR", "France", ["fra"]),
    ("GE", "Georgia", ["geo", "sakartvelo"]),
    ("DE", "Germany", ["deu", "ger", "deutschland"]),
    ("GR", "Greece", ["grc", "hellas"]),
    ("HU", "Hungary", ["hun"]),
    ("IS", "Iceland", ["isl"]),
    ("IE", "Ireland", ["irl"]),
    ("IT", "Italy", ["ita", "italia"]),
    ("XK", "Kosovo", ["xkx", "kosova", "kosovë"]),
    ("LV", "Latvia", ["lva"]),
    ("LI", "Liechtenstein", ["lie"]),
    ("LT", "Lithuania", ["ltu"]),
    ("LU", "Luxembourg", ["lux"]),
    ("MT", "Malta", ["mlt"]),
    ("MD", "Moldova", ["mda"]),
    ("MC", "Monaco", ["mco"]),
    ("ME", "Montenegro", ["mne", "crna gora"]),
    ("NL", "Netherlands", ["nld", "holland", "the netherlands"]),
    ("MK", "North Macedonia", ["mkd", "macedonia"]),
    ("NO", "Norway", ["nor", "norge"]),
    ("PL", "Poland", ["pol", "polska"]),
    ("PT", "Portugal", ["prt"]),
    ("RO", "Romania", ["rou"]),
    ("RS", "Serbia", ["srb"]),
    ("SM", "San Marino", ["smr"]),
    ("SK", "Slovakia", ["svk"]),
    ("SI", "Slovenia", ["svn"]),
    ("ES", "Spain", ["esp", "espana", "españa"]),
    ("SE", "Sweden", ["swe", "sverige"]),
    ("CH", "Switzerland", ["che", "suisse", "schweiz"]),
    ("TR", "Turkey", ["tur", "türkiye", "turkiye"]),
    ("UA", "Ukraine", ["ukr"]),
    ("GB", "United Kingdom", ["gbr", "uk", "great britain", "britain", "england", "scotland", "wales"]),
    ("VA", "Vatican City", ["vat", "holy see"]),
    # --- Americas ---
    ("AG", "Antigua and Barbuda", ["atg"]),
    ("AR", "Argentina", ["arg"]),
    ("BS", "Bahamas", ["bhs"]),
    ("BB", "Barbados", ["brb"]),
    ("BZ", "Belize", ["blz"]),
    ("BO", "Bolivia", ["bol"]),
    ("BR", "Brazil", ["bra", "brasil"]),
    ("CA", "Canada", ["can"]),
    ("CL", "Chile", ["chl"]),
    ("CO", "Colombia", ["col"]),
    ("CR", "Costa Rica", ["cri"]),
    ("CU", "Cuba", ["cub"]),
    ("DM", "Dominica", ["dma"]),
    ("DO", "Dominican Republic", ["dom"]),
    ("EC", "Ecuador", ["ecu"]),
    ("SV", "El Salvador", ["slv"]),
    ("GD", "Grenada", ["grd"]),
    ("GT", "Guatemala", ["gtm"]),
    ("GY", "Guyana", ["guy"]),
    ("HT", "Haiti", ["hti"]),
    ("HN", "Honduras", ["hnd"]),
    ("JM", "Jamaica", ["jam"]),
    ("MX", "Mexico", ["mex"]),
    ("NI", "Nicaragua", ["nic"]),
    ("PA", "Panama", ["pan"]),
    ("PY", "Paraguay", ["pry"]),
    ("PE", "Peru", ["per"]),
    ("KN", "Saint Kitts and Nevis", ["kna"]),
    ("LC", "Saint Lucia", ["lca"]),
    ("VC", "Saint Vincent and the Grenadines", ["vct"]),
    ("SR", "Suriname", ["sur"]),
    ("TT", "Trinidad and Tobago", ["tto", "trinidad"]),
    ("US", "United States", ["usa", "us", "united states of america", "america"]),
    ("UY", "Uruguay", ["ury"]),
    ("VE", "Venezuela", ["ven"]),
    # --- Asia ---
    ("AF", "Afghanistan", ["afg"]),
    ("BH", "Bahrain", ["bhr"]),
    ("BD", "Bangladesh", ["bgd"]),
    ("BT", "Bhutan", ["btn"]),
    ("BN", "Brunei", ["brn"]),
    ("KH", "Cambodia", ["khm"]),
    ("CN", "China", ["chn", "prc"]),
    ("IN", "India", ["ind"]),
    ("ID", "Indonesia", ["idn"]),
    ("IR", "Iran", ["irn"]),
    ("IQ", "Iraq", ["irq"]),
    ("IL", "Israel", ["isr"]),
    ("JP", "Japan", ["jpn"]),
    ("JO", "Jordan", ["jor"]),
    ("KZ", "Kazakhstan", ["kaz"]),
    ("KW", "Kuwait", ["kwt"]),
    ("KG", "Kyrgyzstan", ["kgz"]),
    ("LA", "Laos", ["lao"]),
    ("MY", "Malaysia", ["mys"]),
    ("MV", "Maldives", ["mdv"]),
    ("MN", "Mongolia", ["mng"]),
    ("MM", "Myanmar", ["mmr", "burma"]),
    ("NP", "Nepal", ["npl"]),
    ("KP", "North Korea", ["prk"]),
    ("OM", "Oman", ["omn"]),
    ("PK", "Pakistan", ["pak"]),
    ("PS", "Palestine", ["pse", "palestinian territories"]),
    ("PH", "Philippines", ["phl"]),
    ("QA", "Qatar", ["qat"]),
    ("KR", "South Korea", ["kor", "korea", "south korea", "republic of korea"]),
    ("SG", "Singapore", ["sgp"]),
    ("LK", "Sri Lanka", ["lka", "ceylon"]),
    ("SY", "Syria", ["syr"]),
    ("TW", "Taiwan", ["twn"]),
    ("TJ", "Tajikistan", ["tjk"]),
    ("TH", "Thailand", ["tha"]),
    ("TL", "Timor-Leste", ["tls", "east timor"]),
    ("TM", "Turkmenistan", ["tkm"]),
    ("UZ", "Uzbekistan", ["uzb"]),
    ("VN", "Vietnam", ["vnm", "viet nam"]),
    ("YE", "Yemen", ["yem"]),
    # --- Oceania ---
    ("AU", "Australia", ["aus", "oz"]),
    ("FJ", "Fiji", ["fji"]),
    ("KI", "Kiribati", ["kir"]),
    ("MH", "Marshall Islands", ["mhl"]),
    ("FM", "Micronesia", ["fsm"]),
    ("NR", "Nauru", ["nru"]),
    ("NZ", "New Zealand", ["nzl"]),
    ("PW", "Palau", ["plw"]),
    ("PG", "Papua New Guinea", ["png"]),
    ("WS", "Samoa", ["wsm"]),
    ("SB", "Solomon Islands", ["slb"]),
    ("TO", "Tonga", ["ton"]),
    ("TV", "Tuvalu", ["tuv"]),
    ("VU", "Vanuatu", ["vut"]),
    # --- Africa ---
    ("DZ", "Algeria", ["dza"]),
    ("AO", "Angola", ["ago"]),
    ("BJ", "Benin", ["ben"]),
    ("BW", "Botswana", ["bwa"]),
    ("BF", "Burkina Faso", ["bfa"]),
    ("BI", "Burundi", ["bdi"]),
    ("CV", "Cabo Verde", ["cpv", "cape verde"]),
    ("CM", "Cameroon", ["cmr"]),
    ("CF", "Central African Republic", ["caf"]),
    ("TD", "Chad", ["tcd"]),
    ("KM", "Comoros", ["com"]),
    ("CD", "DR Congo", ["cod", "democratic republic of the congo", "congo-kinshasa", "drc", "congo kinshasa"]),
    ("CG", "Republic of the Congo", ["cog", "congo-brazzaville", "congo brazzaville", "congo"]),
    ("CI", "Ivory Coast", ["civ", "côte d'ivoire", "cote d'ivoire"]),
    ("DJ", "Djibouti", ["dji"]),
    ("EG", "Egypt", ["egy"]),
    ("GQ", "Equatorial Guinea", ["gnq"]),
    ("ER", "Eritrea", ["eri"]),
    ("SZ", "Eswatini", ["swz", "swaziland"]),
    ("ET", "Ethiopia", ["eth"]),
    ("GA", "Gabon", ["gab"]),
    ("GM", "Gambia", ["gmb"]),
    ("GH", "Ghana", ["gha"]),
    ("GN", "Guinea", ["gin"]),
    ("GW", "Guinea-Bissau", ["gnb"]),
    ("KE", "Kenya", ["ken"]),
    ("LS", "Lesotho", ["lso"]),
    ("LR", "Liberia", ["lbr"]),
    ("LY", "Libya", ["lby"]),
    ("MG", "Madagascar", ["mdg"]),
    ("MW", "Malawi", ["mwi"]),
    ("ML", "Mali", ["mli"]),
    ("MR", "Mauritania", ["mrt"]),
    ("MU", "Mauritius", ["mus"]),
    ("MA", "Morocco", ["mar"]),
    ("MZ", "Mozambique", ["moz"]),
    ("NA", "Namibia", ["nam"]),
    ("NE", "Niger", ["ner"]),
    ("NG", "Nigeria", ["nga"]),
    ("RW", "Rwanda", ["rwa"]),
    ("ST", "Sao Tome and Principe", ["stp"]),
    ("SN", "Senegal", ["sen"]),
    ("SC", "Seychelles", ["syc"]),
    ("SL", "Sierra Leone", ["sle"]),
    ("SO", "Somalia", ["som"]),
    ("ZA", "South Africa", ["zaf"]),
    ("SS", "South Sudan", ["ssd"]),
    ("SD", "Sudan", ["sdn"]),
    ("TZ", "Tanzania", ["tza"]),
    ("TG", "Togo", ["tgo"]),
    ("TN", "Tunisia", ["tun"]),
    ("UG", "Uganda", ["uga"]),
    ("ZM", "Zambia", ["zmb"]),
    ("ZW", "Zimbabwe", ["zwe"]),
    # --- Middle East (not already listed) ---
    ("LB", "Lebanon", ["lbn"]),
    ("SA", "Saudi Arabia", ["sau"]),
    ("AE", "United Arab Emirates", ["are", "uae", "dubai", "abu dhabi"]),
]

# Build lookup tables
_BY_CODE: dict[str, str] = {}          # code -> display_name
_RESOLVE: dict[str, str] = {}          # lowercase alias/name -> code

for _code, _name, _aliases in _COUNTRIES:
    _BY_CODE[_code] = _name
    _RESOLVE[_name.lower()] = _code
    _RESOLVE[_code.lower()] = _code
    for _a in _aliases:
        _RESOLVE[_a] = _code


def resolve(name: str) -> str | None:
    """Resolve a free-text country name to its ISO code. Returns None if unknown."""
    return _RESOLVE.get(name.strip().lower())


def display_name(code: str) -> str:
    """Return the display name for a country code, or the code itself if unknown."""
    return _BY_CODE.get(code.upper(), code)


def all_countries() -> list[dict[str, str]]:
    """Return list of {code, name} for all known countries."""
    return [{"code": c, "name": n} for c, n, _ in _COUNTRIES]


def resolve_or_keep(name: str) -> str:
    """Resolve to ISO code, or return the original string if unknown (for graceful degradation)."""
    return resolve(name) or name.strip()
