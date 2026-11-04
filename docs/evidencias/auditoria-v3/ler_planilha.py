"""Leitura apenas; salva extrato dos critérios, não edita a planilha."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import openpyxl

source = Path(r'C:\Users\Usuário\Downloads\iaclube-plano-visual-evidencias-v3-auditoria-preliminar.xlsx')
before = hashlib.sha256(source.read_bytes()).hexdigest()
book = openpyxl.load_workbook(source, read_only=True, data_only=True)
sheet = book['Execução técnica']
rows = []
for number, row in enumerate(sheet.values, 1):
    if isinstance(row[0], str) and row[0].startswith(('AUD-', 'C0-', 'C1-', 'M1-')):
        rows.append(dict(id=row[0], titulo=row[4], escopo=row[6], criterio_pronto=row[7],
                         dependencias=row[8], status=row[10],
                         origem=f"'Execução técnica'!A{number}:W{number}"))
book.close()
after = hashlib.sha256(source.read_bytes()).hexdigest()
assert before == after
result = dict(arquivo=str(source), arquivo_exato_com_sufixo_1_encontrado=False,
              sha256=before, arquivo_preservado=True, total=len(rows),
              contagem_status=dict(Counter(row['status'] for row in rows)), tarefas=rows)
Path(__file__).with_name('PLANILHA_REFERENCIA.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'tarefas'}, ensure_ascii=False, indent=2))
