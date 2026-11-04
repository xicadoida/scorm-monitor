# Consolidação C0/C1 — 04/11/2026

Consolidação vigente das cinco tarefas e próximas prioridades: [RELATORIO_ATUALIZACAO_PLANO.md](evidencias/RELATORIO_ATUALIZACAO_PLANO.md). A [matriz SCORM atual](evidencias/consolidacao-atual/MATRIZ_SCORM.md) e as novas evidências substituem, para acompanhamento corrente, a matriz e a ordem de ações históricas abaixo. Não é necessário reimplementar a C0-01 ou recuperar uma branch antiga para repetir os testes atuais.

Atualização posterior às auditorias: as correções C0-01 estão descritas em [publicação e recuperação](SCORM_PUBLICACAO_RECUPERACAO.md) e [relatório de correções](evidencias/RELATORIO_CORRECOES_C001.md). O conteúdo abaixo preserva o snapshot anterior às correções: afirmações de ausência de manifesto XML validado ou staging/rollback descrevem aquele momento, não o estado atual. Resultados e limitações atuais devem ser consultados nesses novos documentos. A revisão separada C0-08 está em [revisão semântica](evidencias/C0-08-REVISAO_SEMANTICA.md).

Escopo: AUD-01, AUD-02, C0-01 e diagnóstico C0-09/C0-10. Nenhuma execução C0-02 ou C1. Este documento foi criado agora: o caminho citado no histórico não existia no checkout.

## C0-01: comparação e alteração localizada

Antes: dois fluxos duplicados, leitura integral do upload, nome fornecido pelo cliente usado como caminho no upload, extractall sem limites. Manifesto único e launcher fixo eram conferidos após extração. Upload e substituição exigem require_admin. Substituição remove pasta FTP antiga antes do envio.

Agora: `backend/scorm_package.py` compartilhado pelas duas rotas; nome temporário fixo, leitura em blocos limitada, limites configuráveis de entradas/tamanho individual/total/expansão; validação de caminhos absolutos, traversal, aliases Windows, NUL original, links, arquivos especiais, duplicatas e arquivos suspeitos; extração em subpasta exclusiva, CRC conferido ao ler e limites de bytes reais. course_code restrito antes de formar comandos FTP. Erros InvalidPackage retornam success=false e mensagem segura, mantendo contrato atual (HTTP 200). Em replace o banco é fechado quando a validação falha.

O manifesto é identificado pelo nome: NÃO é validado XML/esquema, recursos ou versão SCORM. Launcher permanece específico scormdriver/indexAPI.html para compatibilidade. HTML/JS são conteúdo esperado, não passam por análise antimalware. A lista de extensões proibidas é defesa parcial; o servidor deve impedir execução de scripts em /scorm. Nenhum pacote publicado foi modificado.

## AUD-02: publicação e falhas parciais

Upload: validar → conectar FTP → criar pasta/enviar recursivamente → quit → inserir Course e atualizar catálogo → commit. Pasta existente pode receber arquivos sem limpeza; não há checagem prévia de conflito de código nesta rota.

Replace: consultar Course → validar → conectar FTP → remover pasta antiga recursivamente → enviar novo conteúdo → quit → alterar updated_at/catálogo → commit. IDs, matrículas e sessões não são alterados diretamente; isso não comprova consistência dos arquivos.

Não há staging, backup, rollback ou recuperação de publicação interrompida no código encontrado. Funções FTP ignoram certos erros de permissão. Falha no upload pode deixar arquivos parciais; na substituição, pode perder o pacote anterior. Erro FTP de replace é devolvido com texto da exceção (risco de detalhes internos); upload não tem tratamento equivalente. Falha de quit pode ocorrer após publicação real. Perda de resposta de rename não é tratada: sequer existe rename neste fluxo. Falha de commit após publicação deixa banco e FTP divergentes. Não existe transação conjunta ou reconciliação persistente. Nenhuma dessas capacidades do relato anterior foi confirmada.

Não se recriou uma arquitetura de publicação a partir de relato sem o código original: recuperar a branch/patch anterior e revisar a estratégia de reconciliação é a próxima ação de C0-01. A mudança atual é somente uma etapa e não autoriza a publicação em produção.

## Matriz de testes

Resultados da suíte local real em `evidencias/C0-01/EV-01-testes.txt`. ZIPs sintéticos; sem mocks de FTP, HTTP ou BD. Agrupamentos com subTest não são testes adicionais no total unittest.

| Cenário | Comportamento esperado | Teste existente agora | Resultado |
|---|---|---|---|
| ZIP válido/raiz | Extrair e localizar launcher | test_valid_package | Aprovado local |
| Pacote em subpasta | Localizar raiz | test_nested_package | Aprovado local |
| ZIP inválido/truncado | Rejeitar com InvalidPackage | test_invalid_zip, test_truncated_zip | Aprovado local |
| CRC corrompido | Rejeitar, não publicar | test_crc_corruption | Aprovado local |
| ../, absoluto, drive, barra invertida, aliases | Rejeitar antes de extrair | test_unsafe_paths | Aprovado local |
| Arquivos suspeitos/ocultos | Rejeitar | test_suspicious_files | Aprovado local |
| Link simbólico | Rejeitar | test_symlink | Aprovado local |
| Alias de nome com caixa diferente | Rejeitar duplicata | test_duplicate_case_alias | Aprovado local |
| Manifesto ausente/múltiplo | Rejeitar | test_missing_manifest, test_multiple_manifests | Aprovado local |
| Launcher ausente | Rejeitar | test_missing_launcher | Aprovado local |
| Quantidade/tamanho individual/total | Rejeitar | test_limits | Aprovado local |
| Expansão ZIP | Rejeitar | test_expansion_ratio | Aprovado local |
| Upload excedido/nome externo | Limitar leitura/ignorar nome | test_upload_limit_and_untrusted_filename | Aprovado local |
| course_code inseguro | Rejeitar | test_course_code | Aprovado local |
| ZIP criptografado/compressão não suportada | Rejeitar | Não há teste dedicado | Pendente |
| Limites reais divergentes dos metadados | Interromper extração | Sem fixture dedicada | Pendente |
| Upload HTTP válido/inválido | Persistir ou rejeitar sem FTP indevido | Não há teste integrado | Pendente EV-03/04 |
| Substituição válida | Preservar vínculos e pacote consistente | Não há teste integrado | Pendente |
| Falha parcial FTP e pasta anterior ausente | Recuperar sem perda | Não há implementação/teste | Pendente EV-05 |
| Staging/backup/rollback, reinício e falha ambígua | Reconciliar estado remoto | Não há implementação/teste | Pendente |
| Falha BD após envio e concorrência | Reconciliar/rejeitar conflito | Não há teste | Pendente |

## C0-10: cobertura atual

Antes desta execução não havia diretório tests nem test_*.py no backend. Agora existem 16 métodos unittest focados no validador. Não há cobertura de autenticação (assinatura, expiração, versão/revogação, admin), matrícula (duplicação, acesso, curso inativo), sessões (dono, início/update/finish), conclusão (nota, passed/failed, persistência) ou frequência. Não substituir unittest por pytest apenas porque a planilha antiga mencionava pytest. Fixtures são arquivos sintéticos em TemporaryDirectory; não há fixtures de BD nem integração contínua comprovada. C0-10: Em andamento, nunca Concluído com base nesses testes.

## Prioridades propostas

1. Recuperar branch/patch C0-01 anterior e reconciliar com main; validar publicação recuperável e consistência BD/FTP com testes isolados, incluindo falhas ambíguas e concorrência.
2. C0-04 → C0-09: confirmar responsáveis, backup/restauração e criar homologa⁠ção isolada. Só então executar EV-03/04/05.
3. Completar execução local AUD-01 e integração das rotas C0-01.
4. C0-10 e dependência C0-08: ampliar regressões para autenticação, matrícula, sessão/conclusão.
5. Planejar C0-03/C0-02 e demais C0 segundo riscos; C1 após estabilização e definições pedagógicas de trilhas, perfis e conclusão. Nada dessas etapas foi iniciado automaticamente.
