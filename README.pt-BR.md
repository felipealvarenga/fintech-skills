# fintech-skills

Skills de engenharia fintech para agentes de código: um ponto de entrada de auditoria e doze
skills que ensinam Claude Code, Codex, Cursor, Copilot e qualquer agente que leia `SKILL.md` a
tratar dinheiro como sistemas fintech de produção tratam. Toda skill vem com evals e vetores de
teste que rodam no CI.

[English](README.md)

<!-- generated:headline -->
**Medido.** Os mesmos 91 prompts rodaram no `claude-sonnet-5-5` com e sem as skills (skills em
`ee4f998`), e uma sessão separada do mesmo modelo avaliou cada transcrição contra expectativas escritas antes
da execução. A nota é a fração das expectativas que o avaliador marcou como atendidas; o código do agente é
lido, não executado. **Com as skills, 72%. Sem elas, 27%** (267 contra 99 de 370). Por skill,
método e transcrições brutas: [evals/results/20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md). Os prompts são prompts de desenvolvimento: as skills foram revisadas
contra as falhas das execuções anteriores nestes mesmos prompts, e um conjunto reservado é o próximo passo.
<!-- /generated:headline -->

## Por quê

Agentes escrevem código de pagamento rápido e errado do mesmo jeito que pessoas: float para
valores, coluna de saldo atualizada no lugar, retry que cobra duas vezes, webhook tratado como
verdade, conciliação que esconde diferenças atrás de uma tolerância. Cada skill corrige um
desses, com regras testáveis, um checklist de revisão e os testes que a mudança precisa incluir.

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
| Skill | Use quando | Com / sem | Vetores |
|---|---|---|---|
| [fintech-audit](skills/fintech-audit/SKILL.md)† | Auditar um repositório ou um PR que mexe com dinheiro; o ponto de entrada | 77% / 50% | py |
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Guardar, somar, ratear, converter, arredondar ou formatar valores | 83% / 33% | py, ts |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Qualquer tabela que responde "quanto X tem ou deve" | 82% / 32% | py, ts |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Criar, capturar, estornar ou pagar; chamar um processador | 93% / 25% | py, ts |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receber callbacks de processadores, bancos e PSPs | 69% / 7% | py, ts |
| [reconciliation](skills/reconciliation/SKILL.md) | Conciliar ledger, relatório do processador e extrato bancário | 72% / 24% | py |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Integrar com QuickBooks, Xero, NetSuite, Omie, Conta Azul | 64% / 14% | py |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizar transações com regras, ML ou LLM, em especial com lançamento automático | 56% / 22% | py |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Coletar, logar, exibir ou exportar dados pessoais, bancários ou de cartão | 67% / 41% | py |
| [audit-trail](skills/audit-trail/SKILL.md) | Qualquer mutação de dinheiro, limites, permissões ou dados de cliente; ações de agentes | 78% / 22% | py |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Juros, parcelas, tabelas Price e SAC, provisões, taxa efetiva | 68% / 18% | py |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, parcelamento no cartão, CPF e CNPJ, NF-e | 69% / 17% | py, ts |
| [money-tests](skills/money-tests/SKILL.md) | Escrever ou revisar testes para qualquer item acima | 60% / 40% | py |

Uma execução por prompt. Uma célula de cerca de 28 expectativas carrega cerca de ±16 pontos (intervalo de Wilson a 95%); os números do pacote carregam cerca de ±5. † fintech-audit foi medida sem o lint que ela roda: o sandbox do eval não tem shell, então a linha e o relatório de exemplo (produzido com shell) não são o mesmo arranjo.
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
| Execução | Skills em | Sujeito | Com | Sem | Ganho (pontos) |
|---|---|---|---|---|---|
| [20261108T035910Z-c7e767e](evals/results/20261108T035910Z-c7e767e/summary.md) | `c7e767e` | `claude-sonnet-5-5` | 62% | 25% | 36.8 |
| [20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md) | `ee4f998` | `claude-sonnet-5-5` | 72% | 27% | 45.4 |

Em 1 das 91 sessões com skill da última execução o agente nunca abriu a skill; essa sessão conta contra as skills.
<!-- /generated:runs -->

## Escopo

São práticas de engenharia, não aconselhamento contábil, fiscal ou jurídico. Onde uma regra
depende da jurisdição (arredondamento legal, códigos de imposto, CET, prazos de retenção), a
skill diz isso e mantém a parte de engenharia. Mecânica de API de fornecedor fica com o plugin
do fornecedor: a Stripe tem o dela, a Intuit tem `intuit-developer` e `quickbooks-labs`.

## Como foi feito

Escrito por Felipe Alvarenga a partir de trabalho em produção com crédito, pagamentos e
integrações contábeis no Brasil e nos EUA, redigido e iterado com Claude Code. Os vetores rodam a
cada push. Os evals avaliados rodam antes de cada release e as falhas de cada execução mudam as
skills para a seguinte; os resumos das execuções registram o que mudou e por quê.

<!-- generated:cut-rule -->
A regra de corte declarada antes da primeira execução: skill que não move os próprios evals em pelo menos
10 pontos é incorporada a outra ou removida. Na última execução o menor ganho foi de 20.0 pontos (money-tests)
e o maior de 67.9 (idempotent-payments). O ruído de uma célula é de cerca de ±16 pontos, então a regra é aplicada
sobre execuções repetidas, não sobre uma.
<!-- /generated:cut-rule -->

## Licença

MIT.
