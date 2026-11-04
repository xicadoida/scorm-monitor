"""Executar explicitamente antes de habilitar o novo upload/replace."""
from database import engine
from models import ScormPublication


def migrate(bind):
    ScormPublication.__table__.create(bind=bind, checkfirst=True)


if __name__ == '__main__':
    migrate(engine)
    print('Tabela scorm_publications disponível; nenhuma publicação executada.')
