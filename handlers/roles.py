import uuid
import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

from config import get_roles, create_role, update_role, delete_role
from keyboards import TEMPERATURE_LEVELS, cancel_keyboard, roles_menu, role_detail, confirm_menu

router = Router()
logger = logging.getLogger(__name__)


class AddRoleFSM(StatesGroup):
    waiting_title       = State()
    waiting_description = State()


class EditRoleFSM(StatesGroup):
    waiting_title       = State()
    waiting_description = State()


# ── Список ────────────────────────────────────────────────────

@router.message(F.text == "🎭 Роли")
async def roles_handler(message: Message):
    roles = get_roles()
    await message.answer(
        f"🎭 Роли ({len(roles)}):" if roles else "📭 Ролей нет. Создайте первую!",
        reply_markup=roles_menu(roles=roles)   # глобальный контекст
    )


@router.callback_query(F.data == "grole:list")
async def roles_list(callback: CallbackQuery):
    roles = get_roles()
    await callback.message.edit_text(
        f"🎭 Роли ({len(roles)}):" if roles else "📭 Ролей нет. Создайте первую!",
        reply_markup=roles_menu(roles=roles)
    )
    await callback.answer()


# ── Открыть роль ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("grole:open:"))
async def role_open(callback: CallbackQuery):
    role_key = callback.data.split(":")[2]
    role = next((r for r in get_roles() if r["key"] == role_key), None)
    if not role:
        await callback.answer("❌ Роль не найдена", show_alert=True)
        return
    desc = role.get("description") or "Не задано"
    desc_preview = desc[:200] + "…" if len(desc) > 200 else desc
    await callback.message.edit_text(
        f"🎭 {role['title']}\n\n📝 Промпт:\n{desc_preview}",
        reply_markup=role_detail(role=role)    # глобальный контекст
    )
    await callback.answer()


# ── Добавить ─────────────────────────────────────────────────

@router.callback_query(F.data == "grole:add")
async def role_add_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddRoleFSM.waiting_title)
    await callback.message.answer("✏️ Введите название роли:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(AddRoleFSM.waiting_title)
async def role_add_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if any(r["title"].lower() == title.lower() for r in get_roles()):
        await message.answer(f"⚠️ Роль «{title}» уже существует. Введите другое название:")
        return
    await state.update_data(title=title)
    await state.set_state(AddRoleFSM.waiting_description)
    await message.answer("📝 Введите системный промпт:", reply_markup=cancel_keyboard())


@router.callback_query(F.data.startswith("grole:temp:"))
async def role_set_temperature(callback: CallbackQuery):
    # grole:temp:{role_key}:{temp_key}
    parts    = callback.data.split(":")
    role_key = parts[2]
    temp_key = parts[3]

    if temp_key not in TEMPERATURE_LEVELS:
        await callback.answer("❌ Неверный уровень", show_alert=True)
        return

    update_role(role_key, temperature=temp_key)

    roles = get_roles()
    role  = next((r for r in roles if r["key"] == role_key), None)
    if not role:
        await callback.answer("❌ Роль не найдена", show_alert=True)
        return

    label, _ = TEMPERATURE_LEVELS[temp_key]
    desc = role.get("description") or "Не задано"
    desc_preview = desc[:200] + "…" if len(desc) > 200 else desc

    await callback.message.edit_text(
        f"🎭 {role['title']}\n\n📝 Промпт:\n{desc_preview}",
        reply_markup=role_detail(role=role)
    )
    await callback.answer(f"✅ {label}")



@router.message(AddRoleFSM.waiting_description)
async def role_add_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    create_role(key=str(uuid.uuid4())[:8], title=data["title"], description=message.text.strip())
    await state.clear()
    roles = get_roles()
    await message.answer(
        f"✅ Роль «{data['title']}» создана!\n\n🎭 Роли ({len(roles)}):",
        reply_markup=roles_menu(roles=roles)
    )


# ── Редактировать название ────────────────────────────────────

@router.callback_query(F.data.startswith("grole:edit:title:"))
async def role_edit_title_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditRoleFSM.waiting_title)
    await state.update_data(role_key=callback.data.split(":")[3])
    await callback.message.answer("✏️ Введите новое название:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(EditRoleFSM.waiting_title)
async def role_edit_title_save(message: Message, state: FSMContext):
    data = await state.get_data()
    update_role(data["role_key"], title=message.text.strip())
    await state.clear()
    role = next((r for r in get_roles() if r["key"] == data["role_key"]), {})
    await message.answer(
        f"✅ Название обновлено.\n\n🎭 {role.get('title')}\n📝 {role.get('description') or 'Не задано'}",
        reply_markup=role_detail(role=role)
    )


# ── Редактировать промпт ──────────────────────────────────────

@router.callback_query(F.data.startswith("grole:edit:desc:"))
async def role_edit_desc_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditRoleFSM.waiting_description)
    await state.update_data(role_key=callback.data.split(":")[3])
    await callback.message.answer("📝 Введите новый промпт:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(EditRoleFSM.waiting_description)
async def role_edit_desc_save(message: Message, state: FSMContext):
    data = await state.get_data()
    update_role(data["role_key"], description=message.text.strip())
    await state.clear()
    role = next((r for r in get_roles() if r["key"] == data["role_key"]), {})
    desc_preview = role.get("description", "")[:200]
    await message.answer(
        f"✅ Промпт обновлён.\n\n🎭 {role.get('title')}\n📝 {desc_preview}",
        reply_markup=role_detail(role=role)
    )


# ── Удалить ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("grole:delete:") & ~F.data.contains(":yes:"))
async def role_delete_confirm(callback: CallbackQuery):
    role_key = callback.data.split(":")[2]
    role = next((r for r in get_roles() if r["key"] == role_key), {})
    await callback.message.edit_text(
        f"⚠️ Удалить роль «{role.get('title', role_key)}»?\n"
        f"Пользователи с этой ролью останутся без роли.",
        reply_markup=confirm_menu(
            yes_data=f"grole:delete:yes:{role_key}",
            no_data=f"grole:open:{role_key}"
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("grole:delete:yes:"))
async def role_delete_do(callback: CallbackQuery):
    role_key = callback.data.split(":")[3]
    delete_role(role_key)
    roles = get_roles()
    await callback.message.edit_text(
        f"✅ Роль удалена.\n\n🎭 Роли ({len(roles)}):",
        reply_markup=roles_menu(roles=roles)
    )
    await callback.answer("🗑️ Роль удалена")


# ── Отмена ────────────────────────────────────────────────────

@router.message(
    F.text == "/cancel",
    StateFilter(
        AddRoleFSM.waiting_title, AddRoleFSM.waiting_description,
        EditRoleFSM.waiting_title, EditRoleFSM.waiting_description,
    )
)
async def cancel_role_fsm(message: Message, state: FSMContext):
    await state.clear()
    roles = get_roles()
    await message.answer(
        f"❌ Отменено.\n\n🎭 Роли ({len(roles)}):",
        reply_markup=roles_menu(roles=roles)
    )
