"""Atualiza a vers\u00e3o do cat\u00e1logo ap\u00f3s corrigir o formato dos links padr\u00e3o."""
from catalog_utils import touch_catalog
from database import SessionLocal


def main():
    db = SessionLocal()
    try:
        touch_catalog(db)
        db.commit()
        print("Cat\u00e1logo marcado como atualizado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
