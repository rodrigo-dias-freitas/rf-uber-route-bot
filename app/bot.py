from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from app.config import DAILY_META_BRL, TELEGRAM_BOT_TOKEN
from app.gemini_vision import generate_initial_plan, generate_recalculation
from app.models import DayState, calc_remaining_and_rate, parse_status_message

TZ = ZoneInfo("America/Sao_Paulo")
USER_STATES: dict[int, DayState] = {}


def get_today_state(user_id: int) -> DayState:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    state = USER_STATES.get(user_id)
    if not state or state.date_str != today:
        state = DayState(date_str=today, meta_brl=DAILY_META_BRL)
        USER_STATES[user_id] = state
    return state


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Bot de rota ativo (Meta: R$ 550,00 | Zonas: Zona Norte / Jacarepaguá, Zona Sul, Tijuca, Centro).\n"
        "• Envie o print do gráfico de Tendências de Ganhos para gerar o plano do dia.\n"
        "• Envie `<valor> <zona>` (ex: `377,84 copacabana`) para recalcular."
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    USER_STATES[user_id] = DayState(date_str=today, meta_brl=DAILY_META_BRL)
    await update.message.reply_text("Estado do dia resetado. Pode mandar o novo print do gráfico.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    user_id = update.effective_user.id
    state = get_today_state(user_id)

    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())

    state.chart_image_bytes = image_bytes
    state.chart_mime_type = "image/jpeg"

    now_dt = datetime.now(TZ)
    now_str = now_dt.strftime("%H:%M")

    await update.message.chat.send_action("typing")
    reply = generate_initial_plan(state, now_str)
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    state = get_today_state(user_id)
    amount, zone, custom_time = parse_status_message(update.message.text)

    if amount is None or not zone:
        await update.message.reply_text(
            "Formato não reconhecido. Use algo como: `170,46 rio sul` ou `377,84 copacabana 20:59`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    now_dt = datetime.now(TZ)
    if custom_time:
        hh, mm = map(int, custom_time.split(":"))
        now_dt = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    state.current_amount_brl = amount
    state.current_zone = zone
    state.last_updated_str = now_dt.strftime("%H:%M")

    remaining, hours_left, needed_per_hour = calc_remaining_and_rate(
        current_amount=state.current_amount_brl,
        now_dt=now_dt,
        meta_brl=state.meta_brl,
    )

    await update.message.chat.send_action("typing")
    reply = generate_recalculation(
        state=state,
        now_str=state.last_updated_str,
        remaining_brl=remaining,
        hours_left=hours_left,
        needed_per_hour=needed_per_hour,
    )
    await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)


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