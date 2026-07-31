import asyncio
import logging
import sys
import os
import psycopg2 as ps

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    FSInputFile
)
from dotenv import load_dotenv

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

#bot parameters
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

#connection with sql
connection = ps.connect(
     host='localhost',
     user='postgres',
     password='SQL2025Aitu@',
     database='users'
)
print("db connected successfully")
cur = connection.cursor()

#bot menu
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Books")],
        [KeyboardButton(text="Cheat Sheets")],
        [KeyboardButton(text="Syllabus")],
        [KeyboardButton(text="My Results")]
    ],
    resize_keyboard=True
)


class Registration(StatesGroup):
    waiting_for_name = State()


#registration block
@dp.message(Registration.waiting_for_name)
async def check_user(message: Message, state: FSMContext):

    text = message.text.strip()

    parts = text.split()

    if len(parts) != 2:
        await message.answer(
            "Please enter your name and surname\n"
            "Example:\n"
            "Rustam Yakubov"
        )
        return

    first_name = parts[0]
    last_name = parts[1]

    cur.execute(
        """
        SELECT id
        FROM students
        WHERE first_name=%s
        AND last_name=%s
        """,
        (first_name, last_name)
    )

    user = cur.fetchone()

    if user is None:
        await message.answer(
            "You are not registered\n"
            "Please contact your mentor - @scmblzhaha"
        )
        return

    student_id = user[0]

    cur.execute(
        """
        UPDATE students
        SET chat_id=%s
        WHERE id=%s
        """,
        (message.chat.id, student_id)
    )

    connection.commit()

    await message.answer(
        "Registration completed successfully. Good luck in learning Calculus I",
        reply_markup=menu
    )

    await state.clear()


#start
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
    print(f"Chat ID: {message.chat.id}")

    await message.answer(
        "Hi, it's Rustam's bot for Calculus I learning and helping.\n"
        "Please enter your name and surname:"
    )

    await state.set_state(Registration.waiting_for_name)

#syllabus section
@dp.message(lambda message: message.text == "Syllabus")
async def syllabus(message: Message):
    await message.answer_document(
        FSInputFile("files/syllabus_calc1.pdf")
    )
    await message.answer("The syllabus of mentorship is below:")
    await message.answer_document(
            FSInputFile("files/calc1_syllabus.docx")
        )

#books section
@dp.message(lambda message: message.text == "Books")
async def books(message: Message):
    await message.answer_document(
        FSInputFile("files/thomascalc14th.pdf")
    )

#cheat sheets section
@dp.message(lambda message: message.text == "Cheat Sheets")
async def cheats(message: Message):
    await message.answer_document(
        FSInputFile("files/sheet1.pdf")
    )

    await message.answer("List of integrals:")
    await message.answer_document(
        FSInputFile("files/integrals.png")
    )

    await message.answer("List of derivatives:")
    await message.answer_document(
        FSInputFile("files/derivatives.png")
    )


#results notify
mentor_id = 6322522318

@dp.message(Command("result"))
async def send_result(message: Message):

    if message.chat.id != mentor_id:
        return

    args = message.text.split(maxsplit=4)

    if len(args) < 5:
        await message.answer(
            "Usage:\n"
            "/result <student_id> <assignment> <score> <feedback>"
        )
        return

    student_id = args[1]
    assignment = args[2]
    score = args[3]
    feedback = args[4]

    if not student_id.isdigit():
        await message.answer("Student ID must be a number.")
        return

    try:
        score = float(score)
    except ValueError:
        await message.answer("Score must be a number.")
        return

    student_id = int(student_id)

    try:
        cur.execute(
            "SELECT chat_id FROM students WHERE id = %s",
            (student_id,)
        )

        student = cur.fetchone()

        if student is None:
            await message.answer("Student not found.")
            return

        chat_id = student[0]

        cur.execute("""
            INSERT INTO results(student_id, assignment, score, feedback)
            VALUES (%s, %s, %s, %s)
        """, (
            student_id,
            assignment,
            score,
            feedback
        ))

        connection.commit()

        await bot.send_message(
            chat_id,
            f""" {assignment}

Score: {score}

Feedback:
{feedback}"""
        )

        await message.answer("Result saved and sent successfully.")

    except Exception as e:
        connection.rollback()
        await message.answer(f"Error: {e}")


#meet notify
@dp.message(Command("notify"))
async def notify(message: Message):
    if message.chat.id != mentor_id:
        return

    text = message.text.replace("/notify" , "" , 1).strip()

    parts = text.split("|")

    if len(parts) != 4:
        await message.answer(
            "Usage:\n"
            "/notify <date> | <time> | <Online/Offline> | <Location or link>"
        )
        return

    date = parts[0].strip()
    time = parts[1].strip()
    format_ = parts[2].strip()
    location = parts[3].strip()

    cur.execute("""
        SELECT chat_id
        FROM students
        WHERE chat_id IS NOT NULL
    """)

    students = cur.fetchall()

    notification = (
        "Lesson notification!\n\n"
        f"Date: {date}\n"
        f"Time: {time}\n"
        f"Format: {format_}\n"
        f"Location: {location}"
    )

    sent = 0

    for (chat_id,) in students:
        try:
            await bot.send_message(chat_id, notification)
            sent += 1
        except Exception as e:
            print(f"Couldn't send to {chat_id}: {e}")

    await message.answer(f"Notification sent to {sent} students.")

#history of grades
@dp.message(lambda message: message.text == "My Results")
async def my_results(message: Message):

    try:
        cur.execute(
            "SELECT id FROM students WHERE chat_id = %s",
            (message.chat.id,)
        )

        student = cur.fetchone()

        if student is None:
            await message.answer(
                "You are not registered.\nUse /start first =)"
            )
            return

        student_id = student[0]

        cur.execute("""
            SELECT assignment, score, feedback
            FROM results
            WHERE student_id = %s
            ORDER BY created_at DESC
        """, (student_id,))

        results = cur.fetchall()

        if not results:
            await message.answer(
                "My Results\n\n"
                "No results yet."
            )
            return

        text = "My Results\n\n"

        for assignment, score, feedback in results:

            text += (
                f"{assignment}\n"
                f"Score: {score}\n"
                f"{feedback}\n\n"
            )

        await message.answer(text)

    except Exception as e:
        connection.rollback()
        await message.answer(f"Error: {e}")

#list of students
@dp.message(Command("students"))
async def students(message: Message):

    if message.chat.id != mentor_id:
        return

    try:
        cur.execute("""
            SELECT id, first_name, last_name
            FROM students
            ORDER BY id
        """)

        students = cur.fetchall()

        if not students:
            await message.answer("No students found.")
            return

        text = "The list of registered Students\n\n"

        for student_id, first_name, last_name in students:
            text += (
                f"ID: {student_id} | "
                f"{first_name} {last_name}\n"
            )

        await message.answer(text)

    except Exception as e:
        await message.answer(f"Error: {e}")

#history command
@dp.message(Command("history"))
async def history(message: Message):

    if message.chat.id != mentor_id:
        return

    args = message.text.split()

    if len(args) != 2:
        await message.answer("Usage:\n/history <student_id>")
        return

    if not args[1].isdigit():
        await message.answer("Student ID must be a number.")
        return

    student_id = int(args[1])

    try:
        cur.execute("""
            SELECT first_name, last_name
            FROM students
            WHERE id = %s
        """, (student_id,))

        student = cur.fetchone()

        if student is None:
            await message.answer("Student not found.")
            return

        first_name, last_name = student

        cur.execute("""
            SELECT assignment, score, feedback, created_at
            FROM results
            WHERE student_id = %s
            ORDER BY created_at DESC
        """, (student_id,))

        results = cur.fetchall()

        if not results:
            await message.answer(
                f"{first_name} {last_name}\n\n"
                "No results yet."
            )
            return

        text = f"{first_name} {last_name}\n\n"

        for assignment, score, feedback, created_at in results:
            text += (
                f"{assignment}\n"
                f"Score: {score}\n"
                f"{feedback}\n"
            )

        await message.answer(text)

    except Exception as e:
        connection.rollback()
        await message.answer(f"Error: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())