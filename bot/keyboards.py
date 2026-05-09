from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def mcq_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("A", callback_data="A"),
        InlineKeyboardButton("B", callback_data="B"),
        InlineKeyboardButton("C", callback_data="C"),
        InlineKeyboardButton("D", callback_data="D"),
    ]])


def rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("1 – No idea", callback_data="1"),
        InlineKeyboardButton("2 – Hard", callback_data="2"),
    ], [
        InlineKeyboardButton("3 – Good", callback_data="3"),
        InlineKeyboardButton("4 – Easy", callback_data="4"),
    ]])


def got_it_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Got it! Quiz me ✏️", callback_data="got_it"),
    ]])


def continue_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Continue to lessons →", callback_data="continue"),
    ]])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Save", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Cancel", callback_data="confirm_no"),
    ]])
