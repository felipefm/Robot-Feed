# Robot Feed: O Vigia Silencioso (YouTube & Leilões)

## A Essência

Em um mundo digital onde o fluxo de informações é incessante, o **Robot Feed** nasce como um guardião pessoal. Ele é uma ferramenta desenhada para libertar você da necessidade de verificar constantemente se seus criadores de conteúdo favoritos publicaram algo novo.

Imagine um assistente incansável que habita o seu servidor (como um Raspberry Pi), observando o horizonte digital dia e noite. Ele não dorme, não se cansa e não se distrai. Sua missão é garantir que você seja o primeiro a saber quando uma nova história, um novo vídeo ou uma oportunidade de leilão surgir.

## O Que Ele Faz?

Esta ferramenta opera nas sombras, de forma leve e eficiente, realizando seis grandes feitos:

### 1. A Vigília Constante
Você entrega a ele uma lista de canais do YouTube que deseja acompanhar. A partir desse momento, o Robot Feed passa a visitar periodicamente a "porta" desses canais (através de seus sinais RSS). Ele verifica se há algo inédito, seja um vídeo recém-lançado ou uma Live agendada para o futuro.

### 2. A Memória Seletiva
Para não ser inoportuno, o sistema possui uma memória própria. Ele sabe exatamente qual foi o último vídeo que ele já lhe avisou. Assim, ele evita repetições desnecessárias, quebrando o silêncio apenas quando há, de fato, uma novidade genuína.

**Novidade (Smart Live):** Para transmissões ao vivo, implementamos um sistema de **Resfriamento (Cooldown)**. Se um canal ficar ao vivo por muitas horas, o robô não ficará enviando avisos repetidos a cada verificação. Ele respeitará um intervalo configurável (ex: avisar novamente só após 2 horas), mantendo você informado sem spam.

### 3. O Mensageiro Veloz
Assim que uma novidade é detectada, o Robot Feed aciona seu mecanismo de entrega. Ele viaja através da rede do **Telegram** e envia uma notificação direta para o seu celular. A mensagem chega com o título, o nome do canal e o link direto, pronta para ser consumida.

### 4. O Diagnóstico e Controle
Para os momentos de curiosidade ou manutenção, o sistema oferece ferramentas poderosas:
*   **Terminal de Logs:** Um visualizador estilo retrô para acompanhar o funcionamento em tempo real.
*   **Simulação de Live:** Um botão "Megafone" 📢 para testar se a notificação de um canal específico está chegando corretamente.
*   **Descobridor de IDs:** Uma ferramenta para ajudar a encontrar o Chat ID correto de grupos e canais do Telegram.

### 5. Backup e Portabilidade
Sua curadoria de canais é valiosa. O sistema agora permite **Exportar** sua lista para um arquivo JSON e **Importar** listas prontas (compatível com formatos de mosaico), facilitando backups e migrações.

### 6. O Garimpo de Leilões
Expandindo seus horizontes, o Robot Feed agora possui um módulo dedicado a encontrar oportunidades.
*   **Busca Ativa:** Defina termos (ex: "iPhone", "Relógio") e o sistema varre sites de leilão em busca de lotes.
*   **Agendamento:** Configure dias da semana e horários específicos para a varredura automática.
*   **Gestão Visual:** Uma interface dedicada para filtrar, ordenar e visualizar fotos dos lotes encontrados, com histórico persistente.

### 7. Resumo Inteligente de Vídeos
Através de uma nova integração com IA (Gemini Flash), o assistente agora consegue extrair a essência de qualquer vídeo.
*   **Extração e Leitura:** Cole o link de um vídeo do YouTube e receba um resumo ricamente formatado, pronto para leitura direta na tela.
*   **Transcrição Completa:** Acesse todo o diálogo capturado em um painel expansível ("acordeão").
*   **Transparência de Custos:** Veja em tempo real a quantidade de tokens consumida e o custo estimado daquela operação.
*   **Notificações Cirúrgicas no Telegram:** Ao concluir o resumo via comandos, o bot não "spamma" um texto gigante. Ele identifica e recorta magicamente apenas a "Conclusão" do vídeo e envia direto no seu chat.
*   **Cópia Ágil:** Botão inteligente com sistema anti-bloqueio que copia o texto Markdown original limpo para colar no seu bloco de anotações (Notion, Obsidian, etc.).
*   **Comandos via Telegram:** Envie `/resume <URL>` diretamente no chat do Telegram. O robô processará o vídeo, salvará automaticamente no seu Cofre e enviará a conclusão do resumo direto na sua conversa!
*   **Fila de Processamento Automático:** Para não estourar os limites gratuitos da IA, coloque vídeos em fila usando `/fila <URL>` no Telegram. Um "trabalhador" invisível resume um vídeo a cada 5 minutos e te notifica quando estiver pronto.
*   **Freio Inteligente (Backoff):** A fila conta com um sistema ABS. Se a API estourar o limite de cota (Erro 429), a fila pausa sozinha e multiplica o tempo de espera progressivamente (5, 15, 45 min...) para proteger e recuperar sua conexão.
*   **Gerenciamento Visual da Fila:** A página de resumos web agora exibe um painel dinâmico e uma tabela interativa para você acompanhar em tempo real, visualizar, pausar, priorizar ou remover vídeos da fila de processamento.
*   **Suporte ao YouTube Shorts:** Agora o assistente também extrai IDs e entende perfeitamente os links de vídeos curtos (`/shorts/`).
 
### 8. O Cofre de Conhecimento
A internet é volátil, mas o seu conhecimento não precisa ser. O Robot Feed agora atua como um arquivista pessoal.
*   **Anti-Exclusão (Backup offline):** Ao solicitar o resumo de um vídeo, os dados são automaticamente salvos no seu banco de dados local. Se o vídeo original for apagado ou colocado como privado no YouTube, a essência e a transcrição continuam suas para sempre.
*   **Busca Profunda:** Uma interface dedicada ("Cofre") permite buscar palavras-chave em todos os resumos e títulos já arquivados. Lembra que viu uma dica valiosa, mas esqueceu o canal? O cofre varre os textos e encontra para você.
*   **Base Pronta para o Futuro:** O armazenamento dessas transcrições cria a fundação perfeita para, futuramente, integrar uma IA local (RAG) que responda perguntas baseada exclusivamente no seu próprio catálogo de vídeos.
*   **Navegação e Paginação:** Interface otimizada para lidar com centenas de resumos simultâneos, com paginação fluida e indicadores de contagem exatos.
*   **Arquivamento Unificado:** Motor interno arquitetado através de uma "Ponte de Dados" centralizada. Garante que os registros nunca sejam duplicados, preservando qual IA (Provedor) gerou o resumo e quantos tokens foram gastos.
*   **Limpeza do Cofre:** Adicionou algo por engano? Cada item arquivado agora possui um botão para exclusão segura direto da interface, limpando sua base de dados facilmente.

### 9. Inteligência Híbrida e Soberania Digital (Novo!)
O Robot Feed agora não depende apenas da nuvem. Ele evoluiu para um sistema de inteligência distribuída que prioriza a sua privacidade e o seu hardware local.

 *  **InteligRoteamento Inteligente (Multi-LLM):** O sistema tornou-se um maestro de modelos. Ele tenta, em primeira instância, resolver o resumo usando o seu próprio hardware. Se o seu servidor local estiver offline, ele aciona inteligentemente as camadas de reserva (Gemini ou Mistral), garantindo que nenhum vídeo fique sem resposta.

*   **HardwareCérebro Local (LM Studio & GPU):** Através da integração com o LM Studio, o robô agora desperta o poder da sua placa de vídeo (GPU). Ele utiliza modelos de ponta, como o Qwen 2.5 14B, para processar tudo dentro da sua própria rede, sem que seus dados saiam de casa.

*   **Memória de Contexto Expandida:** Diferente das limitações de versões gratuitas, o seu nó local foi configurado para "ler" janelas imensas de texto (até 54k tokens), permitindo resumos profundos de vídeos longos sem perder nenhum detalhe.

*   **Supelo de Autoria:** Transparência total no processamento. Cada resumo no seu Cofre agora exibe orgulhosamente qual "entidade" trabalhou nele — seja o seu LM Studio local ou um provedor na nuvem.

*   **Economia Real (FinOps):** Ao processar resumos localmente na sua GPU de 16GB, você elimina custos de API e contorna limites de cota, transformando seu investimento em hardware em uma usina de conhecimento gratuita e ilimitada.

## Como Você Interage com Ele?

Embora ele trabalhe nos bastidores, o Robot Feed possui um rosto amigável e agora mais inteligente:

*   **Navegação Unificada:** Alterne facilmente entre o "Monitor YouTube", "Cofre", "Garimpo de Leilões", "Resumo de Vídeo" e "Docs da API" através da barra de navegação.
*   **Documentação Embutida:** Acesse o painel interativo (Swagger) do backend perfeitamente integrado à interface principal.
*   **O Painel de Controle:** Uma interface web simples e elegante onde você pode visualizar quem está sendo monitorado.
*   **Interface Limpa:** A seção de configurações agora é retrátil (acordeão), mantendo o foco no que importa: seus canais.
*   **Gestão Inteligente:** Esqueça a necessidade de procurar IDs complexos de canais (`UC...`). Agora, basta informar o **identificador** (ex: `@CanalTech` ou a URL), e o sistema consulta sua API local para preencher os dados automaticamente.
*   **O Maestro do Tempo:** Você decide o ritmo. Configure o intervalo de verificação e o tempo de espera para repetição de avisos de Live.
*   **Ouvinte de Comandos:** O bot agora escuta ativamente o seu Telegram. Você não precisa sequer abrir a interface web para resumir um vídeo; basta conversar com ele.
*   **Feedback Imediato:** Assim que o sistema acorda (reinicia), ele envia uma mensagem ao seu Telegram avisando que está online e monitorando.

## Por Que Usar?

Para não depender dos algoritmos incertos das redes sociais ou dos "sininhos" que nem sempre tocam. O Robot Feed devolve a você o controle sobre o que você consome, garantindo que o conteúdo que você ama chegue até você, e não o contrário.

---

### Resumo Técnico (Para os Curiosos)

Embora a alma do projeto seja literária, seu corpo é construído com tecnologia sólida:

*   **Coração:** Python.
*   **Corpo:** Docker (perfeito para CasaOS).
*   **Interface:** Flask (Web).
*   **Memória:** SQLite.
*   **Voz:** API do Telegram.
*   **Olhos:** Feedparser (RSS).
*   **Inteligência:** Integração com API externa (FastAPI) para resolução de metadados de canais.
*   **Logs:** Sistema de arquivos persistente com visualizador web em tempo real.
*   **Motor de IA Local:** LM Studio (Interface OpenAI Compatible).
*   **Aceleração:** Suporte a GPU via Vulkan/ROCm (Otimizado para AMD Radeon).
*   **Modelos Suportados:** Qwen 2.5, Mistral, Gemini Flash.


*Este projeto foi criado para rodar silenciosamente no seu lar digital.*