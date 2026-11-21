from google import genai
from google.genai import types
from app.config import ALLOWED_ZONES, CUTOFF_HOUR, DAILY_META_BRL, GEMINI_API_KEY
from app.models import DayState

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = f"""
Você é um assistente operacional de rotas para motorista de aplicativo no Rio de Janeiro.
Regras obrigatórias:
1. Considere APENAS estas 4 zonas: {", ".join(ALLOWED_ZONES)}. Ignore outras zonas no foco principal.
2. Meta diária fixa: R$ {DAILY_META_BRL:.2f}, com teto até {CUTOFF_HOUR}.
3. Seja direto, prático e escaneável (máximo de 4 a 5 linhas com tópicos curtos).
4. Use sempre os nomes exatos das 4 zonas quando citar o circuito.
5. Nunca invente dados que não estejam no gráfico ou no estado informado; quando o gráfico não tiver sido enviado ainda, baseie-se no estado atual e nas janelas típicas das 4 zonas sem afirmar leitura visual inexistente.
"""


def generate_initial_plan(state: DayState, now_str: str) -> str:
    prompt = f"""
Hora atual: {now_str}. Meta: R$ {state.meta_brl:.2f} até {CUTOFF_HOUR}.
Analise o print de Tendências de Ganhos enviado e gere o ROTEIRO INICIAL DO DIA.
Inclua:
- Foco inicial (manhã/início) entre as 4 zonas.
- Janela sugerida de almoço (vale de demanda) e horário de retorno (subida antes do pico).
- Sequência tarde/noite e transições entre as 4 zonas até bater R$ {state.meta_brl:.2f}.

Formato exato:
**Plano do Dia — Meta: R$ {state.meta_brl:.2f}**
* **Manhã / Início:** ...
* **Almoço e Retorno:** ...
* **Tarde / Noite:** ...
* **Fechamento:** ...
"""
    contents = []
    if state.chart_image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=state.chart_image_bytes,
                mime_type=state.chart_mime_type,
            )
        )
    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
    )
    return (response.text or "").strip()


def generate_recalculation(
    state: DayState,
    now_str: str,
    remaining_brl: float,
    hours_left: float,
    needed_per_hour: float,
) -> str:
    prompt = f"""
Hora de referência: {now_str} (horas restantes até o fim do dia: {hours_left:.1f}h).
Valor acumulado: R$ {state.current_amount_brl:.2f} | Meta: R$ {state.meta_brl:.2f} | Falta: R$ {remaining_brl:.2f}.
Média necessária: R$ {needed_per_hour:.2f}/h.
Zona atual: {state.current_zone}.

Gere o RECÁLCULO RÁPIDO considerando o gráfico do dia (se anexado) e a posição atual.
Formato exato (máximo 4 linhas):
**Ajuste de Rota — Faltam R$ {remaining_brl:.2f}**
* **Ritmo:** [Adiantado / Na linha / Exigindo mais giro] — média necessária de R$ {needed_per_hour:.2f}/h até {CUTOFF_HOUR}.
* **Agora ({state.current_zone}):** ...
* **Próximo passo:** ...
"""
    contents = []
    if state.chart_image_bytes:
        contents.append(
            types.Part.from_bytes(
                data=state.chart_image_bytes,
                mime_type=state.chart_mime_type,
            )
        )
    contents.append(prompt)

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.2,
        ),
    )
    return (response.text or "").strip()