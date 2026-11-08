# fintech-skills

Skills de engenharia fintech para agentes de código. Doze skills que ensinam Claude Code, Codex,
Cursor, Copilot e qualquer agente que leia `SKILL.md` a tratar dinheiro como sistemas fintech de
produção tratam. Toda skill vem com um eval. As numéricas vêm com vetores de teste que rodam no CI.

[English](README.md)

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

| Skill | Use quando | Vetores |
|---|---|---|
| [money-arithmetic](skills/money-arithmetic/SKILL.md) | Guardar, somar, ratear, converter, arredondar ou formatar valores | sim |
| [double-entry-ledger](skills/double-entry-ledger/SKILL.md) | Qualquer tabela que responde "quanto X tem ou deve" | sim |
| [idempotent-payments](skills/idempotent-payments/SKILL.md) | Criar, capturar, estornar ou pagar; chamar um processador | |
| [webhook-handling](skills/webhook-handling/SKILL.md) | Receber callbacks de processadores, bancos e PSPs | |
| [reconciliation](skills/reconciliation/SKILL.md) | Conciliar ledger, relatório do processador e extrato bancário | sim |
| [accounting-sync](skills/accounting-sync/SKILL.md) | Integrar com QuickBooks, Xero, NetSuite, Omie, Conta Azul | |
| [transaction-classification](skills/transaction-classification/SKILL.md) | Categorizar transações com regras, ML ou LLM, em especial com lançamento automático | |
| [pii-and-card-data](skills/pii-and-card-data/SKILL.md) | Coletar, logar, exibir ou exportar dados pessoais, bancários ou de cartão | |
| [audit-trail](skills/audit-trail/SKILL.md) | Qualquer mutação de dinheiro, limites, permissões ou dados de cliente; ações de agentes | |
| [interest-and-amortization](skills/interest-and-amortization/SKILL.md) | Juros, parcelas, tabelas Price e SAC, provisões, taxa efetiva | sim |
| [brazil-payment-rails](skills/brazil-payment-rails/SKILL.md) | Pix, boleto, parcelamento no cartão, CPF e CNPJ, NF-e | |
| [money-tests](skills/money-tests/SKILL.md) | Escrever ou revisar testes para qualquer item acima | |

## Evals

Toda skill tem `evals/evals.json` no formato do `skill-creator` da Anthropic: prompts que um
agente receberia e expectativas que um avaliador confere na transcrição. Quatro skills também têm
vetores: arquivos pytest com uma implementação de referência, executáveis contra o seu código
por uma variável de ambiente. Veja [evals/README.md](evals/README.md).

Execute avaliações com e sem a skill com `python3 scripts/run_evals.py --skill money-arithmetic`.
Para todas as skills, use `--all --budget 144`; o limite padrão é 80 sessões, incluindo avaliadores.
Use `--agent fake` para exercitar o runner sem modelo. Evals reais nunca rodam no CI.

## Escopo

São práticas de engenharia, não aconselhamento contábil, fiscal ou jurídico. Onde uma regra
depende da jurisdição (arredondamento legal, códigos de imposto, CET, prazos de retenção), a
skill diz isso e mantém a parte de engenharia. Mecânica de API de fornecedor fica com o plugin
do fornecedor: a Stripe tem o dela, a Intuit tem `intuit-developer` e `quickbooks-labs`.

## Como foi feito

Escrito por Felipe Alvarenga a partir de trabalho em produção com crédito, pagamentos e
integrações contábeis no Brasil e nos EUA, redigido e iterado com Claude Code. Cada regra entrou
porque a ausência dela causou um incidente ou um fechamento de mês real.

## Licença

MIT.
