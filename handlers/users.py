import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

from config import (
    get_account, get_user,
    create_user, update_user, delete_user,
    get_roles, delete_role,
)
from keyboards import (
    account_detail,
    main_menu,
    user_detail,
    roles_menu, role_detail,
    context_menu,
    request_user_keyboard,
    confirm_menu,
    CONTEXT_SIZES
)

router = Router()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════════════════════════

class AddUserFSM(StatesGroup):
    waiting_user_select = State()


class EditUserFSM(StatesGroup):
    waiting_description = State()


# ══════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ
# ══════════════════════════════════════════════════════════════

def _role_title(role_key: str | None) -> str:
    """Получить название роли по ключу."""
    if not role_key:
        return "Не задана"
    roles = get_roles()
    role = next((r for r in roles if r["key"] == role_key), None)
    return role["title"] if role else role_key


def _user_detail_text(acc: dict, user: dict) -> str:
    uname = f"@{user['username']}" if user.get("username") else user.get("name", str(user["id"]))
    return (
        f"👤 {uname}\n"
        f"📝 {user.get('description') or 'Описание не задано'}\n"
        f"Статус: {'🟢 Включен' if user.get('active') else '🔴 Выключен'}"
    )


def _account_detail_text(acc: dict) -> str:
    uname = f"@{acc['username']}" if acc.get("username") else acc["id"]
    users = list(acc.get("users", {}).values())
    return (
        f"📱 {uname}\n"
        f"📝 {acc.get('description') or 'Описание не задано'}\n"
        f"👥 Пользователей: {len(users)}"
    )


# ══════════════════════════════════════════════════════════════
#  ДОБАВИТЬ ПОЛЬЗОВАТЕЛЯ — нативный выбор Telegram
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:add:"))
async def user_add_start(callback: CallbackQuery, state: FSMContext):
    acc_id = callback.data.split(":")[2]
    await state.set_state(AddUserFSM.waiting_user_select)
    await state.update_data(acc_id=acc_id)
    await callback.message.answer(
        "👤 Выберите пользователя из списка Telegram:",
        reply_markup=request_user_keyboard()
    )
    await callback.answer()


@router.message(AddUserFSM.waiting_user_select, F.users_shared)
async def user_add_receive(message: Message, state: FSMContext):
    data = await state.get_data()
    acc_id = data["acc_id"]
    shared = message.users_shared.users[0]

    user_id  = shared.user_id
    username = shared.username or None
    name     = shared.first_name or "Без имени"

    # Проверка: уже добавлен
    if get_user(acc_id, str(user_id)):
        await message.answer(f"⚠️ Пользователь уже добавлен к этому аккаунту.", reply_markup=main_menu())
        await state.clear()
        return

    create_user(acc_id, user_id, username, name)
    await state.clear()

    uname = f"@{username}" if username else name
    acc = get_account(acc_id)
    users = list(acc.get("users", {}).values())
    await message.answer(f"✅ Пользователь {uname} добавлен!", reply_markup=main_menu())
    await message.answer(
        _account_detail_text(acc),
        reply_markup=account_detail(acc, users)
    )


@router.message(AddUserFSM.waiting_user_select, F.text == "❌ Отмена")
async def user_add_cancel(message: Message, state: FSMContext):
    data = await state.get_data()
    acc_id = data.get("acc_id")
    await state.clear()
    await message.answer("❌ Отменено")
    if acc_id:
        acc = get_account(acc_id)
        users = list(acc.get("users", {}).values())
        await message.answer(
            _account_detail_text(acc),
            reply_markup=account_detail(acc, users)
        )


# ══════════════════════════════════════════════════════════════
#  ОТКРЫТЬ ПОЛЬЗОВАТЕЛЯ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:open:"))
async def user_open(callback: CallbackQuery):
    _, _, acc_id, user_id = callback.data.split(":")
    user = get_user(acc_id, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(
        _user_detail_text(get_account(acc_id), user),
        reply_markup=user_detail(
            acc_id=acc_id,
            user=user,
            active_role=_role_title(user.get("role")),
            active_ctx=user.get("context", "10")
        )
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════
#  УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:delete:"))
async def user_delete_confirm(callback: CallbackQuery):
    _, _, acc_id, user_id = callback.data.split(":")
    user = get_user(acc_id, user_id)
    uname = f"@{user['username']}" if user and user.get("username") else user_id
    await callback.message.edit_text(
        f"⚠️ Удалить пользователя {uname}?",
        reply_markup=confirm_menu(
            yes_data=f"usr:delete:yes:{acc_id}:{user_id}",
            no_data=f"usr:open:{acc_id}:{user_id}"
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("usr:delete:yes:"))
async def user_delete_do(callback: CallbackQuery):
    _, _, _, acc_id, user_id = callback.data.split(":")
    delete_user(acc_id, user_id)
    acc = get_account(acc_id)
    users = list(acc.get("users", {}).values())
    await callback.message.edit_text(
        _account_detail_text(acc),
        reply_markup=account_detail(acc, users)
    )
    await callback.answer("🗑️ Пользователь удалён")


# ══════════════════════════════════════════════════════════════
#  ВКЛ/ВЫКЛ ПОЛЬЗОВАТЕЛЯ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:toggle:"))
async def user_toggle(callback: CallbackQuery):
    _, _, acc_id, user_id = callback.data.split(":")
    user = get_user(acc_id, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    new_state = not user.get("active", False)
    update_user(acc_id, user_id, active=new_state)
    user["active"] = new_state

    await callback.message.edit_text(
        _user_detail_text(get_account(acc_id), user),
        reply_markup=user_detail(
            acc_id=acc_id,
            user=user,
            active_role=_role_title(user.get("role")),
            active_ctx=user.get("context", "10")
        )
    )
    await callback.answer(f"{'🟢 Включен' if new_state else '🔴 Выключен'}")


# ══════════════════════════════════════════════════════════════
#  ОПИСАНИЕ ПОЛЬЗОВАТЕЛЯ (редактирование)
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:edit:desc:"))
async def user_edit_desc_start(callback: CallbackQuery, state: FSMContext):
    _, _, _, acc_id, user_id = callback.data.split(":")
    await state.set_state(EditUserFSM.waiting_description)
    await state.update_data(acc_id=acc_id, user_id=user_id)
    await callback.message.answer(
        "📝 Введите описание пользователя:\n/cancel — отменить"
    )
    await callback.answer()


@router.message(EditUserFSM.waiting_description)
async def user_edit_desc_save(message: Message, state: FSMContext):
    data = await state.get_data()
    acc_id, user_id = data["acc_id"], data["user_id"]
    update_user(acc_id, user_id, description=message.text.strip())
    await state.clear()
    user = get_user(acc_id, user_id)
    await message.answer(
        _user_detail_text(get_account(acc_id), user),
        reply_markup=user_detail(
            acc_id=acc_id,
            user=user,
            active_role=_role_title(user.get("role")),
            active_ctx=user.get("context", "10")
        )
    )


# ══════════════════════════════════════════════════════════════
#  РОЛИ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:role:") & ~F.data.contains(":set:"))
async def roles_open(callback: CallbackQuery):
    parts = callback.data.split(":")       # usr:role:acc_id:user_id
    acc_id, user_id = parts[2], parts[3]
    user = get_user(acc_id, user_id)
    await callback.message.edit_text(
        "🤖 Выберите или настройте роль:",
        reply_markup=roles_menu(
            acc_id=acc_id,
            user_id=int(user_id),
            active_role=user.get("role") if user else None,
            roles=get_roles()
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("role:set:"))
async def role_set(callback: CallbackQuery):
    parts = callback.data.split(":")       # role:set:acc_id:user_id:key
    acc_id, user_id, role_key = parts[2], parts[3], parts[4]
    update_user(acc_id, user_id, role=role_key)
    await callback.message.edit_reply_markup(
        reply_markup=roles_menu(
            acc_id=acc_id,
            user_id=int(user_id),
            active_role=role_key,
            roles=get_roles()
        )
    )
    await callback.answer(f"✅ Роль: {_role_title(role_key)}")


@router.callback_query(
    F.data.startswith("role:edit:")
    & ~F.data.contains(":title:")
    & ~F.data.contains(":desc:")
)
async def role_open_detail(callback: CallbackQuery):
    parts = callback.data.split(":")       # role:edit:acc_id:user_id:key
    acc_id, user_id, role_key = parts[2], parts[3], parts[4]
    roles = get_roles()
    role = next((r for r in roles if r["key"] == role_key), None)
    if not role:
        await callback.answer("❌ Роль не найдена", show_alert=True)
        return
    user = get_user(acc_id, user_id)
    await callback.message.edit_text(
        f"🎭 {role['title']}\n📝 {role.get('description') or 'Описание не задано'}",
        reply_markup=role_detail(
            acc_id=acc_id,
            user_id=int(user_id),
            role=role,
            is_active=user.get("role") == role_key if user else False
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("role:delete:"))
async def role_delete_confirm(callback: CallbackQuery):
    parts = callback.data.split(":")       # role:delete:acc_id:user_id:key
    acc_id, user_id, role_key = parts[2], parts[3], parts[4]
    roles = get_roles()
    role = next((r for r in roles if r["key"] == role_key), {})
    await callback.message.edit_text(
        f"⚠️ Удалить роль «{role.get('title', role_key)}»?\n"
        f"Она будет удалена у всех пользователей.",
        reply_markup=confirm_menu(
            yes_data=f"role:delete:yes:{acc_id}:{user_id}:{role_key}",
            no_data=f"role:edit:{acc_id}:{user_id}:{role_key}"
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("role:delete:yes:"))
async def role_delete_do(callback: CallbackQuery):
    parts = callback.data.split(":")       # role:delete:yes:acc_id:user_id:key
    acc_id, user_id, role_key = parts[3], parts[4], parts[5]
    delete_role(role_key)
    user = get_user(acc_id, user_id)
    # Сбросить роль пользователю если она была активна
    if user and user.get("role") == role_key:
        update_user(acc_id, user_id, role=None)
        user["role"] = None
    await callback.message.edit_text(
        "✅ Роль удалена.",
        reply_markup=roles_menu(
            acc_id=acc_id,
            user_id=int(user_id),
            active_role=user.get("role") if user else None,
            roles=get_roles()
        )
    )
    await callback.answer("🗑️ Роль удалена")


# ══════════════════════════════════════════════════════════════
#  КОНТЕКСТ
# ══════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("usr:ctx:") & ~F.data.contains(":set:"))
async def context_open(callback: CallbackQuery):
    parts = callback.data.split(":")       # usr:ctx:acc_id:user_id
    acc_id, user_id = parts[2], parts[3]
    user = get_user(acc_id, user_id)
    await callback.message.edit_text(
        "📏 Выберите размер контекста:",
        reply_markup=context_menu(
            acc_id=acc_id,
            user_id=int(user_id),
            active_ctx=user.get("context", "10") if user else "10"
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("usr:ctx:set:"))
async def context_set(callback: CallbackQuery):
    parts = callback.data.split(":")       # usr:ctx:set:acc_id:user_id:value
    acc_id, user_id, ctx_val = parts[3], parts[4], parts[5]
    update_user(acc_id, user_id, context=ctx_val)
    ctx_label = CONTEXT_SIZES.get(ctx_val, ctx_val)
    await callback.message.edit_reply_markup(
        reply_markup=context_menu(
            acc_id=acc_id,
            user_id=int(user_id),
            active_ctx=ctx_val
        )
    )
    await callback.answer(f"✅ {ctx_label}")


# ══════════════════════════════════════════════════════════════
#  ОТМЕНА FSM (общая)
# ══════════════════════════════════════════════════════════════

@router.message(
    F.text == "/cancel",
    StateFilter(
        EditUserFSM.waiting_description,
    )
)
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено")
