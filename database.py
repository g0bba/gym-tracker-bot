import os
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Exercise(Base):
    __tablename__ = 'exercises'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    muscle_group = Column(String)

class Workout(Base):
    __tablename__ = 'workouts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    date = Column(DateTime, default=datetime.utcnow)
    title = Column(String, default="Тренировка")

class WorkoutExercise(Base):
    __tablename__ = 'workout_exercises'
    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, ForeignKey('workouts.id'))
    exercise_id = Column(Integer, ForeignKey('exercises.id'))
    order = Column(Integer)

class Set(Base):
    __tablename__ = 'sets'
    id = Column(Integer, primary_key=True)
    workout_exercise_id = Column(Integer, ForeignKey('workout_exercises.id'))
    set_number = Column(Integer)
    weight = Column(Float)
    reps = Column(Integer)
    is_warmup = Column(Boolean, default=False)

async def create_db():
    # Берем URL из настроек хостинга, а если нет - используем локальный SQLite
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gym_tracker.db")
    
    # Если это PostgreSQL (в будущем), адаптируем строку для асинхронности и SSL
    if db_url.startswith("postgresql"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode" not in db_url:
            db_url += "?sslmode=require"

    try:
        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ База данных подключена и таблицы созданы!")
        return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        raise
