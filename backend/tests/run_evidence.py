"""Executar de backend/: python tests/run_evidence.py. Sem API/FTP/BD."""
import platform
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
destination = Path('../docs/evidencias/correcoes-c001/TESTES-RUNNER.txt')
destination.parent.mkdir(parents=True, exist_ok=True)
with destination.open('w', encoding='utf-8') as log:
    log.write('Data da execução: 2026-11-04 (America/Sao_Paulo)\n')
    log.write('Comando: python tests/run_evidence.py\n')
    log.write(f'Ambiente: {platform.platform()}; Python {platform.python_version()}\n')
    log.write('Tipo: testes locais unitários, HTTP ASGI e SQLite; FTP simulado e loopback real.\nSomente dados sintéticos; sem homologação ou produção.\n\n')
    suite = unittest.defaultTestLoader.discover('tests')
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    log.write(f'\nTotal={result.testsRun}; falhas={len(result.failures)}; erros={len(result.errors)}; ignorados={len(result.skipped)}\n')
print(destination.read_text(encoding='utf-8'))
sys.exit(not result.wasSuccessful())
