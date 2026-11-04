# Correções C0-01 após auditoria v3

Data: 04/11/2026, America/Sao_Paulo. Checkout `main/fa3fbaba77df92a121c42c98da6968bb9d4c9a8d`. Sem commit/push/deploy. A auditoria v3 e seus logs foram lidos; sua reprodução não foi confundida com correção já implementada.

## Estado encontrado e problemas confirmados

O Git já apresentava courses.py modificado, AGENTS.md, scorm_package.py, backend/tests e docs não rastreados. Esses trabalhos foram preservados e estendidos. Relatório/log v3 e EV-01 anterior permanecem como registros históricos, sem substituir seus resultados pelos atuais.

Critério C0-01: ZIP correto deve funcionar e casos maliciosos/inválidos devem ser rejeitados com mensagem clara; o pedido atual acrescenta substituição recuperável, falhas ambíguas e consistência com registros persistidos. A auditoria comprovava 16 testes locais do ZIP, mas não validação do conteúdo XML nem publicação segura.

Problema A: scorm_package.py contava nomes de manifestos e exigia launcher fixo; manifesto vazio ou XML inválido passava. Problema B: replace removia a pasta anterior antes do envio direto, sem staging/backup/journal. Falha de comunicação/commit podia deixar BD e arquivos divergentes e não havia caminho de recuperação após reinício.

## Correções implementadas agora

### A — manifesto

`backend/scorm_manifest.py`: parser defusedxml, limite de manifesto, rejeição de vazio/XML malformado/DTD/entidades; namespaces e estrutura mínima SCORM 1.2/2004; organização padrão, recursos referenciados, SCO, arquivos declarados, dependências e xml:base. Referências locais devem existir e permanecer na raiz do pacote, incluindo após percent-decoding. Não há fetch XML/XSD/entidades. Launcher deriva do SCO, com URL codificada, permitindo também res/index.html e ferramentas sem scormdriver. Estrutura mínima não equivale a validação integral XSD/sequencing ou certificado SCORM.

`backend/scorm_package.py` mantém proteções e limites ZIP, integra validação XML antes de qualquer FTP e devolve erro InvalidPackage. Os 16 testes preexistentes foram mantidos e tiveram suas fixtures válidas atualizadas: `<manifest/>` deixou de representar um pacote válido. Regressões adicionais verificam as falhas reais anteriormente observadas.

### B — publicação recuperável

`backend/scorm_publication.py`: intenção durável pending em tabela própria, exclusão por código de curso, staging com token e conferência de lista/SHA-256 por leitura FTP, teste de rename no staging, preservação da versão anterior em backup, promoção de staging e commit conjunto de Course/CatalogState/decisão committed. Identidade e caminhos são conferidos antes da reconciliação. Não há fallback destrutivo quando o servidor não suporta rename.

Falha controlável antes do commit reconcilia com conexões novas e restaura o anterior. Commit aplicado sem resposta é identificado por estado committed no banco; a nova versão é mantida. Falha de restauração ou estado desconhecido preserva journal e arquivos e bloqueia nova publicação. Limpeza que falha após commit não reverte o curso: retorna recovery_pending=true. Marcadores permanecem até o fim da limpeza; pasta temporária vazia pode ser removida em nova tentativa. Conteúdo não vazio sem identidade válida exige operador.

`backend/routes/courses.py`: upload e replace usam a mesma camada em threadpool, mantendo contratos anteriores de sucesso e erro de validação. Erros de recuperação retornam 503 sem texto interno, journal ocupado 409. Cadastro duplicado é rejeitado antes do FTP; pasta preexistente desconhecida não é sobrescrita no upload novo. Criação/edição/exclusão administrativas rejeitam journal visível. Essa guarda não resolve todas as corridas com escritores legados/externos; ver limites.

`backend/models.py`: ScormPublication; migração explícita `backend/migrate_add_scorm_publications.py`. `backend/recover_scorm_publication.py` oferece consulta sem efeito e reconciliação com --apply, somente após parar escritores. Não há recuperação automática no startup que possa reverter operação ativa de outro worker.

Os dados de curso, catálogo e journal usam a mesma transação SQL na decisão final. Matrículas, sessões e frequência não são recriadas pela publicação. Há testes de preservação de Course.id, matrícula e sessão passed e de rollback dos registros após falha.

## Arquivos modificados/criados nesta rodada

Alterados: `.gitignore` (ignora .venv-c001), `backend/.env.example` (somente nomes/exemplos e limites), `backend/requirements.txt` (defusedxml, preservado UTF-16), `backend/models.py`, `backend/routes/courses.py`, `backend/scorm_package.py`, `backend/tests/test_scorm_package.py`, `backend/tests/run_evidence.py`, `docs/PLANO_EXECUCAO_C0_C1.md`, `docs/ARQUITETURA_EXECUCAO_LOCAL.md`, `docs/evidencias/C0-01/INDICE.md`.

Criados de implementação: `backend/scorm_manifest.py`, `backend/scorm_publication.py`, `backend/migrate_add_scorm_publications.py`, `backend/recover_scorm_publication.py`, `backend/requirements-test.txt`.

Criados de teste: `backend/tests/scorm_fixtures.py`, `backend/tests/publication_fixtures.py`, `backend/tests/test_scorm_manifest.py`, `backend/tests/test_scorm_publication.py`, `backend/tests/test_scorm_api.py`, `backend/tests/test_scorm_ftp_local.py`, `backend/tests/publication_crash_worker.py`.

Documentação/evidências novas: este relatório, `docs/SCORM_PUBLICACAO_RECUPERACAO.md`, `docs/evidencias/C0-08-REVISAO_SEMANTICA.md` e arquivos em `docs/evidencias/correcoes-c001/` listados abaixo. Nenhuma alteração de frontend, pacotes publicados, .htaccess, Excel ou lógica de C0-08.

## Ambiente e comandos reais

Foi criado `.venv-c001` usando Python 3.12.14. A primeira tentativa de pip no sandbox falhou por restrição de sockets; a instalação foi repetida com acesso de rede autorizado e concluída somente no venv. Não foram alterados Python global, PATH ou política de scripts do Windows.

Comandos de preparação, a partir da raiz:

```powershell
& "C:\Users\Usuário\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv-c001
& ./.venv-c001/Scripts/python.exe -m pip install --retries 0 -r backend/requirements.txt
& ./.venv-c001/Scripts/python.exe -m pip install --retries 0 defusedxml==0.7.1 httpx==0.28.1 pyftpdlib==2.1.0
```

O requirements foi atualizado com defusedxml; em instalação nova, usar `python -m pip install -r backend/requirements-test.txt` para obter o conjunto declarado completo. `pip check` no venv: exit 0, sem requisitos quebrados. Versões instaladas registradas em AMBIENTE.txt.

Execução final, da raiz:

```powershell
& ./.venv-c001/Scripts/python.exe docs/evidencias/correcoes-c001/verificar.py
```

O procedimento executa, com cwd backend e configuração sintética:

```powershell
& "C:\Users\Usuário\Documents\scorm-monitor\.venv-c001\Scripts\python.exe" -m unittest discover -s tests -v
```

Resultado final: **62 testes executados, 62 aprovados, 0 falhas, 0 erros, 0 ignorados; exit 0**. Os 16 testes anteriores permanecem, e 46 foram acrescentados. Métodos com subTest podem conter vários cenários, mas contam como um no total. Avisos de depreciação datetime.utcnow do padrão existente aparecem no log; não impediram os testes. Não foi feita refatoração de datas fora do escopo.

| Grupo | Quantidade | O que exercita e qual dependência é real |
|---|---:|---|
| test_scorm_package.py | 16 | ZIPs sintéticos e filesystem temporário real, caminhos/CRC/limites/extração |
| test_scorm_manifest.py | 14 | XML real local: versões 1.2/2004, vazio, malformado, DTD/XXE, referências e caminhos |
| test_scorm_publication.py | 20 | SQLite real e protocolo FTP simulado; upload completo, staging incompleto/corrupto, rename indisponível, swap/restauração falhos, efeitos ambíguos, commit antes/depois de falha, journal ocupado, destino alterado e retomada |
| test_scorm_api.py | 9 | FastAPI/ASGI via TestClient, SQLite real e FTP simulado: upload/replace/rejeição/autenticação ausente/erro sanitizado; migração idempotente em BD novo e preservação de curso existente |
| test_scorm_ftp_local.py | 3 | FTP loopback pyftpdlib com sockets/arquivos reais + SQLite real: upload/replace, rollback após perda de resposta injetada e recuperação após término abrupto de subprocesso |

No último caso, um subprocesso executa a substituição contra o FTP loopback e encerra com `os._exit(73)` após o rename real, antes do commit SQL. O processo de teste lê o journal persistido em nova sessão e restaura os arquivos anteriores, conferindo URL/registro preservados. Não é reboot do VPS, falha física do servidor ou homologação. A perda de resposta de rede é injetada no cliente; não se afirma que uma rede de produção foi interrompida.

## Compatibilidade com conteúdo existente

Os **10 manifestos encontrados em public/scorm** foram lidos sem modificação e passaram na validação de estrutura/referências: seis SCORM 1.2 e quatro 2004. SHA-256 dos manifestos preservado. Relatório individual em COMPATIBILIDADE_MANIFESTOS.json. Esse resultado não é execução no player, inventário de produção ou reimportação completa dos dez ZIPs; limites e regras de arquivos do ZIP não foram reaplicados aos diretórios publicados.

## Evidências por tipo

| Caminho relativo | Evidência e limite |
|---|---|
| docs/evidencias/correcoes-c001/TESTES.txt | EV-01 atual: saída completa dos 62 testes, comando/cwd/ambiente/exit reais |
| docs/evidencias/correcoes-c001/AMBIENTE.txt | Venv, pip check e versões instaladas, sem .env/credenciais |
| docs/evidencias/correcoes-c001/COMPATIBILIDADE_MANIFESTOS.json | Leitura local real dos dez manifestos, versões/launchers e hashes |
| docs/evidencias/correcoes-c001/PRESERVACAO.json | Hashes de sessions.py, schemas.py, App.jsx, main.jsx e .htaccess iguais ao snapshot v3 |
| docs/evidencias/correcoes-c001/verificar.py | Reprodução do teste/compatibilidade/ambiente; não sobrescreve EV-01 histórico |
| backend/scorm_manifest.py e backend/scorm_publication.py | EV-02: código verificável das correções XML, staging e reconciliação |
| backend/tests/test_scorm_api.py e TESTES.txt | EV-03/04 locais: chamadas HTTP ASGI válidas/inválidas, com FTP simulado; não há screenshot nem prova em homologação |
| backend/tests/test_scorm_ftp_local.py e TESTES.txt | EV-05 local: FTP/SQLite reais, injeção de falha e subprocesso interrompido; EV-05 em homologação continua pendente |
| docs/SCORM_PUBLICACAO_RECUPERACAO.md | EV-06: garantias, limites, requisitos de servidor, migração, recuperação e checklist operacional |

Os logs não contêm senhas, tokens de autenticação, conteúdo de .env ou alunos reais. FTP local usa somente identidade sintética no código de teste e não registra login no artefato de evidência. Logs v3 permanecem congelados e descrevem estado anterior; não executar o procedimento histórico para comprovar comportamento corrigido. O runner antigo agora grava em TESTES-RUNNER.txt no diretório atual e descreve corretamente o tipo de suíte, preservando EV-01 anterior.

## Revisão separada C0-08

Não foi alterada a lógica de sessão/nota. A classificação v3 dos cenários exigia contextualização: aprovação sem nota não é por si só defeito universal; conclusão e aprovação são dimensões separadas em 2004; nota bruta exige conhecer a escala. A suposição 0–100 do backend atual pode ser violada por 1000, mas falta contrato de versão/normalização e decisão pedagógica. Ver `docs/evidencias/C0-08-REVISAO_SEMANTICA.md`, com fontes primárias e observações do código. O cliente não transmite versão/min/max à API atual; não se inventou essa informação nem se alterou C0-08 para satisfazer mocks.

## Limitações e riscos residuais

Não há atomicidade distribuída: existe janela de indisponibilidade entre renames e janela com arquivos novos antes da decisão SQL. Recuperabilidade exige conservar journal/backup e destino correto, não garante continuidade de acesso durante toda falha. MLSD e rename de diretórios foram confirmados no FTP local e são sondados no staging de cada publicação, mas não foram verificados no servidor de homologação/produção. Não há fallback destrutivo.

A PK serializa publicações cooperantes por código. Guardas nas rotas administrativas não eliminam todas as corridas com requisições legadas iniciadas antes da intenção, ferramentas FTP externas ou bancos distintos; suspender edição/exclusão/manutenção concorrente. A recuperação manual/offline exige parar escritores para não reverter uma operação ainda ativa. Staging não vazio sem marcador, configuração alterada, perda de journal ou indisponibilidade persistente exigem operador. Não apagar journal/backup para desbloquear.

FTPS tem validação de certificado na opção TLS, mas não foi ensaiado; FTP clássico permanece default legado. Parser mínimo não implementa sequencing/XSD/antimalware nem resolve C0-02. Espaço, quotas, multipart/proxy, timeout total, concorrência e cabeçalhos de publicação exigem homologação. Não foram executados UI, navegação completa de alunos, migração em MySQL/VPS, restauração operacional de backup ou testes contra infraestrutura externa.

## Situação e próximo passo

**C0-01: Em revisão.** As lacunas principais têm implementação e regressões locais; recomenda-se revisão técnica do protocolo e do procedimento operacional antes de homologação. Não marcar Concluído, nem usar FTP loopback como aceite de C0-09. C0-08 continua Em análise e sem mudança funcional. Nenhuma tarefa C1 iniciada.

A próxima etapa é preparar C0-09 com BD/FTP/credenciais separados, revisar backup e política de escritores, aplicar a migração somente no destino autorizado e repetir os cenários com o usuário/servidor FTP reais de teste. A migração não foi aplicada em produção. Em futura publicação autorizada, enviar todos os módulos novos, instalar defusedxml e criar scorm_publications antes de reiniciar o serviço da API; não é necessário rebuild do frontend nem reboot integral do VPS para estas alterações.

## RESUMO PARA ATUALIZAÇÃO DA PLANILHA

Em 04/11/2026, no checkout main/fa3fbab com alterações locais preservadas, foram corrigidas as lacunas C0-01 da auditoria v3: manifesto vazio/XML inválido/DTD/entidades rejeitados; estrutura SCORM 1.2/2004 e referências locais verificadas; launcher obtido do manifesto. Upload e replace compartilham staging verificado por SHA-256, backup, troca por rename, journal persistente no banco e recuperação/reconciliação com conexões novas. Falhas ambíguas de commit/rename e interrupção de processo têm regressões. Nova tabela scorm_publications exige migração explícita antes de uso fora dos testes.

Resultado atual: 62 testes, 62 aprovados, 0 falhas/erros/ignorados; 16 anteriores mantidos e 46 acrescentados. Inclui SQLite real, HTTP ASGI local com FTP simulado, FTP loopback real e recuperação após os._exit em subprocesso. Dez manifestos locais passaram, seis SCORM 1.2/quatro 2004, sem alteração dos arquivos. Evidências em docs/evidencias/correcoes-c001/TESTES.txt, AMBIENTE.txt, COMPATIBILIDADE_MANIFESTOS.json e PRESERVACAO.json. Documentação operacional: docs/SCORM_PUBLICACAO_RECUPERACAO.md. Relatório: docs/evidencias/RELATORIO_CORRECOES_C001.md.

Status recomendado C0-01: Em revisão, sem conclusão por testes locais. Homologação e aceite operacional continuam pendentes. Permanecem janelas entre FTP e BD, dependência de MLSD/rename, revisão de concorrência com escritores legados/externos, transporte seguro e recuperação offline com journal/backup preservados. Próximo passo: revisão técnica e homologação C0-09 segregada. C0-08 foi apenas reinterpretada à luz das versões SCORM e regras locais; lógica intacta, decisão pedagógica pendente. Sem deploy, commit, push, alteração de produção/Excel/frontend ou funcionalidades C1.
