"""First-run setup: schema, reference data, admin account, synthetic cohort, trained models."""
from config import settings
from data import generate_dataset
from database import db, seed
from models import predictor, trainer
from services import auth


def ensure_ready() -> None:
    db.init_db()
    seed.seed_reference_data()
    auth.ensure_admin()
    if not db.scalar("SELECT COUNT(*) FROM students WHERE is_synthetic = 1"):
        generate_dataset.seed_database()
    if not predictor.models_available():
        trainer.train_all()
        predictor.refresh()
