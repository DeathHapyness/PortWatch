# netprobe — utilitário mínimo de infra, não segue a stack "aprovada" do
# backend (FastAPI etc.) de propósito: função única, superfície mínima.
# Único componente do PortWatch autorizado a usar network_mode: host, e por
# isso não tem NENHUM acesso ao socket Docker (ver docs/adr/0003).
FROM python:3.14-alpine@sha256:05b2b8b732ecd268fee8727a369f936f022d1321b59befd13c30ede22769dcdc

# Usuário não-root dedicado. Leitura de /proc/net/{tcp,udp}{,6} não exige
# privilégio nenhum (esses arquivos são world-readable no namespace de rede
# do processo) e a porta de escuta (>1024) não exige CAP_NET_BIND_SERVICE —
# então não há motivo para rodar como root. Confirmado via teste manual
# (ver infra/netprobe/README.md).
RUN adduser -D -u 10001 -h /app netprobe

WORKDIR /app
COPY --chown=netprobe:netprobe netprobe.py .

USER netprobe

ENV NETPROBE_HOST=127.0.0.1 \
    NETPROBE_PORT=8088

EXPOSE 8088

ENTRYPOINT ["python3", "-u", "netprobe.py"]
