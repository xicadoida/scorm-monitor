# Plano de execução C0/C1

## Estado atual

- Branch de trabalho: `c0-01-scorm-upload-security`.
- C0-01 — Segurança do upload SCORM: implementado localmente e aguardando validação de homologação.
- C1 e as demais tarefas: não iniciadas por escopo.
- Não houve migração, alteração de banco, deploy ou acesso à produção.

## C0-01 — decisões técnicas

O upload inicial e a substituição de arquivo usam agora o mesmo fluxo:

1. gravar o upload em blocos de 64 KiB em um ZIP temporário com nome controlado pelo servidor;
2. inspecionar o índice do ZIP antes de extrair;
3. extrair manualmente para uma pasta temporária separada, sem `extractall()`;
4. manter a regra existente de exatamente um `imsmanifest.xml` e de
   `scormdriver/indexAPI.html` na mesma raiz;
5. publicar somente o pacote já validado.

São rejeitados ZIPs corrompidos, criptografados, com caminhos absolutos, `..`,
barras invertidas, nomes duplicados/conflitantes, links simbólicos, tipos de
entrada anormais, quantidade excessiva de arquivos, tamanhos excessivos e
razão de compressão suspeita. Pacotes com uma pasta-wrapper continuam aceitos,
como nos SCORMs atuais.

A publicação FTP passou a usar uma pasta de staging. No upload novo, a pasta
final só é criada após a cópia completa. Na substituição, a versão anterior é
renomeada para backup, a versão nova ocupa o caminho final e o backup só é
removido após o commit local. Se o commit falhar, há tentativa de rollback
remoto. Se essa compensação falhar, a resposta evita alegar sucesso e sinaliza
que é necessária verificação manual.

O rollback de substituição também usa renomes: a versão nova vai primeiro para
uma pasta temporária, o backup anterior retorna ao caminho final e só então a
versão temporária é apagada. Assim, uma falha na troca não apaga a única versão
disponível. Se o curso existir no banco, mas a pasta FTP estiver ausente, a
substituição faz uma publicação de recuperação em staging.

## Limites configuráveis

Definidos em `backend/.env.example`; valores ausentes ou inválidos usam os
defaults abaixo.

| Variável | Default | Justificativa |
| --- | ---: | --- |
| `SCORM_MAX_UPLOAD_BYTES` | 104857600 (100 MiB) | Acima dos pacotes atuais observados, sem aceitar uploads arbitrários. |
| `SCORM_MAX_ENTRIES` | 5000 | Muito acima das cerca de 70–90 entradas dos pacotes atuais. |
| `SCORM_MAX_UNCOMPRESSED_BYTES` | 536870912 (512 MiB) | Limita expansão total de ZIP bomb. |
| `SCORM_MAX_FILE_BYTES` | 104857600 (100 MiB) | Evita um único arquivo excessivo. |
| `SCORM_MAX_COMPRESSION_RATIO` | 100 | Bloqueia expansão desproporcional por arquivo. |

Para conter a requisição antes de chegar ao Python, o proxy web deverá ter
futuramente um limite de corpo igual ou menor que 100 MiB. Essa configuração
de infraestrutura não foi alterada nesta tarefa.

## Arquivos alterados

- `backend/scorm_package.py`: validação, gravação limitada e extração segura.
- `backend/scorm_publisher.py`: staging, troca remota, backup e rollback FTP.
- `backend/routes/courses.py`: integração nos endpoints de upload e substituição.
- `backend/.env.example`: parâmetros documentados.
- `backend/tests/test_scorm_package.py`: testes de ZIP e upload temporário.
- `backend/tests/test_scorm_publisher.py`: testes de staging, falhas e rollback FTP.
- `backend/tests/test_scorm_upload_routes.py`: proteção estrutural do fluxo nos dois endpoints.

## Testes

O comando de validação local é:

```powershell
cd backend
python -m unittest discover -s tests -v
```

Resultado local: **38 testes aprovados**. A suíte cobre pacote válido na raiz
e em pasta-wrapper, manifesto ausente/duplicado, launcher ausente, ZIP
corrompido, ZIP Slip, entradas conflitantes ou malformadas, limites de
tamanho/quantidade/expansão, erro de extração, staging FTP, falha de upload,
falha de troca, rollback com preservação da versão nova, recuperação de pasta
FTP ausente, limpeza de backup e a integração estrutural dos dois endpoints
com o mesmo validador.

Também foram validados sem alteração dos arquivos reais dois pacotes já
versionados no projeto:

- `curso_005/...scorm12-q8FqlTa8.zip`: aceito (71 entradas);
- `curso_006/...scorm12-1UrM5X1Q.zip`: aceito (71 entradas).

Na varredura dos sete ZIPs versionados, quatro foram aceitos. Os três
rejeitados falharam nas mesmas regras estruturais que já existiam antes desta
tarefa: dois por manifesto duplicado e um por launcher ausente.

O parsing sintático de `routes/courses.py`, `scorm_package.py` e
`scorm_publisher.py` também foi aprovado localmente.

## Limitações remanescentes

- FTP e banco não formam uma transação única. Uma falha de rede ambígua após
  um `rename` pode exigir inspeção manual de pastas de staging ou backup.
- O servidor FTP precisa permitir listagem e renomeação de diretórios; isso
  deverá ser confirmado em homologação antes do deploy.
- São aceitos apenas ZIP_STORED e ZIP_DEFLATED, os métodos usados pelos
  pacotes SCORM atuais analisados. Não há varredura antimalware nesta camada.
- Os testes de FTP usam um servidor em memória. Não houve conexão com a
  Hostinger, acesso à produção ou teste de integração contra o backend em
  execução, conforme as restrições da tarefa.
