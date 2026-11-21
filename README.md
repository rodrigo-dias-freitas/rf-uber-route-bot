# 🚘 RF Uber Route Bot — Tactical Ride-Share Optimizer & Daily Goal Radar (v1.0.0)

O **RF Uber Route Bot** é um co-piloto operacional via Telegram desenvolvido para otimizar rotas, turnos e pausas estratégicas de motoristas de aplicativo no **Rio de Janeiro**, com foco no atingimento de metas financeiras diárias (**R$ 550,00** até às **00:00**).

Projetado sob a arquitetura de *Decision Support System* (DSS), o agente utiliza **Visão Computacional (Gemini AI)** para interpretar capturas de tela dos gráficos de *Tendências de Ganhos* da Uber, cruzando picos de demanda, janelas de vale (almoço/descanso) e geografia urbana restrita às zonas de maior rentabilidade, mantendo a decisão final de aceite de corridas sob controle total do motorista.

---

## 🎯 Arquitetura & Filosofia (v1.0.0)

O sistema foi desenhado para eliminar deslocamentos vazios e maximizar o ganho por hora dentro da realidade operacional do Rio de Janeiro:

1. **Geografia Restrita (4 Zonas Estratégicas):** Toda a análise e sugestão de posicionamento concentra-se exclusivamente no eixo **Zona Norte / Jacarepaguá**, **Zona Sul**, **Tijuca** e **Centro**.
2. **Leitura Multimodal de Demanda:** Interpretação automatizada do gráfico diário de barras (*Tendências de Ganhos*) para identificar horários de pico máximo e vales de baixa procura.
3. **Gestão de Turnos e Janela de Almoço:** Indicação precisa do melhor horário de pausa (vale de demanda) e do momento exato de retorno antes da curva de subida da tarde/noite.
4. **Recálculo Dinâmico em Tempo Real:** Atualização instantânea do saldo restante, ritmo horário necessário (`R$/h`) e próximo deslocamento tático a partir de comandos curtos enviados entre corridas.

---

## 🖥️ Setup Operacional Recomendado

Para extrair o máximo desempenho do bot durante a operação diária:

- **Abertura do Turno (Print Inicial):** Enviar a captura de tela do gráfico de *Tendências de Ganhos* do dia para gerar o roteiro macro e a janela de almoço.
- **Atualizações Rápidas (Status):** Enviar mensagens curtas no formato `<valor_acumulado> <zona_atual> [hora_opcional]` (ex.: `377,84 copacabana` ou `170,46 rio sul 13:15`).
- **Fechamento & Reset:** Utilização do comando `/reset` ao iniciar um novo ciclo diário para zerar o estado da sessão.

---

## 📱 Formato de Saída (Telegram)


### Plano Inicial (após envio do print)

**Plano do Dia — Meta: R$ 550.00**
* **Manhã / Início:** Focar no eixo Tijuca e Centro aproveitando o fluxo matinal até a estabilização da demanda.
* **Almoço e Retorno:** Pausa programada no vale entre 13h00 e 15h30, com retorno posicionado na Zona Sul antes da subida das 16h00.
* **Tarde / Noite:** Operar no pico máximo da Zona Sul (18h00 às 23h00), aproveitando puxadas para Centro e Tijuca.
* **Fechamento:** Manter giro curto entre Zona Sul, Centro e Tijuca até consolidar a meta antes das 00h00.

Recálculo Rápido (após envio de status)
**Ajuste de Rota — Faltam R$ 172.16**
* **Ritmo:** Adiantado — média necessária de R$ 42.14/h até 00:00.
* **Agora (Zona Sul):** Região em patamar máximo de demanda noturna; evite deslocamentos longos para fora do eixo.
* **Próximo passo:** Priorizar corridas curtas e médias entre Zona Sul, Centro e Tijuca até fechar a meta.


---

## 🛠️ Tecnologias Utilizadas
* **Linguagem:** Python 3.12+
* **Visão Computacional & IA:** Google GenAI SDK (gemini-2.5-flash)
* **Interface & Mensageria:** python-telegram-bot (Telegram Bot API)
* **Gestão de Ambiente & Fuso Horário:** python-dotenv, zoneinfo / tzdata
* **Versionamento:** Git / GitHub


## 🚀 Como Rodar o Projeto
**Clonar o Repositório:**

```text
git clone [https://github.com/rodrigofreitas-dev/rf-uber-route-bot.git](https://github.com/rodrigofreitas-devrf-uber-route-bot.git)
cd rf-uber-route-bot

```
**Configurar o Ambiente Virtual & Dependências:**

```text
python -m venv venv
source venv/bin/activate  # Linux/Mac ou venv\Scripts\activate no Windows
pip install -r requirements.txt
```

**Variáveis de Ambiente (.env):**

```text
GEMINI_API_KEY=sua_chave_gemini
TELEGRAM_BOT_TOKEN=seu_token_telegram
TELEGRAM_CHAT_ID=seu_chat_id
```

**Executar o Bot:**

```text
python -m app.bot
```

Desenvolvido por Rodrigo Freitas — UI/UX Designer, Frontend Developer & Financial Consultant.
