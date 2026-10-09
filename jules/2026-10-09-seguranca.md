# Relatório de Auditoria de Segurança

Este relatório apresenta a auditoria de segurança realizada no repositório. O objetivo é identificar riscos de vazamento de credenciais, dados pessoais, permissões excessivas e fatores que impedem a abertura pública do código no futuro.

## Achados da Auditoria

### 1. Risco de exposição de tokens e chaves em logs de erro HTTP
* **Arquivo e linha:** `bot.py` (linha 186) e `renovar_token.py` (linhas 11 a 15)
* **Gravidade:** Alta
* **Por que importa:** Quando o aplicativo tenta autenticar na API do Threads e o cabeçalho falha, o parâmetro do token passa a ser enviado na URL da requisição. Se ocorrer um erro de HTTP ou exceção de rede, a URL formatada com a chave pode ser gravada nos logs do GitHub Actions. No arquivo de renovação de token, requisições GET passam segredos pela URL e imprimem a resposta em caso de erro, o que pode expor segredos nos logs de execução.
* **Correção sugerida:** Sanitizar todas as mensagens de erro antes de emitir logs ou levantar exceções. Substituir valores sensíveis por texto oculto, como feito na integração com a Shopee.

### 2. Dados pessoais do proprietário do perfil expostos em arquivos versionados
* **Arquivo e linha:** `state.json` (linha 170), `respostas_log.jsonl` (linhas 441 e 935) e arquivos na pasta `dados/`
* **Gravidade:** Alta
* **Por que importa:** Os arquivos de memória do robô salvam o nome de usuário do perfil do Threads, links diretos para cada publicação realizada e métricas demográficas de seguidores. Isso permite identificar diretamente quem é a pessoa dona da conta e acessar o histórico do seu perfil.
* **Correção sugerida:** Remover o armazenamento do nome do perfil e dos links diretos nos arquivos de dados, ou adicionar todos os arquivos de memória e métricas ao arquivo `.gitignore` para que não sejam commitados no repositório.

### 3. Fatores que impedem tornar o repositório público
* **Arquivo e linha:** `.gitignore` (linhas 1 a 3) e histórico de commits do Git
* **Gravidade:** Alta
* **Por que importa:** O histórico de commits do repositório contém diversos arquivos de memória e relatórios diários de métricas que registram o identificador do perfil real do proprietário. Se o repositório for tornado público no estado atual, qualquer pessoa poderá consultar a identidade do proprietário e dados operacionais históricos.
* **Correção sugerida:** Adicionar os arquivos de estado e métricas (`state.json`, `respostas_log.jsonl`, pasta `dados/`, `inspiracoes_estado.json` e `token_renovado_em.txt`) ao `.gitignore`. Caso o repositório seja tornado público no futuro, será necessário reescrever o histórico de commits do Git para remover essas informações retroativamente.

### 4. Presença de agendamento automático em fluxo de renovação de token
* **Arquivo e linha:** `.github/workflows/renovar-token.yml` (linhas 4 a 5)
* **Gravidade:** Média
* **Por que importa:** O fluxo de trabalho de renovação de token possui um gatilho de agendamento automático via cron. A regra do projeto exige que a execução dos fluxos de trabalho ocorra apenas por disparo manual (`workflow_dispatch`), garantindo maior controle sobre quando os processos são executados.
* **Correção sugerida:** Remover o bloco `schedule` do arquivo `renovar-token.yml`, mantendo apenas o gatilho `workflow_dispatch`.

### 5. Extração de conteúdo de terceiros sem uso de API oficial
* **Arquivo e linha:** `inspiracoes.py` (linhas 74 a 125 e 145 a 185)
* **Gravidade:** Média
* **Por que importa:** O leitor de inspirações realiza requisições diretas e utiliza ferramentas de terceiros para baixar e extrair dados do Instagram, TikTok e Threads sem autenticação por API oficial. Essa prática pode levar ao bloqueio do endereço IP por parte das plataformas e falhas na leitura de links.
* **Correção sugerida:** Adicionar tratamento de exceções para falhas de leitura e avaliar a utilização de APIs oficiais ou fontes alternativas homologadas para obtenção dos dados.

### 6. Execução automatizada de postagens e respostas em volume contínuo
* **Arquivo e linha:** `bot.py` (linhas 112 a 140 e 820 a 910)
* **Gravidade:** Média
* **Por que importa:** O robô realiza postagens e respostas automáticas no Threads ao longo do dia. Mesmo com pausas aleatórias e limites por rodada, volumes elevados de interações automatizadas podem ser sinalizados pelos sistemas de segurança da Meta como comportamento automatizado indevido, gerando risco de bloqueio ou suspensão do perfil.
* **Correção sugerida:** Manter limites de respostas e postagens em patamares conservadores, revisar periodicamente os parâmetros de pausa e monitorar eventuais avisos de limite por parte da API.

### 7. Permissão global de escrita atribuída ao fluxo do robô
* **Arquivo e linha:** `.github/workflows/robo.yml` (linhas 15 a 16)
* **Gravidade:** Baixa
* **Por que importa:** O job do robô define a permissão `contents: write` em nível global para todas as suas etapas. Aplicar o princípio do menor privilégio garante que permissões de escrita sejam concedidas apenas na etapa que realmente grava dados.
* **Correção sugerida:** Restringir a permissão global para leitura (`contents: read`) e atribuir a permissão de escrita apenas à etapa encarregada de salvar a memória do robô.

## Resumo dos Achados

| Item | Arquivo e Linha | Gravidade | Descrição Resumida |
|---|---|---|---|
| 1 | `bot.py` (186) e `renovar_token.py` (11-15) | Alta | Risco de vazamento de token em logs de erro HTTP |
| 2 | `state.json` (170), `respostas_log.jsonl` (441, 935), `dados/*.json` | Alta | Exposição do identificador do perfil real e links de posts |
| 3 | `.gitignore` (1-3) e histórico Git | Alta | Histórico com dados pessoais impede tornar o código público |
| 4 | `.github/workflows/renovar-token.yml` (4-5) | Média | Presença de gatilho agendado (cron) em vez de apenas manual |
| 5 | `inspiracoes.py` (74-125, 145-185) | Média | Extração de páginas de terceiros sem API oficial |
| 6 | `bot.py` (112-140, 820-910) | Média | Risco de restrição na Meta por automação frequente |
| 7 | `.github/workflows/robo.yml` (15-16) | Baixa | Permissão de escrita ampla no escopo do job |
