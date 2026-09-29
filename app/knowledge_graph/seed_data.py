"""Curated seed entities: common Ayurvedic herbs, marker compounds, classical formulations.

Reference data for navigation and botanical lookup — not a substitute for the
Ayurvedic Pharmacopoeia of India monographs in the corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeedHerb:
    botanical_name: str
    names: tuple[str, ...]
    compounds: tuple[str, ...]
    confidence: float = 0.95
    family: str | None = None


@dataclass(frozen=True)
class SeedFormulation:
    name: str
    herbs: tuple[str, ...]  # botanical names
    aliases: tuple[str, ...] = field(default_factory=tuple)
    dosage_form: str | None = None


HERBS: tuple[SeedHerb, ...] = (
    SeedHerb("Withania somnifera", ("Ashwagandha", "Indian ginseng", "Winter cherry"),
             ("withanolides", "withaferin A", "alkaloids"), family="Solanaceae"),
    SeedHerb("Curcuma longa", ("Turmeric", "Haridra", "Haldi"),
             ("curcumin", "demethoxycurcumin", "bisdemethoxycurcumin"), 0.93, "Zingiberaceae"),
    SeedHerb("Ocimum tenuiflorum", ("Tulsi", "Holy basil", "Ocimum sanctum"),
             ("eugenol", "ursolic acid", "rosmarinic acid"), family="Lamiaceae"),
    SeedHerb("Bacopa monnieri", ("Brahmi", "Water hyssop"), ("bacosides",), family="Plantaginaceae"),
    SeedHerb("Phyllanthus emblica", ("Amalaki", "Amla", "Indian gooseberry", "Emblica officinalis"),
             ("ascorbic acid", "gallic acid", "emblicanin A"), family="Phyllanthaceae"),
    SeedHerb("Terminalia chebula", ("Haritaki", "Chebulic myrobalan"),
             ("chebulinic acid", "chebulagic acid", "gallic acid"), family="Combretaceae"),
    SeedHerb("Terminalia bellirica", ("Bibhitaki", "Vibhitaki", "Baheda"),
             ("gallic acid", "ellagic acid"), family="Combretaceae"),
    SeedHerb("Tinospora cordifolia", ("Guduchi", "Giloy", "Amrita"),
             ("berberine", "tinosporaside"), family="Menispermaceae"),
    SeedHerb("Azadirachta indica", ("Neem", "Nimba"), ("azadirachtin", "nimbin"), family="Meliaceae"),
    SeedHerb("Zingiber officinale", ("Ginger", "Shunthi", "Sunthi"),
             ("gingerols", "shogaols"), family="Zingiberaceae"),
    SeedHerb("Piper longum", ("Pippali", "Long pepper"), ("piperine", "piperlongumine"), family="Piperaceae"),
    SeedHerb("Piper nigrum", ("Maricha", "Black pepper"), ("piperine",), family="Piperaceae"),
    SeedHerb("Glycyrrhiza glabra", ("Yashtimadhu", "Licorice", "Liquorice", "Mulethi"),
             ("glycyrrhizin", "glabridin"), family="Fabaceae"),
    SeedHerb("Asparagus racemosus", ("Shatavari",), ("shatavarins",), family="Asparagaceae"),
    SeedHerb("Commiphora wightii", ("Guggulu", "Guggul", "Commiphora mukul"),
             ("guggulsterones",), family="Burseraceae"),
    SeedHerb("Centella asiatica", ("Mandukaparni", "Gotu kola"),
             ("asiaticoside", "madecassoside"), family="Apiaceae"),
    SeedHerb("Boswellia serrata", ("Shallaki", "Indian frankincense"),
             ("boswellic acids",), family="Burseraceae"),
    SeedHerb("Trigonella foenum-graecum", ("Methi", "Fenugreek"),
             ("diosgenin", "trigonelline"), family="Fabaceae"),
    SeedHerb("Panax ginseng", ("Korean ginseng",), ("ginsenosides",), 0.9, "Araliaceae"),
    SeedHerb("Eleutherococcus senticosus", ("Siberian ginseng", "Eleuthero"),
             ("eleutherosides",), 0.9, "Araliaceae"),
)

# Vernacular terms that must never resolve to a single herb.
AMBIGUOUS_NAMES: dict[str, tuple[str, ...]] = {
    "ginseng": ("Panax ginseng", "Withania somnifera", "Eleutherococcus senticosus"),
}

FORMULATIONS: tuple[SeedFormulation, ...] = (
    SeedFormulation("Triphala", ("Phyllanthus emblica", "Terminalia chebula", "Terminalia bellirica"),
                    ("Triphala churna",), "churna"),
    SeedFormulation("Trikatu", ("Zingiber officinale", "Piper nigrum", "Piper longum"),
                    ("Trikatu churna",), "churna"),
    SeedFormulation("Chyawanprash", ("Phyllanthus emblica", "Piper longum"),
                    ("Chyavanaprasha", "Chyavanprash"), "avaleha"),
    SeedFormulation("Kaishore Guggulu",
                    ("Commiphora wightii", "Tinospora cordifolia", "Phyllanthus emblica",
                     "Terminalia chebula", "Terminalia bellirica"),
                    ("Kaishora Guggulu",), "vati"),
    SeedFormulation("Yogaraja Guggulu", ("Commiphora wightii", "Zingiber officinale", "Piper longum"),
                    ("Yogaraj Guggulu",), "vati"),
    SeedFormulation("Haridra Khanda", ("Curcuma longa",), (), "khanda"),
    SeedFormulation("Ashwagandharishta", ("Withania somnifera",), ("Ashwagandha arishta",), "arishta"),
    SeedFormulation("Brahmi Ghrita", ("Bacopa monnieri",), ("Brahmi ghrta",), "ghrita"),
    SeedFormulation("Sitopaladi Churna", ("Piper longum",), ("Sitopaladi",), "churna"),
)
