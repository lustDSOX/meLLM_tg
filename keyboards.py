from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButtonRequestUsers, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ══════════════════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ (Reply)
# ══════════════════════════════════════════════════════════════

def main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👤 Аккаунты"),
        KeyboardButton(text="🎭 Роли"),
        KeyboardButton(text="📊 Статус")
    )
    return builder.as_markup(resize_keyboard=True)


# ══════════════════════════════════════════════════════════════
#  АККАУНТЫ (Telethon)
# ══════════════════════════════════════════════════════════════

def accounts_menu(accounts: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for acc in accounts:
        display = f"@{acc['username']}" if acc.get("username") else acc.get("title", "Без имени")
        builder.row(InlineKeyboardButton(
            text=f"📱 {display}",
            callback_data=f"acc:open:{acc['id']}"
        ))

    builder.row(InlineKeyboardButton(
        text="➕ Добавить аккаунт",
        callback_data="acc:add"
    ))
    builder.row(InlineKeyboardButton(
        text="❌ Закрыть", callback_data="close"
    ))
    return builder.as_markup()


def account_detail(account: dict, users: list[dict]) -> InlineKeyboardMarkup:
    acc_id = account["id"]
    builder = InlineKeyboardBuilder()

    if users:
        builder.row(InlineKeyboardButton(
            text="── 👥 Пользователи ──",
            callback_data="noop"
        ))
        for user in users:
            status = "🟢" if user.get("active") else "🔴"
            uname = f"@{user['username']}" if user.get("username") else f"id:{user['id']}"
            builder.row(
                InlineKeyboardButton(
                    text=f"{status} {uname}",
                    callback_data=f"usr:open:{acc_id}:{user['id']}"
                ),
                InlineKeyboardButton(
                    text="🗑️",
                    callback_data=f"usr:delete:{acc_id}:{user['id']}"
                )
            )
    else:
        builder.row(InlineKeyboardButton(
            text="👥 Пользователей нет",
            callback_data="noop"
        ))

    builder.row(InlineKeyboardButton(
        text="➕ Добавить пользователя",
        callback_data=f"usr:add:{acc_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="🗑️ Удалить аккаунт",
        callback_data=f"acc:delete:{acc_id}"
    ))
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="nav:accounts"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════
#  ПОЛЬЗОВАТЕЛЬ (внутри аккаунта)
# ══════════════════════════════════════════════════════════════

def user_detail(
    acc_id: str,
    user: dict,
    active_role: str,
    active_ctx: str
) -> InlineKeyboardMarkup:
    user_id = user["id"]
    builder = InlineKeyboardBuilder()

    # Вкл/Выкл
    is_active = user.get("active", False)
    builder.row(InlineKeyboardButton(
        text=f"{'🟢 Включен' if is_active else '🔴 Выключен'}  —  нажать для переключения",
        callback_data=f"usr:toggle:{acc_id}:{user_id}"
    ))

    # Роль и Контекст
    builder.row(
        InlineKeyboardButton(
            text=f"🤖 Роль: {active_role}",
            callback_data=f"usr:role:{acc_id}:{user_id}"
        ),
        InlineKeyboardButton(
            text=f"📏 Контекст: {active_ctx} сообщ.",
            callback_data=f"usr:ctx:{acc_id}:{user_id}"
        )
    )

    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"acc:open:{acc_id}"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════
#  РОЛЕВАЯ МОДЕЛЬ
# ══════════════════════════════════════════════════════════════

def roles_menu(
    roles: list[dict],
    active_role: str = None,
    acc_id: str = None,         # None = глобальный контекст
    user_id: int = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    global_ctx = acc_id is None or user_id is None

    if not roles:
        builder.row(InlineKeyboardButton(
            text="📭 Нет ролей — добавьте первую",
            callback_data="noop"
        ))
    else:
        for role in roles:
            is_active = role["key"] == active_role
            if global_ctx:
                set_cb  = "noop"                          # выбор роли недоступен глобально
                edit_cb = f"grole:open:{role['key']}"
            else:
                set_cb  = f"role:set:{acc_id}:{user_id}:{role['key']}"
                edit_cb = f"role:edit:{acc_id}:{user_id}:{role['key']}"

            builder.row(
                InlineKeyboardButton(
                    text=f"{'✅ ' if is_active else ''}🎭 {role['title']}",
                    callback_data=set_cb
                ),
                InlineKeyboardButton(
                    text="✏️",
                    callback_data=edit_cb
                )
            )

    # Кнопка добавления
    if global_ctx:
        builder.row(InlineKeyboardButton(text="➕ Добавить роль", callback_data="grole:add"))

    # Навигация
    if global_ctx:
        builder.row(InlineKeyboardButton(text="❌ Закрыть", callback_data="close"))
    else:
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"usr:open:{acc_id}:{user_id}"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
        )
    return builder.as_markup()


TEMPERATURE_LEVELS = {
    "precise":  ("🧊 Сдержанный", 0.3),
    "balanced": ("💬 Обычный",    0.7),
    "lively":   ("😄 Живой",      0.9),
}

def role_detail(
    role: dict,
    is_active: bool = False,
    acc_id: str = None,
    user_id: int = None
) -> InlineKeyboardMarkup:
    key = role["key"]
    builder = InlineKeyboardBuilder()
    global_ctx = acc_id is None or user_id is None

    desc = role.get("description") or "Не задано"
    desc_preview = desc[:30] + "…" if len(desc) > 30 else desc

    title_cb = f"grole:edit:title:{key}" if global_ctx else f"role:edit:title:{acc_id}:{user_id}:{key}"
    desc_cb  = f"grole:edit:desc:{key}"  if global_ctx else f"role:edit:desc:{acc_id}:{user_id}:{key}"

    builder.row(InlineKeyboardButton(
        text=f"✏️ Название: {role['title']}",
        callback_data=title_cb
    ))
    builder.row(InlineKeyboardButton(
        text=f"📝 Описание: {desc_preview}",
        callback_data=desc_cb
    ))

    # Температура — три кнопки в одну строку
    active_temp = role.get("temperature", "balanced")
    temp_cb_prefix = "grole:temp" if global_ctx else f"role:temp:{acc_id}:{user_id}"
    builder.row(*[
        InlineKeyboardButton(
            text=f"{'✅ ' if active_temp == t_key else ''}{label}",
            callback_data=f"{temp_cb_prefix}:{key}:{t_key}"
        )
        for t_key, (label, _) in TEMPERATURE_LEVELS.items()
    ])

    # Активация (только в контексте пользователя)
    if not global_ctx:
        if is_active:
            builder.row(InlineKeyboardButton(text="✅ Активная роль", callback_data="noop"))
        else:
            builder.row(InlineKeyboardButton(
                text="☑️ Сделать активной",
                callback_data=f"role:set:{acc_id}:{user_id}:{key}"
            ))

    delete_cb = f"grole:delete:{key}" if global_ctx else f"role:delete:{acc_id}:{user_id}:{key}"
    builder.row(InlineKeyboardButton(text="🗑️ Удалить роль", callback_data=delete_cb))

    back_cb = "grole:list" if global_ctx else f"usr:role:{acc_id}:{user_id}"
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    )
    return builder.as_markup()

# ══════════════════════════════════════════════════════════════
#  ОКНО КОНТЕКСТА
# ══════════════════════════════════════════════════════════════

CONTEXT_SIZES = {
    "0":  "🚫 Без контекста",
    "10":  "📦 10 сообщений",
    "30": "📬 30 сообщений",
    "50": "📫 50 сообщений",
}

def context_menu(acc_id: str, user_id: int, active_ctx: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in CONTEXT_SIZES.items():
        text = f"✅ {label}" if key == active_ctx else label
        builder.row(InlineKeyboardButton(
            text=text,
            callback_data=f"usr:ctx:set:{acc_id}:{user_id}:{key}"
        ))
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"usr:open:{acc_id}:{user_id}"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close")
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════
#  НАТИВНЫЙ ВЫБОР ПОЛЬЗОВАТЕЛЯ Telegram (временная Reply)
# ══════════════════════════════════════════════════════════════

def request_user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="👤 Выбрать пользователя",
                request_users=KeyboardButtonRequestUsers(
                    request_id=1,
                    user_is_bot=False,
                    max_quantity=1,
                    request_name=True,
                    request_username=True,
                )
            )],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="close")
    ]])


# ══════════════════════════════════════════════════════════════
#  УНИВЕРСАЛЬНОЕ ПОДТВЕРЖДЕНИЕ
# ══════════════════════════════════════════════════════════════

def confirm_menu(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Отмена",      callback_data=no_data)
    ]])
