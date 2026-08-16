from datetime import datetime

from models import CatalogState


def touch_catalog(db):
    """Marca que o catálogo mudou dentro da mesma transação da alteração."""
    state = db.query(CatalogState).filter(CatalogState.id == 1).first()
    if state is None:
        state = CatalogState(id=1, updated_at=datetime.utcnow())
        db.add(state)
    else:
        state.updated_at = datetime.utcnow()
    return state
