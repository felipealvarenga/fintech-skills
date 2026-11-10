# fintech-skills

Skills de engenharia fintech para agentes de código: um ponto de entrada de auditoria e doze
skills que ensinam Claude Code, Codex, Cursor, Copilot e qualquer agente que leia `SKILL.md` a
tratar dinheiro como sistemas fintech de produção tratam. Toda skill vem com evals e vetores de
teste que rodam no CI.

**Para** quem revisa o código de dinheiro que um agente escreveu, numa fintech ou num SaaS que
movimenta dinheiro, e quer que o agente faça as escolhas que um engenheiro sênior de pagamentos
faria, com os testes na mesma mudança. E para o time brasileiro que precisa de Pix, boleto, CPF e
CNPJ e NF-e certos de primeira.

[English](README.md)

<!-- generated:headline -->
**Medido.** Os mesmos 91 prompts rodaram no `claude-sonnet-5-5` e `claude-opus-5-5` com e sem as skills (skills em
`fa81209`), e `claude-sonnet-5-5` avaliou cada transcrição contra expectativas escritas antes
da execução. A nota é a fração das expectativas que o avaliador marcou como atendidas; o código do agente é
lido, não executado. `claude-sonnet-5-5`: **81% com as skills, 24% sem** (299 contra 87 de 370); `claude-opus-5-5`: **89% com as skills, 35% sem** (328 contra 130 de 370). Por skill,
método e transcrições brutas: [evals/results/20261108T180307Z-fa81209](evals/results/20261108T180307Z-fa81209/summary.md), [evals/results/20261109T103432Z-fa81209](evals/results/20261109T103432Z-fa81209/summary.md). Esses prompts são prompts de desenvolvimento: as skills foram revisadas
contra as falhas das execuções anteriores neles. No conjunto reservado, prompts em `evals/heldout/` nunca lidos ao editar uma skill: `claude-sonnet-5-5`: **70% com, 24% sem** (73 contra 25 de 105, [evals/results/20261108T194552Z-fa81209-heldout](evals/results/20261108T194552Z-fa81209-heldout/summary.md)); `claude-opus-5-5`: **81% com, 31% sem** (85 contra 33 de 105, [evals/results/20261109T110030Z-fa81209-heldout](evals/results/20261109T110030Z-fa81209-heldout/summary.md)); `claude-fable-5-2`: **88% com, 35% sem** (92 contra 37 de 105, [evals/results/20261110T031626Z-fa81209-heldout](evals/results/20261110T031626Z-fa81209-heldout/summary.md)).
<!-- /generated:headline -->

## Por que instalar

Agentes escrevem código de pagamento rápido e errado do mesmo jeito que pessoas: float para
valores, coluna de saldo atualizada no lugar, retry que cobra duas vezes, webhook tratado como
verdade, conciliação que esconde diferenças atrás de uma tolerância. Cada skill corrige um
desses, com regras testáveis, um checklist de revisão e os testes que a mudança precisa incluir.

O que você ganha nos primeiros dez minutos:

- Um prompt, `Audit this repository's money code with fintech-skills.`, e o agente devolve o que
  corrigir com arquivo, linha, regra, correção e o teste que prova. No fixture com defeitos
  plantados: 12 achados em 8 arquivos, 4 críticos.
- Vetores de teste com implementação de referência para toda skill, Python e TypeScript para as
  principais. Aponte para o seu módulo de dinheiro e rode no CI.
- Regras que o agente segue quando escreve, não só quando revisa: testes na mesma mudança, nada de
  float para valores, uma chave de idempotência por operação, webhook verificado antes de confiar.
- Números que você pode conferir. Toda execução é publicada com as transcrições, e os prompts
  reservados nunca foram usados para ajustar as skills.

Não é a ferramenta certa se você quer a API de um fornecedor documentada (use o plugin do
fornecedor, veja Escopo) ou um framework de processo para todo o desenvolvimento; estas skills são
regras de domínio e convivem com esses pacotes.

## Instalação

Claude Code:

```
/plugin marketplace add felipealvarenga/fintech-skills
/plugin install fintech-skills@felipealvarenga
```

Codex:

```sh
codex plugin marketplace add felipealvarenga/fintech-skills
codex plugin add fintech-skills@felipealvarenga
```

skills CLI:

```sh
npx skills add felipealvarenga/fintech-skills
```

Manual: copie `skills/<nome>` para `.claude/skills/` ou `.agents/skills/` do seu projeto.

As skills são arquivos Markdown em `skills/`; leia uma antes de instalar, porque uma skill instalada roda
com as permissões do seu agente. O único código do pacote são os vetores que você escolher rodar. Para
atualizar: `claude plugin update fintech-skills@felipealvarenga`, `codex plugin marketplace upgrade` e a
linha `codex plugin add` de novo, ou `npx skills update`.

O skills.sh mostra um selo do Snyk por skill. Em 2026-11-10 quatro marcavam MEDIUM: `accounting-sync`,
`brazil-payment-rails`, `transaction-classification` e `webhook-handling`. São rótulos de capacidade,
"lê conteúdo de terceiros" e "mexe com sistemas de pagamento", os mesmos que a skill `stripe-pay` da
própria Stripe carrega; nenhum achado aponta arquivo. As outras nove marcam "No issues detected".

As skills carregam no início da sessão, então abra uma sessão nova depois de instalar. Depois
mande `Audite o código de dinheiro deste repositório com fintech-skills.` em um repositório que
você conhece: o agente deve carregar a skill `fintech-audit` primeiro e reportar arquivo, linha,
regra, correção e teste. Se a transcrição não mostrar a leitura de nenhuma skill, abra uma sessão
nova. O lint da auditoria precisa de Python 3.10 ou mais novo.

## Skills

Comece pela auditoria. Ela roda um lint determinístico no seu código de dinheiro, confirma cada
pista lendo o código, aplica os checklists abaixo e reporta achados com arquivo, linha, regra,
correção e teste:

```
Audite o código de dinheiro deste repositório com fintech-skills.
```

[Relatório de exemplo](skills/fintech-audit/evals/sample-report.md) na fixture com defeitos
plantados: 12 achados em 8 arquivos, 4 críticos, cada um com arquivo, linha, regra, correção e
teste. Sonnet 5.5, 7 turnos, USD 0,21.

<!-- generated:skills-table -->
| Skill | Use quando | `claude-sonnet-5-5` com / sem | `claude-opus-5-5` com / sem | `claude-fable-5-2` com / sem, reservado | Vetores |
|---|---|---|---|---|---|
| [fintech-audit](skills/fintech-audit/SKILL.md)† | Auditar um repositório ou um PR que mexe com dinheiro; o ponto de entrada | 77% / 33% | 83% / 40% | 100% / 88% | py |
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Guardar, somar, ratear, converter, arredondar ou formatar valores | 83% / 33% | 90% / 47% | 100% / 62% | py, ts |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Qualquer tabela que responde "quanto X tem ou deve" | 82% / 25% | 93% / 39% | 100% / 38% | py, ts |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Criar, capturar, estornar ou pagar; chamar um processador | 86% / 21% | 100% / 36% | 75% / 25% | py, ts |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receber callbacks de processadores, bancos e PSPs | 86% / 7% | 86% / 28% | 100% / 22% | py, ts |
| [reconciliation](skills/reconciliation/SKILL.md) | Conciliar ledger, relatório do processador e extrato bancário | 72% / 10% | 86% / 24% | 88% / 25% | py |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Integrar com QuickBooks, Xero, NetSuite, Omie, Conta Azul | 68% / 21% | 86% / 29% | 88% / 38% | py |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizar transações com regras, ML ou LLM, em especial com lançamento automático | 100% / 22% | 96% / 26% | 100% / 25% | py |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Coletar, logar, exibir ou exportar dados pessoais, bancários ou de cartão | 63% / 37% | 81% / 44% | 75% / 62% | py |
| [audit-trail](skills/audit-trail/SKILL.md) | Qualquer mutação de dinheiro, limites, permissões ou dados de cliente; ações de agentes | 74% / 26% | 85% / 33% | 88% / 38% | py |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Juros, parcelas, tabelas Price e SAC, provisões, taxa efetiva | 71% / 18% | 79% / 32% | 75% / 38% | py |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, parcelamento no cartão, CPF e CNPJ, NF-e | 90% / 21% | 86% / 31% | 100% / 0% | py, ts |
| [money-tests](skills/money-tests/SKILL.md) | Escrever ou revisar testes para qualquer item acima | 97% / 30% | 100% / 47% | 50% / 0% | py |

Uma execução por prompt. Uma célula de cerca de 28 expectativas carrega até cerca de ±14 pontos (intervalo de Wilson a 95%); os números do pacote carregam até cerca de ±4. A coluna `claude-fable-5-2` é a execução reservada desse modelo (dois prompts por skill, células de cerca de 8 expectativas, cerca de ±22 pontos cada); leia no nível do pacote: 88% com, 35% sem. † fintech-audit foi medida sem o lint que ela roda: o sandbox do eval não tem shell, então a linha e o relatório de exemplo (produzido com shell) não são o mesmo arranjo.
<!-- /generated:skills-table -->

Toda `SKILL.md` tem a mesma forma: quando usar, regras numeradas, como aplicar, o que fazer
quando o pedido contraria uma regra, os testes que a mudança precisa incluir, checklist de
revisão, antipadrões com correção, referências. A tabela acima é gerada do frontmatter das
skills e da última execução.

## Evals

Toda skill tem `evals/evals.json` (prompts que um agente receberia e expectativas que um
avaliador confere na transcrição) e `evals/vectors/` (arquivos pytest e vitest com uma
implementação de referência, executáveis contra o seu código por uma variável de ambiente). Uma
execução avaliada manda os mesmos prompts com e sem a skill, avalia os dois lados e vai para uma
pasta própria em `evals/results/`, com os modelos, o sha do git, todas as transcrições e todos os
arquivos que o agente escreveu. Pastas antigas nunca são editadas. Método e flags:
[evals/README.md](evals/README.md).

<!-- generated:runs -->
| Execução | Skills em | Prompts | Sujeito | Com | Sem | Ganho (pontos) |
|---|---|---|---|---|---|---|
| [20261108T035910Z-c7e767e](evals/results/20261108T035910Z-c7e767e/summary.md) | `c7e767e` | desenvolvimento | `claude-sonnet-5-5` | 62% | 25% | 36.8 |
| [20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md) | `ee4f998` | desenvolvimento | `claude-sonnet-5-5` | 72% | 27% | 45.4 |
| [20261108T143507Z-ae8adc1](evals/results/20261108T143507Z-ae8adc1/summary.md) | `ae8adc1` | desenvolvimento | `claude-sonnet-5-5` | 78% | 26% | 52.4 |
| [20261108T180307Z-fa81209](evals/results/20261108T180307Z-fa81209/summary.md) | `fa81209` | desenvolvimento | `claude-sonnet-5-5` | 81% | 24% | 57.3 |
| [20261108T194552Z-fa81209-heldout](evals/results/20261108T194552Z-fa81209-heldout/summary.md) | `fa81209` | reservado | `claude-sonnet-5-5` | 70% | 24% | 45.7 |
| [20261109T103432Z-fa81209](evals/results/20261109T103432Z-fa81209/summary.md) | `fa81209` | desenvolvimento | `claude-opus-5-5` | 89% | 35% | 53.5 |
| [20261109T110030Z-fa81209-heldout](evals/results/20261109T110030Z-fa81209-heldout/summary.md) | `fa81209` | reservado | `claude-opus-5-5` | 81% | 31% | 49.5 |
| [20261110T031626Z-fa81209-heldout](evals/results/20261110T031626Z-fa81209-heldout/summary.md) | `fa81209` | reservado | `claude-fable-5-2` | 88% | 35% | 52.4 |

Em 2 das 91 sessões com skill da execução `claude-sonnet-5-5` em `fa81209` o agente nunca abriu a skill; essas sessões contam contra as skills. Em todas as 91 sessões com skill da execução `claude-opus-5-5` em `fa81209` o agente abriu a skill.
<!-- /generated:runs -->

## Escopo

São práticas de engenharia, não aconselhamento contábil, fiscal ou jurídico. Onde uma regra
depende da jurisdição (arredondamento legal, códigos de imposto, CET, prazos de retenção), a
skill diz isso e mantém a parte de engenharia. Mecânica de API de fornecedor (endpoints, OAuth,
chamadas de SDK) fica fora do escopo: use o plugin do próprio fornecedor para isso, como o plugin
oficial da Stripe ou os `intuit-developer` e `quickbooks-labs` da Intuit. Estas skills cobrem o
que esses plugins não cobrem: as regras de engenharia para dinheiro.

## Como foi feito

Escrito por Felipe Alvarenga a partir de trabalho em produção com crédito, pagamentos e
integrações contábeis no Brasil e nos EUA, redigido e iterado com Claude Code. Os vetores rodam a
cada push. Os evals avaliados rodam antes de cada release e as falhas de cada execução mudam as
skills para a seguinte; os resumos das execuções registram o que mudou e por quê.

<!-- generated:cut-rule -->
A regra de corte declarada antes da primeira execução: skill que não move os próprios evals em pelo menos
10 pontos é incorporada a outra ou removida. Na execução `claude-sonnet-5-5` em `fa81209` o menor ganho foi de 25.9 pontos (pii-and-card-data) e o maior de 79.3 (webhook-handling); na execução `claude-opus-5-5` em `fa81209` o menor ganho foi de 37.0 pontos (pii-and-card-data) e o maior de 70.4 (transaction-classification).
O ruído de uma célula é de cerca de ±14 pontos, então a regra é aplicada sobre execuções repetidas, não sobre uma.
<!-- /generated:cut-rule -->

## Licença

MIT.
