from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
import re
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from app.config import ALLOWED_ZONES, TELEGRAM_BOT_TOKEN
from app.gemini_vision import (
    generate_initial_plan,
    generate_recalculation,
    interpret_free_message,
)
from app.models import (
    CUTOFF_DEFAULT,
    META_DEFAULT,
    DayState,
    calc_remaining_and_rate,
    parse_status_message,
)

TZ = ZoneInfo("America/Sao_Paulo")
USER_STATES: dict[int, DayState] = {}


def get_today_state(user_id: int) -> DayState:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    state = USER_STATES.get(user_id)
    if not state or state.date_str != today:
        state = DayState(
            date_str=today,
            meta_brl=META_DEFAULT,
            active_zones=list(ALLOWED_ZONES),
            cutoff_hour=CUTOFF_DEFAULT,
        )
        USER_STATES[user_id] = state
    return state


def _format_zones(zones: list[str]) -> str:
    return ", ".join(zones) if zones else ", ".join(ALLOWED_ZONES)


async def _send_markdown_safe(target_message, text: str, edit: bool = False):
    safe_text = (text or "").strip() or "Não foi possível gerar a mensagem no momento."
    try:
        if edit:
            await target_message.edit_text(safe_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await target_message.reply_text(safe_text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        if edit:
            await target_message.edit_text(safe_text)
        else:
            await target_message.reply_text(safe_text)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = update.effective_user.id
    state = get_today_state(user_id)
    await _send_markdown_safe(
        update.message,
        f"Bot de rota ativo (Meta: R$ {state.meta_brl:.2f} | Parada: {state.cutoff_hour} | Regiões: {_format_zones(state.active_zones)}).\n"
        "• Envie o print do gráfico de Tendências de Ganhos para gerar o plano do dia.\n"
        "• Mande status rápido (`377,84 copacabana`) ou fale livremente (ex.: `hoje tem jogo, só começo depois das 18:30 e paro às 23h, meta 420 só zona sul`).",
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = update.effective_user.id
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    USER_STATES[user_id] = DayState(
        date_str=today,
        meta_brl=META_DEFAULT,
        active_zones=list(ALLOWED_ZONES),
        cutoff_hour=CUTOFF_DEFAULT,
    )
    await update.message.reply_text(
        f"Estado do dia resetado (Meta: R$ {META_DEFAULT:.2f} | Parada: {CUTOFF_DEFAULT} | Todas as regiões ativas). Pode mandar o novo print."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return
    
    user_id = update.effective_user.id
    state = get_today_state(user_id)

    now_dt = datetime.now(TZ)
    now_str = now_dt.strftime("%H:%M")
    caption = (update.message.caption or "").strip()

    print("DEBUG HANDLE_PHOTO CHEGOU:", user_id, now_str, "caption=", repr(caption))

    is_heatmap_update = False
    if caption:
        if re.search(r"\b(mapa|calor|recalcular|agora)\b", caption, flags=re.IGNORECASE):
            is_heatmap_update = True

        parsed = interpret_free_message(state, caption, now_str)
        if parsed.get("meta_brl") is not None:
            state.meta_brl = float(parsed["meta_brl"])
        if parsed.get("active_zones"):
            state.active_zones = parsed["active_zones"]
        if parsed.get("start_after_str"):
            state.start_after_str = parsed["start_after_str"]
        if parsed.get("cutoff_hour"):
            state.cutoff_hour = parsed["cutoff_hour"]
        if parsed.get("day_note"):
            state.day_notes = f"{state.day_notes}; {parsed['day_note']}".strip("; ")
        if parsed.get("amount_brl") is not None:
            state.current_amount_brl = float(parsed["amount_brl"])
            is_heatmap_update = True
        if parsed.get("zone"):
            state.current_zone = parsed["zone"]
            is_heatmap_update = True
        if parsed.get("custom_time"):
            try:
                hh, mm = map(int, str(parsed["custom_time"]).split(":"))
                now_dt = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
                now_str = now_dt.strftime("%H:%M")
            except Exception:
                pass

    # Se já há ganho registrado no dia e não foi pedido plano inicial, trata como atualização de mapa
    if not is_heatmap_update and state.current_amount_brl > 0:
        is_heatmap_update = True

    loading_text = "🔄 Recalculando rota com o novo mapa..." if is_heatmap_update else "🗺️ Traçando a rota do dia..."
    status_msg = await update.message.reply_text(loading_text)
    await update.message.chat.send_action("typing")

    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())

    state.chart_image_bytes = image_bytes
    state.chart_mime_type = "image/jpeg"

    if is_heatmap_update:
        state.last_updated_str = now_str
        remaining, hours_left, needed_per_hour = calc_remaining_and_rate(
            current_amount=state.current_amount_brl,
            now_dt=now_dt,
            meta_brl=state.meta_brl,
            cutoff_hour=state.cutoff_hour,
            start_after_str=state.start_after_str,
        )
        reply = generate_recalculation(
            state=state,
            now_str=now_str,
            remaining_brl=remaining,
            hours_left=hours_left,
            needed_per_hour=needed_per_hour,
        )
    else:
        reply = generate_initial_plan(state, now_str)

    if not reply or not str(reply).strip():
        reply = "Não consegui gerar a análise do print agora. Tente enviar a imagem novamente em instantes."

    await _send_markdown_safe(status_msg, reply, edit=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    state = get_today_state(user_id)
    text = update.message.text.strip()
    now_dt = datetime.now(TZ)
    ref_str = now_dt.strftime("%H:%M")

    # Atalho direto para mensagens simples no formato "<valor> <zona> [hora]"
    amount, zone, custom_time = parse_status_message(text)
    if amount is not None and zone:
        if custom_time:
            hh, mm = map(int, custom_time.split(":"))
            now_dt = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
            ref_str = now_dt.strftime("%H:%M")

        state.current_amount_brl = amount
        state.current_zone = zone
        state.last_updated_str = ref_str
    else:
        status_msg = await update.message.reply_text("🔄 Atualizando cenário e recalculando rota...")
        await update.message.chat.send_action("typing")

        parsed = interpret_free_message(state, text, ref_str)

        if parsed.get("meta_brl") is not None:
            state.meta_brl = float(parsed["meta_brl"])
        if parsed.get("active_zones"):
            state.active_zones = parsed["active_zones"]
        if parsed.get("start_after_str"):
            state.start_after_str = parsed["start_after_str"]
        if parsed.get("cutoff_hour"):
            state.cutoff_hour = parsed["cutoff_hour"]
        if parsed.get("day_note"):
            state.day_notes = f"{state.day_notes}; {parsed['day_note']}".strip("; ")
        if parsed.get("amount_brl") is not None:
            state.current_amount_brl = float(parsed["amount_brl"])
        if parsed.get("zone"):
            state.current_zone = parsed["zone"]

        if parsed.get("custom_time"):
            try:
                hh, mm = map(int, str(parsed["custom_time"]).split(":"))
                now_dt = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
                ref_str = now_dt.strftime("%H:%M")
            except Exception:
                pass

        state.last_updated_str = ref_str

        remaining, hours_left, needed_per_hour = calc_remaining_and_rate(
            current_amount=state.current_amount_brl,
            now_dt=now_dt,
            meta_brl=state.meta_brl,
            cutoff_hour=state.cutoff_hour,
            start_after_str=state.start_after_str,
        )
        reply = generate_recalculation(
            state=state,
            now_str=ref_str,
            remaining_brl=remaining,
            hours_left=hours_left,
            needed_per_hour=needed_per_hour,
        )
        await _send_markdown_safe(status_msg, reply, edit=True)
        return

    status_msg = await update.message.reply_text("🔄 Recalculando rota e ritmo...")
    await update.message.chat.send_action("typing")

    remaining, hours_left, needed_per_hour = calc_remaining_and_rate(
        current_amount=state.current_amount_brl,
        now_dt=now_dt,
        meta_brl=state.meta_brl,
        cutoff_hour=state.cutoff_hour,
        start_after_str=state.start_after_str,
    )
    reply = generate_recalculation(
        state=state,
        now_str=ref_str,
        remaining_brl=remaining,
        hours_left=hours_left,
        needed_per_hour=needed_per_hour,
    )
    await _send_markdown_safe(status_msg, reply, edit=True)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado no .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()