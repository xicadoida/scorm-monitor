# AUD-02 — matriz vigente de validação SCORM

04/11/2026. Código atual no working tree main/fa3fbab. Resultado novo da suíte em EV-01-testes.txt: 66/66, zero falhas/erros/ignorados. Nomes abaixo são métodos existentes em backend/tests. Integração local real não significa homologação.

| Cenário | Comportamento esperado | Teste/prova existente | Resultado atual e tipo |
|---|---|---|---|
| ZIP válido/raiz ou subpasta | Aceitar e localizar conteúdo | PackageTests.test_valid_package, test_nested_package | Aprovados; filesystem real temporário |
| Upload completo pela rota | Persistir Course e publicar | ApiTests.test_upload_http_and_persistence | Aprovado; ASGI + SQLite real/FTP simulado |
| Upload HTTP real válido | Publicar e conferir arquivos/BD | demonstrar_http.py, EV-03-04-local.json | Executado; HTTP socket, autenticação, SQLite e FTP loopback reais |
| ZIP inválido/truncado/CRC | Rejeitar sem publicar | PackageTests.test_invalid_zip, test_truncated_zip, test_crc_corruption; ApiTests.test_corrupt_zip_http_rejected | Aprovados; ZIP real/ASGI isolados |
| ZIP inválido por HTTP socket | Rejeitar, zero arquivos/curso/journal | demonstrar_http.py, EV-03-04-local.json | Executado local real, sem mocks de dependências |
| Caminho inseguro, alias, link | Rejeitar | PackageTests.test_unsafe_paths, test_duplicate_case_alias, test_symlink | Aprovados; arquivos temporários |
| Limites de upload, entradas e extração | Rejeitar antes de FTP | PackageTests.test_limits, test_expansion_ratio, test_upload_limit_and_untrusted_filename | Aprovados; limites configurados em fixtures |
| Arquivo suspeito/course_code inseguro | Rejeitar | PackageTests.test_suspicious_files, test_course_code | Aprovados |
| Manifesto vazio/malformado/estrutura inválida | Rejeitar claramente | ManifestTests.test_empty_manifest, test_malformed_xml, test_wrong_structure; ApiTests.test_invalid_manifest_http_has_no_ftp_or_db_effect | Aprovados; XML real e ASGI |
| DTD/entidade externa | Rejeitar sem resolver | ManifestTests.test_entities_and_dtd | Aprovado; defusedxml, sem rede XML |
| Manifesto SCORM 1.2 e 2004 | Aceitar estrutura mínima | ManifestTests.test_manifest_12, test_manifest_2004 | Aprovados; fixtures sintéticas |
| Recurso/arquivo/launcher/default ausente | Rejeitar | ManifestTests.test_resource_reference, test_missing_resource_file, test_default_organization; PackageTests.test_missing_launcher | Aprovados |
| Referência insegura/xml:base/query | Confinar local e preservar URL legítima | ManifestTests.test_unsafe_resource_paths, test_xml_base_and_group_item, test_launcher_without_driver_folder_and_query | Aprovados |
| Substituição válida | Preservar identidade e vínculos | PublicationTests.test_replace_preserves_persisted_links; ApiTests.test_replace_http_preserves_course_id | Aprovados; SQLite real/FTP simulado |
| Substituição FTP real | Promover staging e limpar backup | LocalFtpTests.test_real_ftp_upload_and_replace | Aprovado; loopback + SQLite reais |
| Falha/corrupção em staging | Preservar anterior | PublicationTests.test_failure_during_temporary_upload, test_staged_integrity_mismatch | Aprovados; FTP simulado/SQLite real |
| Rename não suportado/swap falha | Abortamento recuperável | PublicationTests.test_rename_unsupported_does_not_touch_previous, test_failure_during_swap | Aprovados; FTP simulado |
| Resposta remota ambígua | Reconsultar/restaurar | PublicationTests.test_ambiguous_swap_applied_then_connection_lost; LocalFtpTests.test_real_ftp_rollback_after_injected_swap_response_loss | Aprovados; simulado e FTP real com falha de resposta injetada |
| Processo interrompido | Recuperar pelo journal persistido | LocalFtpTests.test_real_ftp_recovery_after_process_exit | Aprovado; subprocesso com os._exit, FTP/SQLite reais |
| Restauração/limpeza falham sucessivamente | Preservar estado e permitir retomada idempotente | PublicationTests.test_successive_restore_failures_preserve_previous_and_journal, test_successive_cleanup_failures_never_revert_committed_version, test_restore_response_lost_is_idempotent_on_retry | Aprovados; FTP simulado/SQLite real |
| Pasta anterior ausente/permissão negada | Publicar caso legítimo; não confundir erro com ausência | PublicationTests.test_missing_previous_folder, test_permission_failure_not_mistaken_for_absence | Aprovados; FTP simulado |
| Commit falha/é aplicado sem resposta | Reconciliar decisão SQL e arquivos | PublicationTests.test_database_failure_rolls_back_remote, test_ambiguous_database_commit_keeps_committed_version | Aprovados; SQLite real/driver com falha injetada |
| Publicações simultâneas do mesmo curso | Excluir segunda operação antes de alterar FTP | PublicationTests.test_simultaneous_publication_same_course_is_excluded | Aprovado; threads/sessões reais, FTP simulado |
| Dez manifestos publicados locais | Preservar compatibilidade mínima | verificar.py, VERIFICACAO.json | 10 aceitos: seis 1.2/quatro 2004, hashes preservados |
| Servidor de homologação, TLS, falhas físicas, escritores externos | Confirmar política/capacidades reais | Checklist C0-09 | Pendente; nenhuma infraestrutura externa acessada |

## Fluxo e limites atuais

Rotas: POST /courses/upload e POST /courses/{course_code}/replace-file em backend/routes/courses.py:70/:110. Ambas usam prepare_package e publish_course; os trabalhos FTP/SQL ocorrem em threadpool. Antes da extração são conferidos limites/metadados de entradas/caminhos/links/duplicatas/nomes suspeitos e manifesto único. Durante a leitura extraída, limites reais e CRC; depois, XML e referências locais. Nenhum FTP é iniciado antes da validação completa. Launcher deriva do primeiro SCO da organização padrão.

Valores padrão: upload/arquivo 100 MiB, total extraído 500 MiB, 10.000 entradas, razão 200, manifesto 2 MiB; configuráveis por SCORM_MAX_*. Defusedxml rejeita DTD/entidades. Validação é mínima, não XSD/sequencing/antimalware. Multipart/proxy, disco, carga e conteúdo ativo têm limites operacionais próprios.

FTP: journal pending persistido → staging/identidade → conferência de lista/SHA-256 por RETR → probe de rename → anterior em backup → novo final → Course/CatalogState/journal committed no mesmo commit → limpeza. Falhas usam conexões novas e decisão durável; erro desconhecido preserva journal/backup. 409 para operação ocupada, 503 para reconciliação indisponível; validação mantém contrato success=false com HTTP 200. Recovery após reinício é offline e idempotente com escritores parados.

Não há transação FTP/SQL ou garantia de disponibilidade contínua. A PK serializa publicações cooperantes, não edição/exclusão legada ou ferramentas externas. A restauração depende de BD/backup preservados, destino certo e permissões. Procedimento completo: docs/SCORM_PUBLICACAO_RECUPERACAO.md. A auditoria AUD-02 atende seu critério de matriz existente/faltante e exemplos; isso não representa homologação concluída.
