# fintech-skills

Skills de engenharia fintech para agentes de código. Um ponto de entrada de auditoria e doze skills que ensinam Claude Code, Codex,
Cursor, Copilot e qualquer agente que leia `SKILL.md` a tratar dinheiro como sistemas fintech de
produção tratam. Toda skill vem com um eval e com vetores de teste que rodam no CI.

[English](README.md)

**Medido.** Os mesmos 91 prompts rodaram no Sonnet 5.5 com e sem as skills, e um segundo modelo
avaliou as transcrições contra expectativas escritas antes da execução. **Com as skills, 72% das
expectativas passaram. Sem elas, 27%** (267 contra 99 de 370). Por skill, método e transcrições
brutas: [evals/results/20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md).

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

## Skills

Comece pela auditoria. Ela roda um lint determinístico no seu código de dinheiro, confirma cada
pista lendo o código, aplica os checklists abaixo e reporta achados com arquivo, linha, regra,
correção e teste.

```
Audite o código de dinheiro deste repositório com fintech-skills.
```

[Relatório de exemplo](skills/fintech-audit/evals/sample-report.md) na fixture com defeitos plantados: 12 achados em 8
arquivos, 4 críticos, cada um com arquivo, linha, regra, correção e teste. Sonnet 5.5, 7 turnos, USD 0,21, nenhum código alterado.

| Skill | Use quando | Com / sem | Vetores |
|---|---|---|---|
| [fintech-audit](skills/fintech-audit/SKILL.md) | Auditar um repositório ou um PR que mexe com dinheiro; o ponto de entrada | 77% / 50% | sim |
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Guardar, somar, ratear, converter, arredondar ou formatar valores | 83% / 33% | sim |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Qualquer tabela que responde "quanto X tem ou deve" | 82% / 32% | sim |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Criar, capturar, estornar ou pagar; chamar um processador | 93% / 25% | sim |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receber callbacks de processadores, bancos e PSPs | 69% / 7% | sim |
| [reconciliation](skills/reconciliation/SKILL.md) | Conciliar ledger, relatório do processador e extrato bancário | 72% / 24% | sim |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Integrar com QuickBooks, Xero, NetSuite, Omie, Conta Azul | 64% / 14% | sim |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizar transações com regras, ML ou LLM, em especial com lançamento automático | 56% / 22% | sim |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Coletar, logar, exibir ou exportar dados pessoais, bancários ou de cartão | 67% / 41% | sim |
| [audit-trail](skills/audit-trail/SKILL.md) | Qualquer mutação de dinheiro, limites, permissões ou dados de cliente; ações de agentes | 78% / 22% | sim |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Juros, parcelas, tabelas Price e SAC, provisões, taxa efetiva | 68% / 18% | sim |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, parcelamento no cartão, CPF e CNPJ, NF-e | 69% / 17% | sim |
| [money-tests](skills/money-tests/SKILL.md) | Escrever ou revisar testes para qualquer item acima | 60% / 40% | sim |

## Evals

Toda skill tem `evals/evals.json` no formato do `skill-creator` da Anthropic: prompts que um
agente receberia e expectativas que um avaliador confere na transcrição. Todas as skills também têm
vetores: arquivos pytest com uma implementação de referência, executáveis contra o seu código
por uma variável de ambiente. Veja [evals/README.md](evals/README.md).

A execução avaliada mais recente, de 2026-11-08 (`claude-sonnet-5-5` como sujeito e avaliador, uma
execução por prompt por condição, 370 expectativas por condição), está em
[evals/results/20261108T053526Z-ee4f998](evals/results/20261108T053526Z-ee4f998/summary.md): números por skill e por eval, a
invocação exata do `claude`, todas as transcrições e todos os arquivos que o agente escreveu. Em 1
das 91 sessões com skill o agente nunca abriu a skill; essa sessão conta contra as skills. A
primeira execução, [evals/results/20261108T035910Z-c7e767e](evals/results/20261108T035910Z-c7e767e/summary.md), mediu
62% contra 25%; a leitura das falhas mostrou o agente deixando os testes como próximo passo em 48
de 140 casos e ignorando a skill em 6 prompts adversariais, e as skills mudaram pelos dois motivos.
Cada nova execução vai para uma pasta nova e resultados antigos nunca são editados.

## Escopo

São práticas de engenharia, não aconselhamento contábil, fiscal ou jurídico. Onde uma regra
depende da jurisdição (arredondamento legal, códigos de imposto, CET, prazos de retenção), a
skill diz isso e mantém a parte de engenharia. Mecânica de API de fornecedor fica com o plugin
do fornecedor: a Stripe tem o dela, a Intuit tem `intuit-developer` e `quickbooks-labs`.

## Como foi feito

Escrito por Felipe Alvarenga a partir de trabalho em produção com crédito, pagamentos e
integrações contábeis no Brasil e nos EUA, redigido e iterado com Claude Code. Os vetores rodam a
cada push. Os evals avaliados rodam antes de cada release, com e sem as skills, e os resultados
ficam em `evals/results/<run-id>/` com os modelos, o sha do git e as transcrições. Skill que não
move os próprios evals em pelo menos 10 pontos é incorporada a outra ou removida; na segunda
execução o menor ganho foi de 20 pontos (money-tests) e o maior de 68 (idempotent-payments).

## Licença

MIT.
