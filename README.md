# robo-threads

Robô que posta e responde comentários no Threads usando só a API oficial da Meta.

## O que ele faz
- Posta várias vezes por dia em horários sorteados (no fuso da Variable `FUSO`), com texto escrito pela IA a partir dos ganchos da planilha.
- Responde comentários dos próprios posts no jeito da persona, com limites por rodada, por dia e por pessoa.
- Não responde comentário que o dono já respondeu à mão. As respostas manuais viram exemplos para a IA.
- Esconde (não apaga) spam e golpe.
- Guarda estatísticas dos posts uma vez por dia.
- Lê links de inspiração e ideias de melhoria salvos no app e resume com o Gemini.

IAs: Gemini como principal. Groq e OpenRouter (modelos grátis) como reserva.

## Como roda
- Workflow `.github/workflows/robo.yml`, disparado a cada 30 min por um despertador externo (cron-job.org).
- Cada rodada salva a memória do robô na branch `main` (commit "memoria do robo").
- O token do Threads se renova sozinho (passo no `robo.yml` e, como reserva, `renovar-token.yml`).

## Arquivos
| Arquivo | Para que serve |
|---|---|
| `bot.py` | Robô principal (postar, responder, estatísticas) |
| `inspiracoes.py` | Leitor de inspirações e ideias de melhoria |
| `renovar_token.py` | Renova o token de 60 dias do Threads |
| `state.json` | Memória do robô (plano do dia, posts, respondidos) |
| `respostas_log.jsonl` | Diário das respostas, sem nome de ninguém |
| `inspiracoes_lidas.md`, `melhorias_lidas.md` | Resumos feitos pelo Gemini |

Os arquivos de memória são escritos pelo robô. Não editar à mão.

## Configuração (Settings > Secrets and variables > Actions)
- **Secrets:** `THREADS_TOKEN`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GH_PAT`, `THREADS_APP_SECRET`.
- **Variables:** `PLANILHA_URL` é obrigatória. As demais (quantidade de posts, horários, limites, persona) são opcionais. Sem elas vale o dicionário `PADRAO` no começo do `bot.py`.

## Botões úteis (Variables)
- `PAUSADO=1`: o robô não faz nada.
- `MODO_TESTE=1`: só mostra no log o que publicaria.
- `FUSO`: fuso dos horários do robô (padrão `America/Manaus`).
- `PERSONA_RESPOSTA`: personalidade das respostas. Sem ela, vale um texto genérico do código.
