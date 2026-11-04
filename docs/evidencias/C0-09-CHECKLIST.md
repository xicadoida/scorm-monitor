# C0-09 — condições para homologa⁠ção

Atualização de fechamento em 04/11/2026: publicação recuperável, migração e procedimento de recuperação estão implementados e testados localmente. Nenhum ambiente externo foi identificado/autorizado. Não foram utilizadas credenciais/dados reais nem feito acesso FTP externo. Os ensaios loopback não disponibilizam homologação à equipe de conteúdo.

O operador precisa fornecer: identificação/URL do ambiente; DATABASE_URL segregado; host/porta/raiz/URL FTP; credencial exclusiva limitada à raiz de teste; transporte escolhido; autorização e janela para falhas. Os valores devem ser configurados privadamente, não anexados aos logs.

Para habilitar testes:

- [ ] Responsável informar URL, autorização e identificação inequívoca do ambiente de teste.
- [ ] API/serviço separados, com destino do frontend e CORS conferidos.
- [ ] Banco exclusivo com schema revisado e dados fictícios; provar que não aponta para produção.
- [ ] Diretório/servidor SCORM de teste e URL pública segregados; não apenas novo nome de curso na raiz de produção.
- [ ] Configurar SCORM_FTP_HOST/PORT/USER/BASE_DIR/TLS, SCORM_PUBLIC_BASE_URL e FTP_PASSWORD exclusivos. Conferir separadamente exclusão legada e logos, que não adotam todas essas variáveis; não testá-los por engano em produção.
- [ ] Com escritores parados e backup preservado, executar `python migrate_add_scorm_publications.py` no backend apontado ao banco de teste e conferir a tabela scorm_publications. Nunca usar create_all como upgrade de produção.
- [ ] AUTH_SECRET, IP_HASH_SECRET, administradores e tokens separados; e-mail desabilitado ou remetido para caixa de teste.
- [ ] Backup/restauração documentados e ensaiados com dados sintéticos (dependência C0-04).
- [ ] Confirmar MLSD, MKD, STOR, RETR, RNFR/RNTO de diretórios irmãos e DELE/RMD com o usuário de teste. O protocolo verifica staging antes de tocar o curso anterior; se rename não funcionar, abortar sem fallback destrutivo.
- [ ] Possibilidade autorizada de interromper comunicação e serviço sem atingir usuários; plano de limpeza limitado ao ambiente de teste.
- [ ] Demonstrar upload e rejeição pela API/UI (EV-03/04), substituição mantendo vínculos, falha durante envio e após publicação, perda de resposta, reinício, falha de commit e concorrência (EV-05).
- [ ] Guardar logs sanitizados com data, versão, cenário e resultado; aceitar resultados pela equipe técnica e de conteúdo.

Recuperação operacional: parar todos os escritores (API/workers/jobs e FTP externo); consultar `python recover_scorm_publication.py --course CODIGO`; após conferência, executar com `--apply`; preservar journal/backup se houver erro; conferir BD/arquivos antes de reabrir. Detalhes em `docs/SCORM_PUBLICACAO_RECUPERACAO.md`.

Critério de aceite: repetir os cenários acima usando apenas dados fictícios, registrar comando/versão/estado final e obter aceite técnico/conteúdo. Incluir publicação simultânea do mesmo código, limpeza/restauração com falhas sucessivas, pasta anterior ausente, transporte/certificado, janela de indisponibilidade e leitura durante troca. Impedir edição/exclusão/FTP externo concorrente com a publicação e parar escritores antes de recuperar.

Status recomendado: Em análise. A preparação documental está pronta; o ambiente externo ainda precisa ser fornecido, configurado e validado. Isso não impede concluir AUD-01 nem fechar a revisão técnica local C0-01.
