# Instruções para o Jules (e qualquer agente de código)

Leia este arquivo inteiro antes de qualquer tarefa neste repositório. Ele vale junto com o `CLAUDE.md` e o `README.md`.

## Como o trabalho funciona aqui
- Você recebe tarefas por issue com a etiqueta `jules`. Faça só o que a issue pede, nada a mais.
- Toda entrega é revisada pelo Claude. PR que mexe em `publicar`, `criar_resposta`, `publicar_resposta`, `tarefa_postar`, `tarefa_responder`, `.github/workflows/` ou uso de secrets só entra com o merge do dono.
- **Nunca desfaça, reverta ou sobrescreva commits de outra pessoa na sua branch.** Se o Claude ou o dono commitou na branch do seu PR, aquele código é o que vale. Não reenvie a sua versão antiga.
- Se pedirem ajuste em comentário do PR, aplique o ajuste de verdade num commit novo. Se não conseguir, responda no PR dizendo o que faltou. Nunca reenvie o mesmo código como se fosse o ajuste.
- Um PR por tarefa. Só os arquivos que a tarefa pede. Nunca deixe arquivos temporários (scripts de teste, saídas, rascunhos) no commit.
- Antes de afirmar que algo falta ou está errado, confira no código. Não exagere a gravidade.

## Regras do robô
- Só API oficial da Meta. Nada de curtir, seguir, mandar DM ou comentar em post de outras pessoas.
- O robô roda na branch `main` e commita a própria memória (`state.json`, `respostas_log.jsonl`, `inspiracoes_estado.json`, `token_renovado_em.txt`, pasta `dados/`). **Nunca edite esses arquivos.**
- Números de configuração ficam só no dicionário `PADRAO` do `bot.py` (ou nas Variables do GitHub). Nunca fixos no meio do código.
- Funcionalidade nova chega desligada por uma chave no `PADRAO`.
- Qualquer falha de serviço externo (Shopee, IA, Apify) vira só log: nunca derruba a rodada.
- Minutos do GitHub Actions são contados: nada de `sleep` longo nem passo que deixe a rodada mais lenta.
- `shopee.py` não importa o `bot.py` (o bot roda como `__main__`); passe o que precisar por parâmetro.

## Segurança e anonimato
- Nunca escreva, mostre ou commite senhas, tokens ou chaves, nem em log ou relatório.
- Nenhum nome real ou dado pessoal do dono em código, log, commit ou relatório.

## Antes de entregar
- Rode `python -m py_compile` em todo `.py` alterado.
- Textos e relatórios em português do Brasil, linguagem simples, sem travessões.

## Pastas suas
- `jules/diario/AAAA-MM-DD.md`: relatório diário.
- `jules/seguranca/AAAA-MM-DD.md`: relatório semanal de segurança.
- `jules/fila/fio-*.json`: fios da estratégia 3 (só crie arquivos novos; quem marca `"aprovado": true` é o Claude). Formato: `id`, `aprovado`, `partes` (3 a 5 itens com `texto`, `midia` "produto" ou "nenhuma", `link` true/false) e `produto` (`itemId`, `imageUrl`, `offerLink`).
