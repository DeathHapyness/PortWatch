# Modelo de ameaça

**Estado:** baseline da v1  
**Última revisão:** 2026-08-26

## Escopo

Este documento cobre a API, o Collector no mesmo processo, o dashboard web,
o `docker-socket-proxy` e o Netprobe. O website institucional e a segurança do
próprio host Docker fora desses componentes não estão no escopo.

PortWatch é somente-observação na v1. Qualquer recurso que inicie, pare,
reinicie ou execute comandos em containers exige uma nova análise de ameaça e
uma decisão arquitetural explícita.

## Ativos protegidos

- token estático da API;
- inventário de containers, imagens, redes, portas e estado de saúde;
- labels e variáveis de ambiente retornadas pelo Docker;
- socket e API do daemon Docker;
- topologia, endereços e serviços do homelab;
- disponibilidade do backend e integridade do snapshot publicado.

Mesmo sem dados pessoais, esse inventário facilita reconhecimento da rede e
deve ser tratado como informação operacional sensível.

## Fronteiras de confiança

1. **Navegador → API/WebSocket.** Tráfego pode atravessar rede local ou reverse
   proxy. Fora de loopback, TLS e controle de acesso externo são responsabilidade
   do operador.
2. **Collector → docker-socket-proxy.** O proxy é a única fronteira autorizada
   para o Docker; o backend não deve montar o socket diretamente.
3. **docker-socket-proxy → daemon Docker.** Comprometimento do proxy pode expor
   dados permitidos pelos endpoints GET, mesmo sem habilitar mutações.
4. **Collector → Netprobe.** O payload é não confiável e precisa de timeout,
   limite de tamanho e validação antes de virar estado interno.
5. **Netprobe → namespace de rede do host.** `network_mode: host` é necessário
   para ler portas, mas amplia visibilidade. O processo não recebe socket Docker
   nem capabilities.
6. **Configuração/CI → processo.** Variáveis, imagens, dependências e artefatos
   de build são entradas de cadeia de suprimentos.

## Adversários considerados

- cliente remoto sem token tentando enumerar ou indisponibilizar a API;
- cliente autenticado malicioso ou token vazado;
- processo local não privilegiado tentando abusar do Netprobe;
- resposta Docker/Netprobe malformada, excessiva ou comprometida;
- dependência ou imagem de container comprometida;
- operador cometendo erro de bind, proxy ou configuração.

Não assumimos proteção contra um atacante que já controla o host, o daemon
Docker ou a conta administrativa do repositório. Esses níveis podem substituir
binários, ler memória/configuração ou alterar imagens e tornam controles da
aplicação insuficientes.

## Ameaças e controles da v1

| Ameaça | Controle esperado | Risco residual |
|---|---|---|
| API exposta sem autenticação | Startup recusa bind declarado fora de loopback sem token | Reverse proxy pode expor um bind local sem que a aplicação detecte |
| Token em URL/log | Bearer no HTTP; primeira mensagem no WebSocket; redação best-effort de logs | Token estático vazado concede acesso até ser rotacionado |
| Token embutido no frontend | Token deve ser informado em runtime antes do release público | `localStorage` pode ser lido por código executado na mesma origem; XSS permanece relevante |
| Leitura excessiva do Docker | Proxy GET-only e allowlist mínima; backend sem socket direto | Endpoints de leitura ainda revelam metadados sensíveis |
| Vazamento por labels/env | Redação por nomes sensíveis antes da publicação | Nomes incomuns podem escapar de uma heurística de redação |
| Payload malformado ou enorme | Validação de shape, timeouts e limites explícitos | Chamadas síncronas podem ultrapassar um deadline até o timeout de transporte |
| Snapshot parcial/inconsistente | Construção fora do lock e publicação atômica | Último snapshot pode ficar stale durante falhas prolongadas |
| Exaustão por WebSocket | Limite global de assinantes e fila limitada por assinante | Conexões dentro do teto ainda consomem recursos |
| Clickjacking/MIME sniffing | `X-Frame-Options` e `X-Content-Type-Options` após integração do middleware aprovado | Cabeçalhos não substituem CSP nem correção de XSS |
| Imagem/dependência comprometida | Locks, ações pinadas por SHA, CI e atualizações automatizadas | Atualização maliciosa ainda pode passar sem revisão adequada |

## Requisitos para mudanças futuras

Uma mudança deve atualizar este documento quando:

- adicionar endpoint mutável, persistência ou conta de usuário;
- montar novo path do host ou conceder capability;
- expor um componente fora de loopback;
- alterar autenticação ou armazenamento de token;
- adicionar nova fonte de dados ou serviço externo;
- mudar a fronteira entre backend, proxy Docker e Netprobe.

## Divulgação

Detalhes exploráveis não devem ser publicados em issues. Após integração dos
arquivos comunitários, use `.github/SECURITY.md` e o canal privado de advisories
do GitHub.
