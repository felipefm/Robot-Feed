# Robot Feed

Um vigia pessoal que roda no servidor de casa (CasaOS) e avisa no **Telegram** quando os canais do YouTube que você segue publicam vídeo, entram ao vivo ou **param de publicar**. Junto dele moram alguns módulos auxiliares: resumo de vídeos com IA, um cofre de resumos, garimpo de leilões e um caderno de cifras.

O Robot Feed é o **front + agendador** (Flask, porta `5000`). O trabalho pesado de scraping e IA fica no **Backend FastAPI** (`../Backend.FastAPI`, porta `8000`).

---

## Sumário

- [Monitor YouTube](#monitor-youtube)
- [Resumo de Vídeo, Fila e Cofre](#resumo-de-vídeo-fila-e-cofre)
- [Garimpo de Leilões](#garimpo-de-leilões)
- [Cifras](#cifras)
- [Comandos do Telegram](#comandos-do-telegram)
- [Instalação e deploy](#instalação-e-deploy)
- [Configurações](#configurações)
- [Dependências do Backend](#dependências-do-backend)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Limitações conhecidas](#limitações-conhecidas)
- [Manutenção](#manutenção)

---

## Monitor YouTube

Página inicial (`/`). Objetivo principal: saber o que os canais publicaram e **quais canais pararam**.

### Como a verificação funciona

A cada *N* minutos (configurável) o agendador percorre todos os canais:

1. **Live:** consulta `GET /api/check-live/<channel_id>` no backend, que lê a página `/channel/<id>/live` do YouTube.
2. **Vídeos:** lê o **RSS oficial** do canal (`youtube.com/feeds/videos.xml?channel_id=...`). Ele traz os ~15 envios mais recentes (vídeos, Shorts, lives encerradas e estreias) com título, data e miniatura.
3. **Canal indisponível:** um 404 no RSS só deixa o canal como *suspeito*. A decisão sai no fim da rodada:
   - **Mais da metade dos canais com 404:** é instabilidade do YouTube (já aconteceu por uma madrugada inteira) e nada é contado.
   - **Caso contrário:** cada suspeito é confirmado abrindo a página do canal (`/channel/<id>`). Se a página existir, o 404 é ignorado. O YouTube responde 200 até para canal inexistente, então a resposta é decidida pelo conteúdo da página. Bloqueio ou erro na página é inconclusivo e também não conta.
   - **Confirmado em 3 rodadas seguidas:** o canal é marcado como *Indisponível* (removido, encerrado ou ID alterado). Quando volta a responder, a marca some sozinha.

### Cuidados para não bloquear o IP

O YouTube limita por IP quem acessa demais. Por isso:
- Vídeos vêm **só do RSS oficial**, e live só da página `/live`. A página `/watch`, a mais vigiada, **não é usada**.
- A página do canal só é aberta para confirmar suspeitos de 404, **nunca durante instabilidade geral**. São no máximo **5 por rodada**, com 2 s entre elas, e um canal já marcado como indisponível não é reconferido.

### Sem avisos repetidos

Cada canal guarda os **30 últimos IDs já notificados**. Uma live agendada ou estreia aparece no RSS quando é marcada e, quando acontece, o YouTube atualiza a data e ela volta ao topo do feed. Com o histórico, ela não é avisada de novo como vídeo novo. O aviso de **live** (🔴) continua saindo quando ela entra no ar.

Canais que falham por erro de rede ou da API entram numa fila de **até 3 novas tentativas** na mesma rodada. Depois disso, ficam registrados como `FALHA DEFINITIVA` no log.

### Notificações (Telegram)

| Evento | Mensagem |
|---|---|
| Vídeo novo | 🚨 *Novidade no Canal*, com título, link, miniatura e botão "Assistir" |
| Live nova | 🔴 *ESTÁ AO VIVO*, com link, miniatura e botão |
| Live continua no ar | Lembrete depois do tempo de **repetição de aviso de live** (padrão 120 min) |
| Canal some do YouTube | ⚠️ *Canal indisponível* (uma vez só) |
| Canal volta | ✅ *Canal disponível novamente* |
| Sistema reiniciado | 🤖 *Sistema iniciado e monitorando!* |

Regras de silêncio:
- **Canal silenciado (🔔 global):** não manda nada daquele canal.
- **Live silenciada:** com o canal ao vivo, o botão do sino silencia **só aquela live**. A próxima live avisa normalmente.
- **Modo silencioso (madrugada):** mensagens geradas no horário configurado (ex.: 23:00 às 07:00) vão para uma fila e são entregues quando o horário acaba, com **3 s entre mensagens** (canais do Telegram aceitam cerca de 20 por minuto).
- **Limite do Telegram:** se o Telegram responder `429 Too Many Requests`, o envio espera o tempo pedido (`retry_after`, até 60 s) e reenvia a mesma mensagem, até 3 vezes.
- Para evitar spam, quando o canal é novo ou o RSS perdeu a sincronia (mais de 5 vídeos "novos"), só o mais recente é avisado.

### O dashboard

- **Cards de resumo:** total de canais, ao vivo, silenciados, **parados** (com quantos estão indisponíveis) e contagem regressiva até a próxima verificação.
- **Selos por canal:** `AO VIVO`, `Mudo`, `Live muta`, **`Parado há X meses`** (sem vídeo novo há **90 dias** ou mais) e **`Indisponível`**.
- **Busca e filtros:** busca por nome e filtros Todos / Ao vivo / Silenciados.
- **Ações sem recarregar a página:** silenciar (canal ou live), simular notificação de live (📣) e remover (com confirmação "Remover? Sim/Não").
- **Verificar agora:** dispara uma rodada manual com barra de progresso, que não bloqueia a tela.
- **Logs:** painel com as últimas 100 linhas do log, com opção de modo detalhado (DEBUG).
- **Datas relativas** ("há 3 h"). Passe o mouse para ver a data completa. Clicar na miniatura amplia a imagem.
- **Configurações:** intervalo, repetição de aviso de live, modo silencioso (liga/desliga e horários), Telegram e URL da API. O token do Telegram nunca é enviado para a página: deixe o campo vazio para manter o atual. Os botões **Descobrir** (Chat ID) e **Enviar mensagem de teste** ficam ali também.
- **Backup:** exportar e importar a lista de canais em JSON (`[{"id": "UC...", "title": "Nome"}]`).

O limite de 90 dias para "Parado" fica em `STALE_DAYS`, em `routes/monitor.py`.

### Adicionar canal

Informe `@handle`, ID (`UC...`) ou URL. O sistema consulta `GET /api/get-channel-details/<identificador>` no backend para obter ID e nome. Também registra o vídeo mais recente do RSS para não avisar vídeos antigos no cadastro.

---

## Resumo de Vídeo, Fila e Cofre

- **Resumo de Vídeo (`/resumo`):** cole um link do YouTube (inclusive `/shorts/` e `youtu.be`) e o backend transcreve e resume com IA (`/api/summarize-video`). Também aceita texto livre (`/api/summarize-text`). A tela mostra o resumo, a transcrição, o provedor de IA usado e os tokens consumidos.
- **Fila:** vídeos enviados com `/fila` (Telegram) ou pela tela são processados **um a cada 5 minutos**. Se a API de IA responder 429 (cota esgotada), a fila pausa sozinha, com espera crescente (5, 15, 45 min…). A tela permite acompanhar, pausar, priorizar, remover e processar agora.
- **Cofre (`/cofre`):** todo resumo concluído fica arquivado no banco local, com título, canal, resumo, transcrição, provedor e tokens. Tem busca por palavra-chave, paginação e exclusão. O conteúdo continua disponível mesmo se o vídeo sair do YouTube.

Quais modelos de IA são usados e a ordem de fallback (IA local e provedores em nuvem) são configurados no **Backend FastAPI**, não aqui.

---

## Garimpo de Leilões

Página `/leiloes`: termos de busca, lotes encontrados (com fotos, filtros e ordenação), histórico, estatísticas e exclusão de lotes e termos. Os dias da semana e o horário da varredura automática ficam configurados aqui. A busca nos sites de leilão é feita pelo backend (`auction_api_url`), e o Robot Feed atua como interface e proxy.

---

## Cifras

Página `/cifras`: importa **uma** cifra por vez a partir de uma URL do CifraClub (formato "simplificada"), guarda no banco e exibe com transposição de tom (`cifras_teclado.js`). Não faz varredura do site, só a página informada.

---

## Comandos do Telegram

O bot escuta o chat configurado:

| Comando | O que faz |
|---|---|
| `/resume <URL>` | Resume o vídeo na hora, salva no Cofre e envia a conclusão no chat |
| `/fila <URL>` | Coloca o vídeo na fila de resumos (processada em segundo plano) |
| `/limparplex` | Pede ao backend para apagar do Plex os vídeos já assistidos |
| `/help` ou `/ajuda` | Lista os comandos |

---

## Instalação e deploy

Roda como app do CasaOS via `docker-compose.yml` (container `yt-monitor`, porta `5000`).

```bash
docker compose up -d --build   # primeira vez
```

- **O código é montado no container** (`/DATA/AppData/robot-feed/Robot-Feed → /app`). Para aplicar mudanças em `.py` ou templates, basta **reiniciar**:
  ```bash
  docker restart yt-monitor
  ```
  Só é preciso **rebuild** quando `requirements.txt` mudar.
- **Dados persistentes** em `data/`: `monitor.db` (SQLite) e `robot.log`.
- **Migrações automáticas:** ao iniciar, `utils/database_utils.py` adiciona as colunas novas que faltarem no banco.
- O **Backend FastAPI** precisa estar no ar (container `backend-fastapi`, porta `8000`).

### Primeira configuração

1. Abra `http://<servidor>:5000` → **Configurações**.
2. Preencha o **Token do bot** (BotFather). Envie qualquer mensagem no grupo ou canal e clique em **Descobrir** para achar o **Chat ID**.
3. Ajuste a **URL da API** (ex.: `http://192.168.0.11:8000`).
4. **Salvar** e depois **Enviar mensagem de teste**.
5. Adicione canais ou importe um backup JSON.

---

## Configurações

Ficam na tabela `config` do banco e são editadas pela interface.

| Campo | Padrão | Descrição |
|---|---|---|
| Intervalo de verificação | 30 min | De quanto em quanto tempo o monitor roda |
| Repetir aviso de live | 120 min | Tempo para lembrar de novo de uma live que continua no ar |
| Modo silencioso | desligado | Horário em que as notificações vão para a fila |
| Token / Chat ID | — | Bot e destino no Telegram |
| URL da API YouTube | `http://host.docker.internal:8000` | Backend FastAPI |
| Leilões (página `/leiloes`) | seg–sex 05:00 | Dias, horário e URL do backend de leilões |

---

## Dependências do Backend

Rotas do Backend FastAPI que o Robot Feed usa:

| Rota | Usada por |
|---|---|
| `GET /api/check-live/{id}` | Detecção de live |
| `GET /api/get-channel-details/{identificador}` | Cadastro de canal |
| `POST /api/summarize-video`, `POST /api/summarize-text` | Resumos e fila |
| `/api/auction/*`, `/api/lotes`, `/dominios`, `/stats`, `/lote` | Garimpo de Leilões |
| `DELETE /plex/limpar-assistidos` | Comando `/limparplex` |
| `/docs` | Página "Docs da API" (Swagger embutido) |

---

## Estrutura do projeto

```
Robot-Feed/
├── app.py                 # Inicialização: Flask, agendador, migrações, blueprints, polling do Telegram
├── feed_service.py        # Verificação de canais (live, RSS, canal indisponível) e progresso
├── telegram_bot.py        # Envio de mensagens/fotos, modo silencioso, fila noturna, comandos
├── models.py              # Channel, Config, NotificationQueue, SummaryQueue, VideoArchive, Musica
├── extensions.py          # db (SQLAlchemy) e scheduler (APScheduler)
├── cifras_scraper.py      # Importação de cifras do CifraClub
├── cifras_teclado.js      # Transposição de tom no navegador
├── routes/
│   ├── monitor.py         # Dashboard do YouTube, configurações, backup, logs
│   ├── resumo.py          # Resumo, fila e cofre
│   ├── leiloes.py         # Interface e proxy de leilões
│   └── cifras.py          # Cifras
├── templates/             # index (monitor), resumo, cofre, leiloes, cifras*, docs, navbar
├── utils/                 # Logging, migrações do banco, helpers de URL da API
├── data/                  # monitor.db e robot.log (persistentes)
└── Documentacao/          # Notas históricas da refatoração em blueprints
```

---

## Limitações conhecidas

- **Estreias (Premiere)** aparecem como **vídeo novo**, não como live. A página `/live` do YouTube não as considera transmissões.
- **"Parado"** depende da data do último envio no RSS. Lives encerradas e Shorts contam como publicação.
- O YouTube limita por IP o acesso à página `/watch` (responde 429). Por isso o monitor **não usa** essa página: duração de vídeo e de live não são coletadas.
- Uma live que começa e termina entre duas verificações não é notificada como live. Se virar vídeo no canal, ela chega pelo RSS.

---

## Manutenção

- **Logs:** painel **Logs** no dashboard, `data/robot.log` ou `docker logs yt-monitor`.
- **Quebras de linha:** vários arquivos usam **CRLF**. Ao editar com scripts, preserve as quebras (`newline=''` no Python) para não gerar diffs do arquivo inteiro.
- **Git:** o repositório fica em `/DATA/AppData/robot-feed` (inclui o `Backend.FastAPI`). Se aparecer "dubious ownership", use `git -c safe.directory='*' ...`.
