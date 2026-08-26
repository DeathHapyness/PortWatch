# Contribuindo com o PortWatch

Obrigado pelo interesse em contribuir. O PortWatch monitora infraestrutura
Docker e, por isso, mudanças aparentemente pequenas podem afetar isolamento,
exposição de dados e acesso ao socket do Docker.

## Antes de começar

- Abra uma issue para mudanças de arquitetura, novos recursos grandes ou
  alterações no modelo de segurança.
- Para correções pequenas, documentação e melhorias localizadas, um pull
  request direto é bem-vindo.
- Leia `CLAUDE.md`: ali estão as restrições permanentes de segurança, stack e
  fronteiras do repositório. Elas valem para contribuições humanas e de agentes.
- Nunca use dados, credenciais ou endpoints de um homelab real em testes,
  exemplos, logs ou issues.

## Ambiente de desenvolvimento

Requisitos e comandos de instalação estão no `README.md`. Testes comuns não
acessam Docker. Os testes E2E são opt-in e usam exclusivamente o sandbox local
definido em `infra/dev/docker-compose.dev.yml`.

Antes de enviar uma mudança, execute os checks da área afetada:

```sh
cd apps/backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

```sh
cd apps/web
pnpm run lint
pnpm run format:check
pnpm run test
pnpm run build
```

Mudanças em `infra/netprobe` também devem executar:

```sh
python -m unittest discover -s infra/netprobe/tests -v
```

## Pull requests

- Mantenha o escopo pequeno e evite misturar refactors não relacionados.
- Use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Inclua testes para alterações de comportamento ou explique por que eles não
  são necessários.
- Atualize documentação e ADRs quando contratos ou decisões arquiteturais
  mudarem.
- Não inclua segredos, dumps de Docker, nomes internos, IPs privados ou outros
  dados identificáveis.

Vulnerabilidades não devem ser reportadas em issues públicas. Consulte
`.github/SECURITY.md`.
