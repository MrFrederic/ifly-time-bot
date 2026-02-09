class Messages:
    # Buy Handler
    BTN_YES_REPLACE = "Да, заменить"
    MSG_EXISTING_REQUEST = "⚠️ У вас уже есть запрос на {hours}.\nХотите изменить его?"
    
    BTN_IMMEDIATE = "Сразу"
    BTN_CANCEL = "Отмена"
    MSG_SELECT_DATE = (
        "📅 Когда вы сможете распилить пакет?\n\n"
        "*Напишите дату* (например, '25.11' или '25.11.2025') или *выберите 'Сразу'*."
    )
    ERR_INVALID_DATE = "❌ Неверный формат даты (ДД.ММ или ДД.ММ.ГГГГ)"
    
    MSG_SELECT_HOURS = (
        "⏱ Сколько часов?\n\n"
        "• Выберите вариант ниже\n"
        "• Или *введите значение* (например, '1.5' или '1.5-2')"
    )
    ERR_HOURS_MULTIPLE = "❌ Часы должны быть кратны 0.5"
    ERR_INVALID_HOURS = "❌ Неверный формат ('1.5' или '1.5-2')"
    
    MSG_REQUEST_SAVED = (
        "✅ Новый запрос!\n"
        "{user_name} хочет взять {hours_str} часа."
    )
    MSG_REQUEST_SAVED_DATE = "\nНе ранее {date_str}."
    MSG_REQUEST_SAVED_GROUP = "\n\nВам придет уведомление, когда пакет будет распилен"
    MSG_REQUEST_SAVED_TIP = "\n💡 Tip: используйте /cancel для удаления вашего запроса"
    MSG_GROUP_FOUND = "🪚 *Пакет распилен!* 🪚\n\n{users_text}\n\nПожалуйста, создайте отдельный чат и договоритесь об оплате."
    ERR_SAVE_REQUEST = "❌ Ошибка при сохранении запроса."
    # Cancel Handler
    MSG_CANCELLED = "✅ Ваш запрос был отменен."
    MSG_NO_ACTIVE_REQUEST = "У вас нет активных запросов. Создайте новый с помощью /buy."

    # Status Handler
    MSG_NO_REQUESTS = "Нет активных запросов на распил.\nИспользуйте /buy чтобы создать новый."
    MSG_CURRENT_REQUESTS_HEADER = "📋 *Текущие запросы:*"

    # Hour Options Labels
    OPT_1H = "1ч"
    OPT_1_5H = "1.5ч"
    OPT_2H = "2ч"
    OPT_2_5H = "2.5ч"
    OPT_3H = "3ч"
    OPT_1_2H = "1-2ч"
    OPT_2_3H = "2-3ч"
    OPT_3_5H = "3-5ч"
