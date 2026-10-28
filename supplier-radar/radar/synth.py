"""Generador de noticias sinteticas por plantillas (sin LLM) para ampliar el dataset de entrenamiento.

Cada noticia lleva su etiqueta POR CONSTRUCCION, siguiendo los criterios inferidos de las noticias reales:
  Supply_Impact : none | delay | stoppage     (parada de suministro = planta cerrada, licencia suspendida, recall...)
  Duration      : short | long | unknown      (corta = como mucho unos dias)
  Urgent        = Is_Risk y Supply_Impact == stoppage y Duration != short

Incluye las trampas: nombres parecidos, lugares sin impacto, eventos en lugares SIN proveedores, noticias positivas,
y variaciones de formato (solo titular, prefijo de agencia, frases de relleno, mayusculas).

AVISO: son datos propios. Sirven para ENTRENAR. Nunca se usan para MEDIR: la medida es el examen independiente.

  python3 -m radar.synth --n 3000 --seed 7      # escribe data/synthetic.csv
"""
import argparse
import random

import pandas as pd

from .config import DATA
from .data import load_suppliers
from .knowledge import city_aliases
from .matcher import SUFFIXES

SYN_PATH = DATA / "synthetic.csv"

FILLER = [
    "A spokesperson declined to comment on the matter.",
    "Local media first reported the story on Tuesday.",
    "The news came a day after the company's quarterly update.",
    "Industry observers said they were following developments closely.",
    "Further details are expected in the coming days.",
    "The announcement was made on Monday morning.",
]
AGENCY = ["(Reuters) - ", "(AP) - ", "LONDON - ", "BRUSSELS - ", "SINGAPORE - ", "NEW DELHI - ", "FRANKFURT - "]
OTHER_PLACES = ["Lima", "Jakarta", "Manila", "Nairobi", "Houston", "Seoul", "Chennai", "Dhaka", "Naples", "Lyon",
                "Seville", "Hamburg", "Prague", "Mumbai", "Delhi", "Guangzhou", "Chongqing", "Kyoto", "Tampa",
                "Lagos", "Santiago", "Istanbul", "Warsaw", "Vienna", "Perth", "Calgary"]


def short_name(name: str) -> str:
    toks = str(name).split()
    while len(toks) > 1 and toks[-1].lower().strip(".,") in SUFFIXES:
        toks.pop()
    return " ".join(toks)


class Gen:
    def __init__(self, seed: int):
        self.r = random.Random(seed)
        self.s = load_suppliers()
        self.by_city = {}
        for _, x in self.s.iterrows():
            self.by_city.setdefault(x.City, []).append(x.Supplier_ID)
        self.by_country = {}
        for _, x in self.s.iterrows():
            self.by_country.setdefault(x.Country, set()).add(x.City)
        self.by_region = {}  # region (alias) -> proveedores de las ciudades de esa region
        for city, aliases in city_aliases().items():
            for a in aliases:
                if a in ("rhine",) or len(a) < 4:  # el Rin es un caso de ruta, se trata aparte
                    continue
                self.by_region.setdefault(a, set()).update(self.by_city.get(city, []))
        self.by_region = {k: sorted(v) for k, v in self.by_region.items() if v}
        self.row = {x.Supplier_ID: x for _, x in self.s.iterrows()}
        self.n = 0

    # ------------------------------------------------------------------ utilidades
    def pick(self, xs):
        return self.r.choice(xs)

    def sup(self, maker=False):
        ids = [i for i, x in self.row.items() if not maker or x.Category not in ("Logistics", "Services")]
        return self.row[self.pick(ids)]

    def name(self, x):
        return self.pick([x.Supplier_Name, x.Supplier_Name, short_name(x.Supplier_Name)])

    def dur(self, kind):
        k = self.r.randint(2, 8)
        if kind == "long":
            return self.pick([f"for at least {k} weeks", f"for up to {k} weeks", f"for about {k} weeks",
                              f"for the next {k} weeks", "for about two months", f"for {k} weeks", "for over a month",
                              "well into next month"])
        if kind == "short":
            return self.pick(["for 48 hours", "for two days", "for a day", "for 24 hours", "over the weekend",
                              "for the next 48 hours", "for one day", "until Friday", "on Tuesday and Wednesday", "for three days"])
        return self.pick(["with no restart date announced", "until further notice", "and no timeline has been given"])

    def style(self, h, s):
        r = self.r.random()
        if r < 0.04:
            s = ""  # solo titular
        elif r < 0.08:
            h, s = s.split(". ")[0].rstrip(".") if s else h, ""  # solo la primera frase del resumen
        elif r < 0.16 and s:
            s = self.pick(AGENCY) + s
        if s and self.r.random() < 0.14:
            s = s + " " + self.pick(FILLER)
        if self.r.random() < 0.02:
            h = h.upper()
        return h, s

    def out(self, headline, summary, risk, ids, event, impact="none", duration="unknown"):
        self.n += 1
        urgent = bool(risk) and impact == "stoppage" and duration != "short"
        headline, summary = self.style(headline, summary)
        return {
            "News_ID": f"SYN{self.n:05d}", "Headline": headline, "Summary": summary,
            "Is_Risk": "Y" if risk else "N", "Urgent": "Y" if urgent else "N",
            "Affected_Supplier_IDs": "; ".join(sorted(ids)), "Event_Type": event,
            "Supply_Impact": impact, "Duration": duration, "Explanation": "synthetic",
        }

    # ------------------------------------------------------------------ escenarios
    def supplier_incident(self):
        kind = self.pick(["fire_long", "fire_unknown", "fire_short", "fire_wh", "recall", "licence", "warning",
                          "going", "downgrade", "ceo", "acq", "strike", "maintenance", "cyber_long", "cyber_delay"])
        x = self.sup(maker=kind in ("fire_long", "fire_unknown", "fire_short", "fire_wh", "recall", "licence", "maintenance"))
        N, C, M, i = self.name(x), x.City, x.Material_Supplied, [x.Supplier_ID]
        if kind == "fire_long":
            d = self.dur("long")
            return self.out(
                self.pick([f"Fire at {N} plant in {C} halts production", f"Blaze forces shutdown of {N} site in {C}",
                           f"Fire at {C} chemical park forces evacuation of {N}"]),
                self.pick([f"A fire broke out at the {C} site of {N} and production has stopped. Inspectors expect the plant to stay closed {d}.",
                           f"Production at {N} in {C} was halted after a fire on Tuesday. Safety inspections are expected to last {d}."]),
                True, i, "Fire / plant incident", "stoppage", "long")
        if kind == "fire_unknown":
            d = self.dur("unknown")
            return self.out(
                f"Explosion shuts down {N} facility in {C}",
                f"An explosion at the {C} facility of {N} has stopped production {d}.",
                True, i, "Fire / plant incident", "stoppage", "unknown")
        if kind == "fire_short":
            d = self.dur("short")
            return self.out(
                f"Small fire at {N} plant in {C} stops lines briefly",
                f"A fire at {N}'s {C} plant was quickly put out. Production lines were stopped {d} for checks and are expected to restart afterwards.",
                True, i, "Fire / plant incident", "stoppage", "short")
        if kind == "fire_wh":
            return self.out(
                f"Explosion at {N} warehouse in {C}, no injuries",
                f"An explosion damaged a storage building at {N}. Production buildings were not affected, but finished goods stock was lost.",
                True, i, "Fire / plant incident", "delay", "unknown")
        if kind == "recall":
            return self.out(
                self.pick([f"{N} announces recall of {M.lower()} lots", f"{N} recalls batches after quality complaints"]),
                f"{N} is recalling several lots after customers reported quality problems. The company is investigating a possible issue at its {C} plant.",
                True, i, "Quality recall", "stoppage", "unknown")
        if kind == "licence":
            d = self.dur("long")
            return self.out(
                self.pick([f"Regulator suspends production licence of {N}", f"Authorities halt {N} operations pending review"]),
                f"Authorities in {x.Country} have suspended production at {N} after a compliance review. The review could take {d.replace('for ', '')}.",
                True, i, "Regulatory action", "stoppage", "long")
        if kind == "warning":
            return self.out(
                f"Regulator issues warning letter to {N}",
                f"A regulator sent a warning letter to {N} citing documentation gaps at its {C} site. The company says operations continue and it will respond within weeks.",
                True, i, "Regulatory action", "delay", "unknown")
        if kind == "going":
            return self.out(
                f"{N} flags going-concern doubt after missed payment",
                f"{N} said it missed a scheduled payment to lenders and its auditor has raised doubts about the company's ability to continue operating. Talks with creditors continue.",
                True, i, "Financial distress", "stoppage", "unknown")
        if kind == "downgrade":
            return self.out(
                f"Rating agency downgrades {N}",
                f"A credit rating agency cut its rating on {N}, citing high debt and weaker margins.",
                True, i, "Financial distress", "none", "unknown")
        if kind == "ceo":
            return self.out(
                f"{N} chief executive steps down",
                f"{N} announced that its chief executive has stepped down with immediate effect. The chief operating officer will act as interim chief executive.",
                True, i, "Leadership change", "none", "unknown")
        if kind == "acq":
            comp = self.pick(["Veltrix Pharma", "Norvane Holdings", "Altis Group", "Medora Capital"])
            return self.out(
                f"{comp} agrees to acquire {N}",
                f"{comp}, a competitor of several large drug makers, has agreed to buy {N}. The deal is expected to close next year.",
                True, i, "Acquisition by competitor", "none", "unknown")
        if kind == "strike":
            return self.out(
                f"Workers at {N} in {C} begin {self.r.randint(2, 4)}-day strike",
                f"Staff at the {C} site of {N} have walked out over pay. The company expects some delayed shipments.",
                True, i, "Labour strike", "delay", "short")
        if kind == "maintenance":
            d = self.dur("short")
            return self.out(
                f"{N} schedules maintenance shutdown at {C} plant",
                f"{N} will stop its {C} plant {d} for planned maintenance. Customers have been informed.",
                True, i, "Other risk", "stoppage", "short")
        if kind == "cyber_long":
            d = self.dur("long")
            return self.out(
                f"Ransomware attack forces {N} to shut down systems",
                f"A cyberattack hit {N}, taking production systems offline at its {C} site {d}.",
                True, i, "Cyber attack", "stoppage", "long")
        return self.out(
            f"Cyber incident disrupts IT systems at {N}",
            f"{N} said a cyber incident has disrupted order processing. Some shipments from {C} may be delayed.",
            True, i, "Cyber attack", "delay", "unknown")

    def positive(self):
        x = self.sup()
        N, C = self.name(x), x.City
        h, s = self.pick([
            (f"{N} doubles capacity at {C} site", f"{N} has opened a new production line at its {C} site, doubling output."),
            (f"{N} signs long-term supply deal with European pharma group", f"{N} signed a multi-year contract to supply a large European drug maker."),
            (f"{N} secures new financing to expand {C} capacity", f"A group of banks has agreed new financing for {N} to expand its facilities."),
            (f"{N} receives approval to expand {C} site", f"Local authorities approved the expansion plans of {N} in {C}."),
            (f"{N} wins quality award", f"{N} was recognised for its quality record by an industry body."),
            (f"{N} completes regulatory inspection with no observations", f"Inspectors found no observations during the audit of {N}'s {C} facility."),
            (f"{N} appoints new head of operations", f"{N} named an experienced industry executive to lead operations at its {C} site, in a planned succession."),
            (f"{N} reports record quarterly output", f"{N} said production at its {C} plant reached a record level last quarter."),
        ])
        return self.out(h, s, False, [x.Supplier_ID], "Positive news")

    HAZ = [("flooding", "Severe flooding"), ("earthquake", "A strong earthquake"), ("wildfire", "Wildfires"),
           ("typhoon", "A typhoon"), ("storm", "A violent storm"), ("heatwave", "An extreme heatwave"),
           ("hurricane", "A hurricane")]

    def place(self):
        """Devuelve (texto del lugar, ids). Ciudad, region o dos ciudades del mismo pais."""
        r = self.r.random()
        if r < 0.40 and self.by_region:
            reg = self.pick(list(self.by_region))
            return reg.title(), self.by_region[reg]
        if r < 0.55:
            country = self.pick([c for c, v in self.by_country.items() if len(v) >= 2])
            a, b = self.r.sample(sorted(self.by_country[country]), 2)
            return f"{a} and {b}", self.by_city[a] + self.by_city[b]
        c = self.pick(list(self.by_city))
        return c, self.by_city[c]


    HAZ_PHRASE = ["a typhoon", "severe flooding", "an earthquake", "wildfires", "a violent storm", "an extreme heatwave",
                  "a hurricane", "heavy snowfall", "torrential rain", "a cyclone"]

    def closure_text(self, place, kind):
        """Titular y resumen de un cierre industrial por desastre, con muchas redacciones distintas."""
        hz = self.pick(self.HAZ_PHRASE)
        if kind == "short":
            d = self.dur("short")
            return self.pick([
                (f"Factories in {place} shut as {hz} hits", f"Manufacturers in {place} suspended operations {d} while {hz} passes. Normal activity should return afterwards."),
                (f"Authorities order {place} plants to halt work", f"Local officials told industrial sites in {place} to stop operations {d} because of {hz}."),
                (f"{hz.capitalize()} closes businesses in {place}", f"Shops, schools and factories in {place} were closed {d} after {hz}."),
                (f"Work stops at {place} industrial zone", f"Operators in {place} halted production {d} as a precaution ahead of {hz}; restart is expected right after."),
                (f"{place} factories close temporarily after {hz}", f"Plants in {place} will stay shut {d}. The authorities expect a quick return to normal."),
            ]), "short"
        if kind == "long":
            d = self.dur("long")
            return self.pick([
                (f"{hz.capitalize()} leaves {place} factories shut", f"Factories in {place} will remain closed {d} after {hz} damaged power lines and roads."),
                (f"Industrial output in {place} halted after {hz}", f"Production across {place} industrial parks is halted {d} while repairs continue."),
                (f"Evacuation order empties {place} industrial estates", f"Authorities evacuated industrial estates in {place} after {hz}; they will stay closed {d}."),
            ]), "long"
        return self.pick([
            (f"Plants in {place} idle after {hz}", f"Industrial plants in {place} stopped work after {hz} and officials have not said when they will reopen."),
            (f"{place} manufacturers suspend output", f"Manufacturers in {place} suspended output following {hz}. No restart date has been announced."),
        ]), "unknown"

    def location_disaster(self):
        place, ids = self.place()
        ev, noun = self.pick(self.HAZ)
        if self.r.random() < 0.55:  # redacciones variadas
            (h, s), kind = self.closure_text(place, self.pick(["long", "long", "unknown", "short", "short"]))
            return self.out(h, s, True, ids, "Natural disaster", "stoppage", kind)
        v = self.pick(["long", "long", "unknown", "short", "checks"])
        if v == "long":
            d = self.dur("long")
            return self.out(
                f"{noun} hits {place}, industrial plants closed",
                f"{noun} struck {place}. Many chemical and pharmaceutical plants have stopped production and roads are closed. Officials say recovery could take {d.replace('for ', '')}.",
                True, ids, "Natural disaster", "stoppage", "long")
        if v == "unknown":
            return self.out(
                f"{noun} disrupts industrial estates in {place}",
                f"{noun} has paused production at many plants across {place} and roads are closed. Authorities have not said when work can resume.",
                True, ids, "Natural disaster", "stoppage", "unknown")
        if v == "short":
            d = self.dur("short")
            return self.out(
                f"{noun} near {place} prompts temporary factory closures",
                f"Several factories around {place} closed {d} as a precaution. Operations are expected to resume quickly.",
                True, ids, "Natural disaster", "stoppage", "short")
        return self.out(
            f"{noun} reported in {place}",
            f"Factories in {place} halted production for safety checks after the event. Other regions reported only light effects.",
            True, ids, "Natural disaster", "stoppage", "short")

    def nonsupplier_event(self):
        """Evento grave pero en un lugar SIN proveedores: no es riesgo para Helixa."""
        p = self.pick(OTHER_PLACES)
        ev, noun = self.pick(self.HAZ)
        if self.r.random() < 0.55:  # mismas redacciones que arriba, pero en un lugar sin proveedores
            (h, s), _ = self.closure_text(p, self.pick(["long", "long", "unknown", "short", "short"]))
            return self.out(h, s, False, [], "Not relevant")
        h, s = self.pick([
            (f"{noun} hits {p}, industrial plants closed", f"{noun} struck {p}. Many factories have stopped production and roads are closed for weeks."),
            (f"Fire at chemical plant in {p} forces evacuation", f"A fire at a chemical plant in {p} led to an evacuation. The plant will stay closed for several weeks."),
            (f"Dock workers strike at {p} port", f"A strike by port workers in {p} has delayed container traffic for days."),
            (f"Power cuts hit factories in {p}", f"Factories in {p} cut output after repeated blackouts."),
        ])
        return self.out(h, s, False, [], "Not relevant")

    def utility_logistics(self):
        kind = self.pick(["power", "blockade", "portstrike", "truckers"])
        if kind == "power":
            reg = self.pick(list(self.by_region))
            return self.out(
                f"Power rationing imposed on {reg.title()} factories",
                f"Factories in {reg.title()} must cut power use by 20 percent for {self.r.randint(1, 3)} weeks as demand for electricity soars.",
                True, self.by_region[reg], "Utility outage", "delay", "long")
        ports = [c for c in ("Rotterdam", "Antwerp", "Singapore", "Barcelona", "Valencia", "Kaohsiung", "Ho Chi Minh City", "Sao Paulo") if c in self.by_city]
        city = self.pick(ports if kind == "portstrike" else list(self.by_city))
        ids = self.by_city[city]
        if kind == "blockade":
            return self.out(
                f"Protests block highway near {city} for second day",
                f"Demonstrators have blocked a main road near {city}, delaying deliveries in and out of the area.",
                True, ids, "Logistics disruption", "delay", "short")
        if kind == "portstrike":
            return self.out(
                f"Strike at {city} terminals enters third day",
                f"A strike by terminal workers around {city} has entered its third day, leaving containers waiting.",
                True, ids, "Labour strike", "delay", "short")
        return self.out(
            f"Truckers call strike over fuel prices near {city}",
            f"A trade association called a three-day strike, threatening road freight from industrial areas including {city}.",
            True, ids, "Labour strike", "delay", "short")

    def export_restriction(self):
        by_c = {}
        for _, x in self.s.iterrows():
            by_c.setdefault(x.Country, []).append(x)
        country = self.pick([c for c, v in by_c.items() if len(v) >= 2 and "(" not in c])
        mats = sorted({x.Material_Supplied for x in by_c[country]})
        chosen = self.r.sample(mats, k=min(len(mats), self.r.randint(1, 2)))
        first = [m.split()[0].lower() for m in chosen]
        ids = [x.Supplier_ID for x in by_c[country] if x.Material_Supplied.split()[0].lower() in first]
        names = " and ".join(m.lower() for m in chosen)
        if self.r.random() < 0.25:
            return self.out(
                f"New tariffs announced on {country} exports of {names}",
                f"A trading partner announced higher tariffs on {names} coming from {country}, raising costs for importers.",
                True, ids, "Geopolitical / sanctions", "delay", "long")
        return self.out(
            f"{country} announces temporary export restrictions on {names}",
            f"The government of {country} has introduced export licensing for {names} to protect domestic supply.",
            True, ids, "Export restriction", "stoppage", "unknown")

    def route(self):
        if self.r.random() < 0.5:
            return self.out(
                self.pick(["Shipping lines reroute around Africa as Red Sea tensions escalate",
                           "Container lines divert Asia-Europe services away from the Red Sea"]),
                "Major container lines are diverting Asia to Europe services around the Cape of Good Hope, adding about two weeks to journey times.",
                True, ["S032"], "Logistics disruption", "delay", "long")
        return self.out(
            self.pick(["Low water on the Rhine restricts barge traffic for chemical shippers",
                       "Dry spell cuts Rhine barge loads, chemical distributors warn of delays"]),
            "Water levels on the Rhine have fallen after a dry summer, forcing barges to carry reduced loads. Chemical distributors along the river warn of slower deliveries.",
            True, ["S009", "S039"], "Logistics disruption", "delay", "unknown")

    GENERIC = [
        ("Central bank holds interest rates steady", "The bank left rates unchanged and signalled no change for the rest of the year."),
        ("Global smartphone shipments rise 4 percent", "Makers shipped more devices than a year earlier, led by emerging markets."),
        ("Swiss franc strengthens against the euro", "The currency rose to its highest level in months."),
        ("European Parliament debates reform of pharmaceutical legislation", "Lawmakers began a debate on a long-awaited update of drug rules."),
        ("German business confidence improves for second month", "A closely watched survey showed a further rise in sentiment."),
        ("Oil prices edge lower on demand worries", "Crude fell slightly as traders weighed weaker consumption forecasts."),
        ("Tech giant unveils new cloud region", "The company opened a new data centre region to serve European customers."),
        ("Airline orders 40 new jets", "The carrier signed a deal to renew its short-haul fleet over the next decade."),
        ("Inflation slows for third straight month", "Consumer prices rose less than analysts had expected."),
        ("Pharma group reports strong sales of obesity drug", "A large drug maker raised its full-year forecast after strong demand."),
        ("Electric car maker opens new plant in Hungary", "The factory will employ 2,000 workers when it reaches full capacity."),
        ("Film festival opens with record attendance", "Organisers said ticket sales were up on last year."),
        ("Stock markets close higher on tech rally", "Major indices gained as investors bought technology shares."),
        ("Government unveils plan to cut hospital waiting lists", "Ministers said the programme would add staff over three years."),
        ("Retailer closes 30 stores as online sales grow", "The chain said it would focus on e-commerce."),
        ("Biotech startup raises 80 million euros", "The company will use the funds to start a clinical trial."),
        ("Telecom operator completes 5G rollout", "The network now covers 95 percent of the population."),
        ("Wheat prices fall after strong harvest", "Farmers reported higher yields in major growing regions."),
    ]
    PLACE_NEWS = [
        "Heavy rain expected in {c} this weekend|Forecasters expect showers across {c} over the weekend, with no warnings issued.",
        "{c} hosts European logistics summit|Industry leaders gather in {c} this week to discuss trends.",
        "{c} airport passenger numbers reach record|The airport serving {c} handled more travellers than ever before.",
        "{c} hosts international AI conference|Researchers and companies meet in {c} for a three-day conference.",
        "New cultural festival announced in {c}|{c} will host a music and film festival next summer.",
        "Marathon returns to {c} this Sunday|Thousands of runners will take part in the annual race through {c}.",
        "Hotel occupancy rises in {c}|Tourism officials said visitor numbers in {c} were up on last year.",
        "Council approves new tram line in {c}|Works in {c} are due to begin next year.",
    ]
    LOOKALIKE = [
        "{w} Capital raises USD 2 billion for new technology fund|Private equity firm {w} Capital has closed its latest fund, which will invest in software companies.",
        "{w} tops the box office in its opening weekend|The new film '{w}' earned more than expected in cinemas.",
        "{w} beat Rangers 2-1 in derby|{w} won the match with a late goal in front of a full stadium.",
        "{w} Energy commissions 500 MW solar farm|Utility {w} Energy has connected a large solar plant to the grid.",
        "{w} Air reports quarterly results ahead of expectations|Airline {w} Air said profit rose on strong summer demand.",
        "{w} Foods recalls yoghurt over labelling error|The food company {w} Foods is withdrawing a product line after a printing mistake.",
        "Band {w} announces world tour|The group {w} will play 40 dates across Europe next year.",
        "{w} University opens new research centre|{w} University said the centre will study climate science.",
    ]

    def noise(self):
        kind = self.pick(["generic", "place", "lookalike"])
        if kind == "generic":
            h, s = self.pick(self.GENERIC)
        elif kind == "place":
            h, s = self.pick(self.PLACE_NEWS).format(c=self.pick(list(self.by_city))).split("|")
        else:
            words = sorted({short_name(x.Supplier_Name).split()[0] for _, x in self.s.iterrows() if len(short_name(x.Supplier_Name).split()[0]) >= 4})
            h, s = self.pick(self.LOOKALIKE).format(w=self.pick(words)).split("|")
        return self.out(h, s, False, [], "Not relevant")

    def make(self, n: int) -> pd.DataFrame:
        plan = [
            (self.supplier_incident, 0.24), (self.location_disaster, 0.18), (self.utility_logistics, 0.06),
            (self.export_restriction, 0.05), (self.route, 0.02), (self.positive, 0.09), (self.noise, 0.24),
            (self.nonsupplier_event, 0.07),
        ]
        fns, ws = zip(*plan)
        rows = [self.r.choices(fns, ws)[0]() for _ in range(n)]
        df = pd.DataFrame(rows).drop_duplicates(subset=["Headline", "Summary"]).reset_index(drop=True)
        df["text"] = (df["Headline"].str.rstrip(". ") + ". " + df["Summary"]).str.strip()
        return df


def generate(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    return Gen(seed).make(n)


def load_synth() -> pd.DataFrame:
    if not SYN_PATH.exists():
        generate().to_csv(SYN_PATH, index=False)
    return pd.read_csv(SYN_PATH, keep_default_na=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    df = generate(a.n, a.seed)
    df.to_csv(SYN_PATH, index=False)
    print(f"{len(df)} noticias sinteticas -> {SYN_PATH}")
    print(df[["Is_Risk", "Urgent"]].value_counts().to_string())
    print(df[["Supply_Impact", "Duration"]].value_counts().to_string())
