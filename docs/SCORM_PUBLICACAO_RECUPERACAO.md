# C0-01 — publicação e recuperação SCORM

Estado implementado em 04/11/2026. Ver resultados em `evidencias/RELATORIO_CORRECOES_C001.md`. Esta versão sucede o snapshot auditado na v3; não houve deploy.

## Contrato do pacote

Upload e substituição usam `prepare_package`/`extract_package` e `validate_manifest`. Permanecem limites de upload, entradas, arquivo, total extraído e razão de expansão, verificações de caminhos/links/duplicatas e CRC. O manifesto tem limite próprio SCORM_MAX_MANIFEST_BYTES (2 MiB), parser defusedxml, rejeição de DTD e entidades internas/externas, estrutura manifest/organizations/resources e namespaces SCORM 1.2 ou 2004. Conferem-se a organização padrão, os recursos dos itens, os SCOs locais, os arquivos declarados, dependências e xml:base. O launcher deriva do primeiro SCO referenciado na organização padrão; query/fragmento são preservados e o caminho local é codificado para URL. Não se exige scormdriver/indexAPI.html: pacotes de outras ferramentas continuam possíveis.

Referências locais devem existir dentro da raiz do pacote. URI percent-encoded é decodificada para verificação, e traversal, caminho absoluto, drive, esquema local ou backslash são rejeitados. Arquivos de asset declarados com HTTP(S) podem ser externos: não são baixados/validados; launcher de SCO externo não é suportado. XML schemaLocation não é carregado. Esta é validação mínima, não conformance XSD, engine de sequencing/multi-SCO, análise antimalware ou certificado de conformidade SCORM. Alguns erros só aparecem após extração temporária; nunca após publicação.

## Estado durável e sequência

Migração explícita cria `scorm_publications`: course_code (PK), token, state, target_key, had_previous e created_at. A PK impede duas publicações gerenciadas simultâneas do mesmo código, incluindo vários workers compartilhando o mesmo banco.

1. Validar ZIP e manifesto integralmente. Rejeitar cadastro duplicado; substituição exige curso existente.
2. Persistir intenção `pending` antes de conectar ao FTP. A operação registra fingerprint de host/porta/usuário/base/TLS; uma mudança de destino bloqueia reconciliação automática.
3. MLSD bem-sucedido no pai determina presença da pasta anterior. Erro de permissão não significa ausência. Persistir had_previous antes de alterar pastas.
4. Criar `.stage-{code}-{token}` e marcador `.iaclube-publication`; transferir todos os arquivos. Conferir lista de arquivos e ler novamente cada arquivo com RETR para comparar SHA-256. Estoques grandes têm custo de leitura/banda correspondente.
5. Renomear staging → probe → staging para confirmar suporte RNFR/RNTO de diretórios no destino sem tocar o curso anterior. Se não houver suporte, abortar mantendo a versão anterior.
6. Se existir versão anterior, renomear final → `.backup-{code}-{token}`. Renomear staging → final e conferir identidade.
7. Em uma transação SQL, criar/atualizar Course, sua URL, timestamp e CatalogState; marcar intenção `committed`. Matrículas, sessões e frequência não são recriadas.
8. Reconciliar a operação e limpar backup/staging. Só depois excluir o journal. Falha de limpeza após commit retorna sucesso com recovery_pending=true e retém o journal; novas publicações ficam bloqueadas até reconciliação.

| Estado durável | Ação de recuperação |
|---|---|
| pending + backup presente | Identificar versão nova pelo marcador, afastá-la para failed e restaurar backup antes de limpar staging. |
| pending + had_previous=true sem backup | Exigir final anterior identificável; se final estiver ausente ou corresponder à nova versão, parar e preservar tudo. |
| pending + had_previous=false | Remover da posição final somente a nova versão identificada, retornando ao estado sem arquivos anteriores. |
| pending + had_previous não definido | Nenhuma troca foi iniciada; não tocar final. Limpar somente staging identificado ou pasta temporária vazia. |
| committed | Manter versão nova identificada; limpar backup/temporários. Nunca reverter só porque a limpeza falhou. |
| Estado/identidade desconhecidos ou BD inacessível | Não adivinhar: preservar arquivos e intenção e exigir reconciliação. |

Após erro de comando remoto, a implementação abandona a conexão anterior e reconsulta o BD e o FTP em conexões novas. Se um commit foi aplicado sem resposta, o journal committed permite finalizar a versão nova. Se a decisão não pode ser lida, o backup permanece. Remoções de staging exigem identidade; um staging parcial sem marcador válido e não vazio exige inspeção manual. Marcador é removido ao fim da limpeza para permitir retomada; diretório vazio também pode ser limpo.

## Limites das garantias

- FTP/SQL não têm transação conjunta. Há uma janela entre renames com curso indisponível, e outra com arquivos novos antes do commit SQL. Outros leitores podem observar essa janela; journal/backup permitem recuperar, não tornam a troca atomicamente visível.
- O servidor precisa cumprir MLSD, STOR, RETR, MKD, DELE/RMD e RNFR/RNTO para diretórios irmãos. A prova de staging testa capacidade, não prova atomicidade ou durabilidade em queda do servidor. Não há fallback que apague a versão antiga se rename não funcionar.
- O banco e o armazenamento precisam conservar dados após falha. Recuperação depende de preservar o journal, o backup e a configuração correspondente; perda simultânea de BD e backup exige backup operacional independente.
- Só as operações desta camada cooperam com a PK. As rotas administrativas de criar/editar/excluir rejeitam journal visível, mas não há transação distribuída com todos os escritores legados ou FTP externo. A checagem nessas rotas não elimina uma corrida iniciada antes da intenção. Bloquear manutenção/edição/exclusão concorrente e acessos FTP externos durante publicação e recuperação; homologar essa política. Não se garante exclusão mútua com ferramentas externas ou bancos diferentes.
- A recuperação após reinício é explícita e offline, não automática durante startup; um worker não deve reverter publicação ainda ativa em outro. Uma interrupção pode exigir intervenção antes de o curso voltar a funcionar.
- FTP clássico continua como default legado; FTPS é opt-in com validação de certificado e canal de dados protegido. Homologação deve escolher transporte seguro. FTPS não foi ensaiado nesta rodada; os testes reais usam loopback sem TLS e dados fictícios.
- Nenhuma alteração de isolamento do iframe/C0-02, notas/C0-08 ou política de exclusão/C0-06 foi implementada. O marcador é operacional, não credencial nem proteção contra outra pessoa com acesso de escrita ao FTP.
- Limites da aplicação não substituem limites de corpo multipart/proxy, quotas, timeout total, espaço em disco ou limitação de concorrência. XSS/conteúdo ativo dos cursos permanece tema C0-02.

## Preparação e migração (não executadas em produção)

Usar dependências `backend/requirements.txt` (agora inclui defusedxml); para testes, `backend/requirements-test.txt` acrescenta httpx e pyftpdlib. Na raiz, foi criado `.venv-c001/`, ignorado no Git. Nenhuma configuração global foi alterada.

Com API e escritores parados, backup de BD e arquivos preservado e apontamento do ambiente revisado, executar em backend/:

```powershell
python migrate_add_scorm_publications.py
```

O script cria somente a nova tabela, via engine de DATABASE_URL; é idempotente. Não executa upload/FTP, não muda Course e não roda os demais scripts. A migração foi testada em SQLite novo e SQLite com Course preexistente. Outro banco exige validação própria. AUTO_CREATE_SCHEMA permanece desabilitado por padrão; a API nova depende desta tabela inclusive para as guardas administrativas.

Variáveis novas: SCORM_FTP_HOST, SCORM_FTP_PORT, SCORM_FTP_USER, SCORM_FTP_BASE_DIR, SCORM_FTP_TLS, SCORM_PUBLIC_BASE_URL e SCORM_MAX_MANIFEST_BYTES. FTP_PASSWORD guarda a senha privada. Limites ZIP anteriores continuam válidos. Defaults FTP/URL preservam o destino legado: para ensaios é obrigatório configurar explicitamente destino segregado. Não basta trocar DATABASE_URL. A configuração nova cobre upload/replace/recuperação; exclusão legada e logos ainda têm configuração própria, fora deste ensaio. Não exercitar essas outras rotas contra um destino supostamente isolado apenas pelas novas variáveis.

## Recuperação após interrupção

1. Suspender todos os escritores de cursos (API/workers, jobs e FTP externo); preservar backup e journal; confirmar BD e destino corretos.
2. Consultar, sem alterar arquivos, em backend/: `python recover_scorm_publication.py --course CODIGO`.
3. Revisar a operação e executar `python recover_scorm_publication.py --course CODIGO --apply` somente com escritores parados.
4. Se o script finalizar com erro, não apagar tabela ou backup para desbloquear o curso. Conferir caminhos, permissões, configuração e marcador; corrigir o impedimento e repetir. Operação normal é idempotente.
5. Validar arquivo/URL/BD e vínculos antes de reabrir escritores. Remover manualmente conteúdo desconhecido só após inspeção e cópia de segurança por operador autorizado.

Esses comandos não foram executados contra produção ou homologação. A recuperação foi exercitada com SQLite e FTP simulados e também em FTP loopback real após falha injetada de resposta de rename.

## Homologação necessária

Confirmar ambiente C0-09 isolado, credenciais próprias e dados fictícios; aplicar migração; conferir MLSD/rename/permissões com o usuário real de teste; upload válido e substituição preservando vínculos; rejeições sem mutações; falhas antes/depois de STOR, rename e commit; interrupção/reinício de processo e recuperação offline; limpeza interrompida, disco cheio, tráfego concorrente e janelas de leitura; transporte TLS e certificado; aceite técnico e de conteúdo. Guardar logs sanitizados por cenário e versão. Esta etapa permanece pendente.
