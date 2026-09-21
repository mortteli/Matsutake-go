"""Which country's feature stack, grid and rule baselines a script should use.

train.py, predict.py and the dataset builders all need the same answer to "Finland or
Sweden?", and the cheap way to get there -- copying train.py to train_se.py -- guarantees the
two drift apart the first time either is fixed. One resolver instead, so a change to the
shared machinery reaches both countries or neither.

    FEATURES, RULES, GROUPS = for_country("se")
    Sources = sources_class("se")
"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

COUNTRIES = ("fi", "se")


def feature_module(country):
    return importlib.import_module("features" if country == "fi" else "features_se")


def grid_class(country):
    if country == "fi":
        return importlib.import_module("grid").Grid
    return importlib.import_module("grid_se").GridSE


def sources_class(country):
    return feature_module(country).Sources if country == "fi" else \
        feature_module(country).SourcesSE


def features(country):
    m = feature_module(country)
    return m.FEATURES if country == "fi" else m.FEATURES_SE


def rules(country):
    """Rule baselines to report alongside the model.

    Finland's three are in train.py, built from kasvupaikka, paatyyppi and latvuspeitto.
    None of those exist in the Swedish stack, so reusing them would raise on a missing
    column. The Swedish pair below is the same idea expressed in the columns Sweden has:
    old pine, little spruce, and -- since there is no site-fertility class -- coarse ground
    and an open canopy standing in for the dry, lichen-rich site the Finnish rules name
    directly.
    """
    if country == "fi":
        return None                                  # train.py's own RULES
    return {
        "rule_se_simple": lambda d: (d.age >= 60) & (d.vol_pine >= 20) & (d.vol_spruce <= 20),
        "rule_se_dry": lambda d: (d.age >= 60) & (d.vol_pine >= 20) & (d.vol_spruce <= 20)
                                 & (d.coarse_frac160 > 0.3) & (d.cover <= 60),
    }


def groups(country):
    """Feature blocks for the ablation runs.

    Finland's are matched by suffix (`_m3`, endswith "9", endswith "31"). The Swedish names
    end in metres instead, and matching them by suffix would quietly capture the wrong
    columns -- `cover_m160` is a neighbourhood, `tpi160` is terrain, and both end in "160".
    So the Swedish blocks are listed rather than pattern-matched.
    """
    if country == "fi":
        return None                                  # train.py's own GROUPS
    F = features("se")
    return {
        "soil": [f for f in F if f.startswith(("soil_", "parent_", "coarse_frac",
                                               "rock_frac", "peat_frac", "glacfl_"))],
        "terrain": ["elev", "slope", "northness", "eastness", "tpi160", "tpi500"],
        "climate": ["thermal_sum", "precip"],
        "neigh": [f for f in F if f.endswith(("_m60", "_m160"))
                  or f in ("pine_max160", "spruce_min160", "age_max160", "open_frac160")],
        "structure": [f for f in F if f in ("cover", "understory", "ba_est", "vol_per_height",
                                            "height", "vol_total")
                      or f.startswith(("cover_m", "ba_est_m", "vol_total_m"))],
        "species": [f for f in F if f.endswith("_share")
                    or f.startswith(("vol_pine", "vol_spruce", "vol_birch", "vol_decid",
                                     "vol_contorta"))],
        "landcover": [f for f in F if f.startswith(("main_", "mire_"))
                      or f in ("productive", "improductive", "prod_missing")],
    }


def for_country(country):
    """(FEATURES, RULES, GROUPS) -- RULES and GROUPS are None for Finland, meaning
    "use the ones defined in train.py"."""
    if country not in COUNTRIES:
        raise ValueError(f"country must be one of {COUNTRIES}, got {country!r}")
    return features(country), rules(country), groups(country)
