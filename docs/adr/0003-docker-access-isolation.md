# ADR-0003 — Acesso ao Docker isolado por privilégio

## Status
Aceito.

## Contexto
O usuário de desenvolvimento já pertence ao grupo `docker` (acesso
root-equivalente ao host via socket). Montar `/var/run/docker.sock`
diretamente no container do PortWatch replicaria esse mesmo risco dentro da
aplicação, mesmo montado `:ro` — isso não limita as operações possíveis
através do socket.

## Decisão
- Nenhum componente do PortWatch monta o socket Docker diretamente.
  `docker-socket-proxy` (Tecnativa) é o único container com o socket
  montado, restrito a GET em `CONTAINERS, NETWORKS, INFO, EVENTS, VERSION`.
- Portas ocupadas no host exigem visibilidade da netns do host — isso é
  isolado no componente `netprobe`, que roda com `network_mode: host` e
  **sem** acesso ao socket Docker. Nenhum outro componente recebe
  `network_mode: host`.
- PortWatch é somente-observação na v1: nenhum endpoint inicia, para,
  reinicia ou executa comando em containers monitorados.

## Consequências
- O único privilégio elevado do sistema fica confinado a um componente
  minúsculo, auditável e sem acesso ao Docker — reduz drasticamente o raio
  de dano se algo for comprometido.
- Recursos de host-ports podem ser desativados (sem `netprobe`) sem afetar
  containers/portas publicadas/redes.
- Ações que mutam containers (start/stop/exec) ficam fora de escopo até uma
  decisão explícita futura, que exigiria revisar esta ADR.
