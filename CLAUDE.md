# Regras do projeto robo-threads

## Segurança
- Nunca escrever, mostrar ou commitar senhas, tokens ou chaves. Elas ficam só nos Secrets do GitHub.
- Nenhum nome real ou dado pessoal do dono em código novo, logs ou commits.

## Robô
- Não mudar a lógica de publicação no Threads (`publicar`, `criar_resposta`, `publicar_resposta`, `tarefa_postar`, `tarefa_responder`) sem explicar antes e pedir confirmação.
- Só API oficial da Meta. Nada de curtir, seguir ou DM automático.
- O robô roda na branch `main` e commita a própria memória (`state.json`, `respostas_log.jsonl` e outros). Não editar esses arquivos à mão.

## GitHub Actions
- Economizar minutos: não disparar rodadas manuais sem pedir.
- Toda rodada é cobrada arredondando para cima por minuto. Evitar passos ou esperas que empurrem a rodada para o minuto seguinte.

## Antes de cada commit
- Rodar `python -m py_compile bot.py` (e os outros `.py` alterados).
- Mostrar o diff resumido.

## Comunicação
- Português simples e direto, sem travessões.
