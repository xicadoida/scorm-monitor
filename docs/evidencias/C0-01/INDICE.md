# Evidências C0-01 — 04/11/2026

Última consolidação: [relatório vigente](../RELATORIO_ATUALIZACAO_PLANO.md), [suíte reexecutada](../consolidacao-atual/EV-01-testes.txt) e [EV-03/04 HTTP/SQLite/FTP locais reais](../consolidacao-atual/EV-03-04-local.json). A evidência EV-05 de homologação continua pendente. As entradas históricas abaixo não devem substituir os resultados atuais.

Registro histórico anterior às correções C0-01. Para o estado atual e os novos testes, consultar [relatório de correções](../RELATORIO_CORRECOES_C001.md) e `../correcoes-c001/TESTES.txt`. Afirmações abaixo sobre rollback ausente e 16 testes descrevem o snapshot anterior; o log histórico foi preservado.

| Código | Evidência | Classificação e limite |
|---|---|---|
| EV-01 | [EV-01-testes.txt](EV-01-testes.txt) | Execução automatizada local verificada: 16 testes, 16 aprovações, 0 falhas/erros/ignorados; Python 3.12.14, Windows 11. ZIPs sintéticos e arquivos temporários reais. Não é teste FTP com mocks nem homologa⁠ção. |
| EV-02 | [Validador](../../../backend/scorm_package.py), [rotas](../../../backend/routes/courses.py), [testes](../../../backend/tests/test_scorm_package.py) | Código inspecionável. Regras compartilhadas agora presentes; rollback ausente. Não comprova o relato de 38 testes ou branch anterior. |
| EV-03 | Pendente | Não houve upload HTTP/UI real. test_valid_package valida somente extração local, não substitui esta evidência. |
| EV-04 | Pendente | Não houve rejeição HTTP/UI demonstrada. test_invalid_zip confirma somente o validador local. |
| EV-05 | Pendente | Sem FTP de teste identificado/autorizado; publicação recuperável ausente. Não existem logs de homologa⁠ção. |
| EV-06 | [Plano técnico](../../PLANO_EXECUCAO_C0_C1.md), [arquitetura](../../ARQUITETURA_EXECUCAO_LOCAL.md), [checklist](../C0-09-CHECKLIST.md) | Documentação verificável criada nesta execução; não constitui aceite de homologa⁠ção. |

Nenhum teste manual pela interface, imagem, deploy, commit ou push foi produzido. Não há evidência com dados pessoais, segredos ou conteúdo de .env. Os testes não modificam pacotes publicados.

Execução inicial: `python -m unittest discover -s tests -v` falhou porque backend/tests não existia. Durante a criação da suíte houve falha no cenário com barra invertida: ZipInfo normaliza filename no Windows. A validação passou a inspecionar orig_filename (também para NUL) e a amostra mantém o nome original. O log EV-01 contém a execução final; não é uma cópia do relato anterior.
