# Status do robô

Valores padrão ficam só no `PADRAO` do `bot.py`. A Variable do GitHub com o mesmo nome manda mais que o padrão.
Toda mudança de regra é feita no mesmo commit em: Variable (se usada), `PADRAO`, `robo.yml` e este arquivo.
O log mostra 1 vez por dia a linha "Config em uso" com os valores valendo de verdade.

## Respostas (mudança de 05/10/2026)
- Teto do dia dividido pelas rodadas que faltam até `HORA_FIM`: cota da rodada = restante do dia ÷ rodadas restantes, com piso `RESPOSTAS_MIN_RODADA` e teto `RESPOSTAS_POR_RODADA`.
- Depois de `HORA_FIM`, a sobra do dia fica liberada, sempre respeitando o teto por rodada.
- Teto por post no dia: `RESPOSTAS_POR_POST_DIA`.
- Ordem: um comentário por vez, sempre do post com menos respostas no dia. No empate, vai o post mais novo.
- Sem mudança: `RESPOSTAS_POR_DIA`, `RESPOSTAS_POR_RODADA`, `RESPOSTAS_POR_PESSOA` e as pausas.
- Qualidade:
  - não repete as 3 primeiras palavras dentro do mesmo post, nem entre rodadas;
  - a lista de correção de acentos ficou maior;
  - filtro de vícios de IA ("não é sobre X, é sobre Y" e parecidos).

## Posts (mudança de 05/10/2026)
- Prefixo de pergunta (DÚVIDA SINCERA, SEJAM SINCEROS, ME CONTA) só entra em post que pergunta de verdade.
- Se o texto sair sem "?", a IA lê o post e escolhe o prefixo que encaixa no sentido (VAMOS CONCORDAR, VAMOS SER HONESTOS, NINGUÉM FALA DISSO, OPINIÃO IMPOPULAR) ou nenhum. Se a IA falhar, o prefixo some. No log aparece "Prefixo corrigido".
- Post com "literal" na observação não passa por essa troca.

## Pasta dados/ (mudança de 05/10/2026)
- 1 vez por dia, na primeira rodada, grava `dados/AAAA-MM-DD.json` com:
  - perfil de 1 dia e de `METRICAS_DIAS` dias, mais seguidores;
  - público agregado por idade, gênero, país e cidade (a Meta só libera com muitos seguidores);
  - todos os posts do período, marcando se foram do robô, com as métricas.
- Guarda `DADOS_DIAS` dias. Não grava dado pessoal de terceiros.
- Se falhar, a rodada segue normal.

## Variables novas (opcionais; vazias = PADRAO)
`RESPOSTAS_POR_POST_DIA`, `RESPOSTAS_MIN_RODADA`, `MINUTOS_ENTRE_RODADAS`, `DADOS_DIAS`.

## Horários perdidos por falha do GitHub (mudança de 05/10/2026)
- Se várias rodadas falharem, o robô posta só 1 na rodada seguinte (como antes).
- Os horários muito atrasados não são mais descartados. Cada um ganha um novo horário sorteado entre agora + `INTERVALO_MINIMO_MIN` e `HORA_FIM`, longe dos outros horários do dia. No log aparece "Horario X reencaixado para Y".
- Só é descartado se não couber mais no dia. No log aparece "Post perdido (sem espaco no dia)".
- Comentários não mudam: o que ficou sem resposta durante a falha entra nas rodadas seguintes, dentro do teto do dia.
