# C0-08 — revisão separada, sem alteração de lógica

04/11/2026. A auditoria v3 foi excessivamente abrangente ao tratar os três cenários como contradições definitivas. Sua reprodução técnica permanece válida, mas a interpretação exige separar padrão SCORM e regra pedagógica local.

Os manifestos locais verificados indicam seis pacotes SCORM 1.2 e quatro SCORM 2004; isso é inventário de arquivos locais, não do banco ou de produção. O frontend mantém ambas as APIs: `src/App.jsx:441` recebe lesson_status, `:514` success_status e `:541` completion_status; envia score.raw sem min/max ou versão. A API `SessionUpdateRequest` também não guarda versão ou limites. Não foi possível atribuir as três requisições sintéticas da auditoria a um pacote/escala específicos.

Em SCORM 1.2, lesson_status combina estados; em 2004, success_status e completion_status são dimensões distintas. Declarar passed não exige que o SCO também publique score.raw. Em 2004, score.raw é relacionado a min/max; não se deve supor sempre porcentagem. [Referência runtime Rustici](https://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/). A ADL exemplifica normalização de raw/100 para SCORM 1.2 e usa score.scaled em 2004 para interoperabilidade. [Perfil SCORM da ADL](https://github.com/adlnet/xAPI-SCORM-Profile/blob/master/xapi-scorm-profile.md#score).

| Cenário reproduzido | Interpretação técnica | Regra IACLUBE e decisão pendente |
|---|---|---|
| passed sem nota | Pode ser declaração legítima do SCO, sem score informado. Não é defeito universal. | Backend aceita passed (sessions.py:74), coerente com parte do frontend. Decidir se todos os cursos exigem quiz/nota ou se a declaração do conteúdo basta. |
| raw=1000 aprovado | Em SCORM 2004 pode ser bruto numa escala maior; sem min/max a requisição é ambígua. Em 1.2, a normalização esperada não corresponde a 1000. | Comentário de sessions.py:93 e passing_score atual assumem 0–100; tratar 1000 diretamente como percentual viola essa suposição implementada. Falta contrato de versão/escala para decidir normalização/rejeição. Não foi encontrada aprovação pedagógica externa. |
| failed com completed=true | Em 2004, conclusão e reprovação podem coexistir legitimamente. | O LMS usa completed como aprovação no cartão: sessions.py:195 agrega passed; src/App.jsx:518 envia completed conforme passed. Falta separar conclusão pedagógica e aprovação ou formalizar que completed significa aprovado neste contrato interno. |

Conclusão: classificar C0-08 como Em análise, com implementação parcial e contrato pendente; não alterar notas nesta C0-01. A aceitação de entrada do cliente continua exigindo análise de confiança/autorizações, mas este trabalho não introduziu uma suposta validação independente de notas. `backend/routes/sessions.py`, `backend/schemas.py` e frontend foram preservados por hash em `correcoes-c001/PRESERVACAO.json`.
