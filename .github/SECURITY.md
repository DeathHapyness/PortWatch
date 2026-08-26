# Política de segurança

## Versões suportadas

O PortWatch ainda está em pré-lançamento. Enquanto não houver uma versão
estável, correções de segurança são aplicadas somente à revisão mais recente da
branch `main`. Commits e cópias antigas não recebem correções retroativas.

## Reportando uma vulnerabilidade

Não abra uma issue pública com detalhes de uma vulnerabilidade ou com dados de
um ambiente real.

Use o recurso privado do GitHub em
[Report a vulnerability](https://github.com/DeathHapyness/PortWatch/security/advisories/new).
Inclua, quando possível:

- componente e versão/commit afetado;
- impacto e pré-condições para exploração;
- passos mínimos para reprodução usando dados fictícios;
- mitigação ou correção sugerida;
- indicação de qualquer informação que não possa ser publicada.

O mantenedor tentará confirmar o recebimento em até 7 dias. Prazos de correção
e divulgação serão combinados conforme severidade, complexidade e existência
de mitigação. Não é possível prometer recompensa financeira.

## Escopo especialmente sensível

Relatos envolvendo acesso ao socket Docker, fuga do `docker-socket-proxy`,
exposição de tokens, leitura de labels/env sem redação, bind fora de loopback ou
execução de operações mutáveis em containers devem ser tratados como privados.

Não teste contra sistemas que você não controla e não inclua credenciais,
endereços ou dados reais no relato.
