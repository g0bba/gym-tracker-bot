import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from database import create_db, User, Exercise, Workout, WorkoutExercise, Set

# Токен берём из настроек хостинга, а не из кода!
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db_session = None

class WorkoutState(StatesGroup):
    waiting_for_exercise = State()
    waiting_for_weight_reps = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    async with db_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == str(message.from_user.id)))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=str(message.from_user.id), username=message.from_user.username)
            session.add(user)
            await session.commit()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 🏋️‍♂️\n"
        "Я твой трекер тренировок.\n"
        "Напиши /new, чтобы начать новую тренировку!"
    )

@dp.message(F.text == "/new")
async def start_workout(message: types.Message, state: FSMContext):
    async with db_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == str(message.from_user.id)))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("⚠️ Сначала напиши /start")
            return
        new_workout = Workout(user_id=user.id, title=f"Тренировка {message.date.strftime('%d.%m')}")
        session.add(new_workout)
        await session.commit()
        await session.refresh(new_workout)
    await state.update_data(workout_id=new_workout.id)
    await state.set_state(WorkoutState.waiting_for_exercise)
    await message.answer("🔥 Тренировка начата!\n\nНапиши название первого упражнения (например: *Жим лежа*).")

@dp.message(WorkoutState.waiting_for_exercise)
async def process_exercise_name(message: types.Message, state: FSMContext):
    exercise_name = message.text.strip().title()
    async with db_session() as session:
        result = await session.execute(select(Exercise).where(Exercise.name == exercise_name))
        exercise = result.scalar_one_or_none()
        if not exercise:
            exercise = Exercise(name=exercise_name, muscle_group="Не указано")
            session.add(exercise)
            await session.commit()
            await session.refresh(exercise)
        data = await state.get_data()
        workout_exercise = WorkoutExercise(workout_id=data['workout_id'], exercise_id=exercise.id, order=1)
        session.add(workout_exercise)
        await session.commit()
        await session.refresh(workout_exercise)
    await state.update_data(workout_exercise_id=workout_exercise.id, exercise_name=exercise_name)
    await state.set_state(WorkoutState.waiting_for_weight_reps)
    await message.answer(f"💪 Записал: *{exercise_name}*.\n\nНапиши вес и повторения через пробел.\nНапример: `80 10`")

@dp.message(WorkoutState.waiting_for_weight_reps)
async def process_weight_reps(message: types.Message, state: FSMContext):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError
        weight = float(parts[0].replace(',', '.'))
        reps = int(parts[1])
    except ValueError:
        await message.answer("⚠️ Не понял формат. Напиши два числа через пробел, например: `80 10`")
        return
    data = await state.get_data()
    async with db_session() as session:
        result = await session.execute(select(Set).where(Set.workout_exercise_id == data['workout_exercise_id']))
        existing_sets = result.scalars().all()
        set_number = len(existing_sets) + 1
        new_set = Set(workout_exercise_id=data['workout_exercise_id'], set_number=set_number, weight=weight, reps=reps, is_warmup=(set_number == 1))
        session.add(new_set)
        await session.commit()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Еще один подход", callback_data="add_another_set")],
        [InlineKeyboardButton(text="✅ Закончить упражнение", callback_data="finish_exercise")]
    ])
    await message.answer(
        f"✅ **{data['exercise_name']}**\nПодход #{set_number}: **{weight} кг x {reps} раз**\n\nЧто делаем дальше?",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "add_another_set")
async def add_another_set_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("💪 Давай следующий подход!\nНапиши вес и повторения (например: `82.5 8`):")
    await state.set_state(WorkoutState.waiting_for_weight_reps)
    await callback.answer()

@dp.callback_query(F.data == "finish_exercise")
async def finish_exercise_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text(f"🎉 Упражнение **{data['exercise_name']}** завершено!\nНапиши /new, чтобы добавить следующее.")
    await callback.answer()

async def main():
    global db_session
    print("🚀 Запуск бота...")
    db_session = await create_db()
    print("✅ База готова! Бот слушает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
