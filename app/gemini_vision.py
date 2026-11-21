import json
from google import genai
from google.genai import types
from app.config import ALLOWED_ZONES, GEMINI_API_KEY
from app.models import CUTOFF_DEFAULT, META_DEFAULT, DayState, filter_allowed_zones

MODEL_NAME = "gemini-3.8-flash"

client = genai.Client(api_key=GEMINI_API_KEY)


def _build_system_instruction(state: DayState) -> str:
    meta = float(state.meta_brl or META_DEFAULT)
    zones_str = ", ".join(state.active_zones or ALLOWED_ZONES)
    cutoff = state.cutoff_hour or CUTOFF_DEFAULT
    start_info = f"Início previsto a partir de {state.start_after_str}." if state.start_after_str else ""
    notes_info = f"Observações do dia: {state.day_notes}." if state.day_notes else ""

    return f"""
Você é um assistente operacional de rotas para motorista de aplicativo no Rio de Janeiro.
Regras obrigatórias:
1. Priorize e restrinja o circuito às regiões ativas do dia: {zones_str}. Evite sugerir deslocamentos para fora dessas regiões, exceto se necessário para retorno ao circuito ativo.
2. Meta do dia: R$ {meta:.2f}, com horário de parada/teto às {cutoff}. {start_info} {notes_info}
3. Seja direto, prático e escaneável (máximo de 4 a 5 linhas com tópicos curtos).
4. Use sempre os nomes exatos das zonas quando citar o circuito.
5. Nunca invente dados que não estejam no gráfico ou no estado informado; quando o gráfico não tiver sido enviado ainda, baseie-se no estado atual e nas janelas típicas das regiões ativas sem afirmar leitura visual inexistente.
"""


def interpret_free_message(state: DayState, text: str, now_str: str) -> dict:
    """
    Interpreta mensagens livres do motorista para extrair alterações de:
    - valor acumulado / zona atual / horário de referência
    - meta do dia
    - regiões ativas (inclusões ou exclusões sobre as 4 zonas oficiais)
    - horário em que começa a rodar (start_after_str)
    - horário em que pretende parar (cutoff_hour)
    - observações do dia (ex.: jogo, chuva, trânsito)
    """
    allowed_str = ", ".join(ALLOWED_ZONES)
    current_zones_str = ", ".join(state.active_zones or ALLOWED_ZONES)

    prompt = f"""
Hora atual: {now_str}.
Estado atual do dia:
- Meta: R$ {state.meta_brl:.2f}
- Regiões ativas: {current_zones_str}
- Começa a rodar depois de: {state.start_after_str or "não definido"}
- Hora de parar hoje: {state.cutoff_hour}
- Observações atuais: {state.day_notes or "nenhuma"}
- Valor acumulado atual: R$ {state.current_amount_brl:.2f} | Zona atual: {state.current_zone}

Zonas oficiais permitidas (use APENAS estes nomes exatos): {allowed_str}.
Mapeie bairros/referências como Copacabana/Ipanema/Leblon/Botafogo/Rio Sul -> "Zona Sul";
Barra/Jacarepaguá/JPA/Zona Norte/ZN -> "Zona Norte / Jacarepaguá";
Tijuca -> "Tijuca"; Centro/Rodoviária -> "Centro".

Mensagem do motorista:
"{text}"

Retorne APENAS um JSON válido com as chaves:
- "amount_brl": número float se o motorista informou valor acumulado atual, ou null.
- "zone": string exata de ALLOWED_ZONES se o motorista informou onde está ou quer focar agora, ou null.
- "custom_time": string "HH:MM" se o motorista informou horário de referência do ganho, ou null.
- "meta_brl": número float se o motorista alterou a meta do dia, ou null.
- "active_zones": lista de strings de ALLOWED_ZONES se o motorista alterou/filtrou/excluiu regiões para hoje (ex.: "sem zona norte" -> as outras zonas ativas), ou null.
- "start_after_str": string "HH:MM" se o motorista disse que só começa a rodar a partir de certo horário (ex.: "só começo depois das 18:30" -> "18:30"), ou null.
- "cutoff_hour": string "HH:MM" se o motorista disse a que horas pretende parar hoje (ex.: "vou parar às 22h" -> "22:00"), ou null.
- "day_note": string curta resumindo evento/contexto mencionado (ex.: "jogo hoje"), ou null.
- "should_recalculate": booleano indicando se vale gerar um recálculo/resposta de rota agora (true por padrão).
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "{}").strip()
    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    if data.get("zone"):
        normalized = filter_allowed_zones([str(data["zone"])])
        data["zone"] = normalized[0] if normalized else None

    if isinstance(data.get("active_zones"), list):
        data["active_zones"] = filter_allowed_zones([str(z) for z in data["active_zones"]])
    else:
        data["active_zones"] = None

    return data


def generate_initial_plan(state: DayState, now_str: str) -> str:
    meta = float(state.meta_brl or META_DEFAULT)
    zones_str = ", ".join(state.active_zones or ALLOWED_ZONES)
    cutoff = state.cutoff_hour or CUTOFF_DEFAULT
    start_line = f"- **Início efetivo:** a partir de {state.start_after_str}\n" if state.start_after_str else ""
    notes_line = f"- **Contexto do dia:** {state.day_notes}\n" if state.day_notes else ""

    prompt = f"""
Hora atual: {now_str}. Meta do dia: R$ {meta:.2f} | Parada prevista: {cutoff}.
Início previsto: {state.start_after_str or "imediato/manhã"}.
Regiões ativas hoje: {zones_str}.
Observações: {state.day_notes or "nenhuma"}.

Analise o print de Tendências de Ganhos enviado e gere o ROTEIRO INICIAL DO DIA.
Inclua:
- Foco inicial dentro de: {zones_str} (respeitando se o início é só mais tarde).
- Janela sugerida de almoço/pausa (se aplicável ao horário) e retorno antes do pico.
- Sequência tarde/noite e transições entre as regiões ativas até bater R$ {meta:.2f} antes de {cutoff}.

Formato exato:
**Plano do Dia — Meta: R$ {meta:.2f}**
{start_line}{notes_line}- **Início / Manhã:** ...
- **Almoço e Retorno:** ...
- **Tarde / Noite:** ...
- **Fechamento ({cutoff}):** ...
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
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_build_system_instruction(state),
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
    meta = float(state.meta_brl or META_DEFAULT)
    zones = state.active_zones or list(ALLOWED_ZONES)
    zones_str = ", ".join(zones)
    cutoff = state.cutoff_hour or CUTOFF_DEFAULT
    in_active_zone = state.current_zone in zones
    has_image = "Sim (pode ser mapa de calor atualizado ou gráfico do dia)" if state.chart_image_bytes else "Não"

    prompt = f"""
    Hora de referência: {now_str} (horas úteis restantes até {cutoff}: {hours_left:.1f}h).
    Início previsto: {state.start_after_str or "já rodando"}.
    Valor acumulado: R$ {state.current_amount_brl:.2f} | Meta do dia: R$ {meta:.2f} | Falta: R$ {remaining_brl:.2f}.
    Média necessária: R$ {needed_per_hour:.2f}/h.
    Zona atual: {state.current_zone} (dentro das regiões ativas hoje [{zones_str}]: {"Sim" if in_active_zone else "Não"}).
    Observações do dia: {state.day_notes or "nenhuma"}.
    Imagem anexada disponível: {has_image}.

    Gere o RECÁLCULO RÁPIDO considerando:
    1. A imagem anexada (se houver): se for mapa de calor, identifique onde há maior concentração/demanda visível dentro de [{zones_str}] sem inventar manchas inexistentes; se for o gráfico de tendências, use as janelas de movimento.
    2. O ritmo necessário ({needed_per_hour:.2f}/h até {cutoff}), a posição atual ({state.current_zone}) e o contexto do dia.

    Formato exato (máximo 4 linhas):
    **Ajuste de Rota — Faltam R$ {remaining_brl:.2f}**
    - **Ritmo:** [Adiantado / Na linha / Exigindo mais giro] — média necessária de R$ {needed_per_hour:.2f}/h até {cutoff}.
    - **Agora ({state.current_zone}):** ...
    - **Próximo passo:** ...
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
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_build_system_instruction(state),
            temperature=0.2,
        ),
    )
    return (response.text or "").strip()