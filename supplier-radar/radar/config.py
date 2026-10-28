import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
CACHE = OUT / "cache"
MODELS = Path(os.environ["RADAR_MODELS"]).resolve() if os.getenv("RADAR_MODELS") else ROOT / "models"   # pesos afinados (no se suben a git); RADAR_MODELS=carpeta para usar otro juego

TRAIN = DATA / "Supplier_Risk_1_Training.xlsx"   # trae Suppliers, Materials y 30 noticias con respuesta
VALID = DATA / "Supplier_Risk_2_Validation.xlsx"  # 10 noticias con respuesta (solo para medir)
TEST = DATA / "Supplier_Risk_3_Test.xlsx"         # 20 noticias sin respuesta
HOLDOUT = DATA / "Supplier_Risk_Holdout.xlsx"       # examen independiente escrito por el equipo (con respuesta)

DATASETS = {"train": TRAIN, "val": VALID, "holdout": HOLDOUT, "test": TEST}
