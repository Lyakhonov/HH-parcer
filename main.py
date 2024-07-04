import telebot
from telebot import types
import logging
import requests
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

db_config = {
    'dbname': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT')
}

params = {
            "area": 113,
            "per_page": 100
        }
current_id = ''
filters_res = ''
my_filter_flag = 0
request_flag = 0

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def create_table(conn):
    cur = conn.cursor()

    create_table_query = """
        CREATE TABLE IF NOT EXISTS vacancies (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200),
            area VARCHAR(50),
            company_name VARCHAR(200),
            experience VARCHAR(50),
            salary INTEGER,
            currency VARCHAR(10),
            url VARCHAR(200)
        )
    """
    cur.execute(create_table_query)
    conn.commit()
    cur.close()

    logging.info("Таблица 'vacancies' успешно создана.")


def remove_duplicates(conn):
    cur = conn.cursor()

    delete_duplicates_query = """
        DELETE FROM vacancies
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM vacancies
            GROUP BY url
        )
    """
    cur.execute(delete_duplicates_query)
    conn.commit()
    cur.close()

    logging.info("Дубликаты в таблице 'vacancies' успешно удалены.")


def insert_vacancies(conn, vacancy_title, vacancy_area,
                     company_name, vacancy_exp, vacancy_salary,
                     currency, vacancy_url):
    cur = conn.cursor()

    insert_query = """
                    INSERT INTO vacancies
                    (title, area, company_name, experience, salary,
                    currency, url) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """
    cur.execute(insert_query, (vacancy_title, vacancy_area,
                company_name, vacancy_exp, vacancy_salary,
                currency, vacancy_url))
    id = cur.fetchall()
    cur.close()
    return id[0][0]


def filter_vacancies(conn, filters_res):
    cur = conn.cursor()
    vacancies_list = []
    filter_query = "SELECT * FROM vacancies WHERE "
    filter_query += filters_res
    filter_query += "LIMIT 5"
    cur.execute(filter_query)
    vacancies = cur.fetchall()
    for vacancy in vacancies:
        res = f"Title: {vacancy[1]}\nArea: {vacancy[2]}\n"
        res += f"Company: {vacancy[3]}\nExperience: {vacancy[4]}\n"
        res += f"Salary: От {vacancy[5]} {vacancy[6]}\nURL: {vacancy[7]}\n\n"
        vacancies_list.append(res)
    cur.close()
    logging.info("Данные в таблице 'vacancies' по фильтрам успешно найдены.")
    return vacancies_list


bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Начать поиск по вакансиям',
                                      callback_data='form')
    btn2_msg = 'Отфильтровать вакансии из базы данных'
    btn2 = types.InlineKeyboardButton(btn2_msg, callback_data='all_filters')
    markup.add(btn1)
    markup.add(btn2)
    bot.send_message(message.chat.id,
                     'Вы можете найти подходящие для Вас вакансии.',
                     reply_markup=markup)


def experience(message):
    global params
    exp = message.text.strip()
    if exp.isdigit():
        if int(exp) == 0:
            params["experience"] = "noExperience"
        elif int(exp) >= 6:
            params["experience"] = ["moreThan6", "between1And3",
                                    "between3And6", "noExperience"]
        elif int(exp) < 6 and int(exp) >= 3:
            params["experience"] = ["between3And6", "between1And3",
                                    "noExperience"]
        else:
            params["experience"] = ["between1And3", "noExperience"]
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                          callback_data='send')
        markup.add(btn1, btn2)
        exp_msg = 'Опыт успешно записан. Выберете следующее действие'
        bot.send_message(message.chat.id, exp_msg, reply_markup=markup)
    else:
        err = 'Неверный ввод. Введите Ваш опыт работы целым чилом в годах'
        err += ' или перейдите к другим полям запроса'
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Перейти к составленю запроса',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Указать опыт',
                                          callback_data='experience')
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, err, reply_markup=markup)


def profession(message):
    global params
    profession = message.text.strip()
    if "text" in params:
        params["text"] += f" {profession}"
    else:
        params["text"] = profession
    prof_msg = 'Опыт успешно записан. Выберете следующее действие'
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                      callback_data='form')
    btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                      callback_data='send')
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, prof_msg, reply_markup=markup)


def employment(message):
    global params
    flag = True
    employments = message.text.split(',')
    employments_list = []
    emp_list = [j.strip().lower() for j in employments]
    for emp in emp_list:
        if emp == 'полная':
            employments_list.append("full")
        elif emp == 'частичная':
            employments_list.append("part")
        elif emp == 'проектная':
            employments_list.append("project")
        elif emp == 'волонтерство':
            employments_list.append("volunteer")
        elif emp == 'стажировка':
            employments_list.append("probation")
        else:
            err = 'Неверный ввод. Укажите через запятую типы занятости'
            err += ' одним словом или перейдите к другим полям запроса'
            markup = types.InlineKeyboardMarkup()
            btn1 = types.InlineKeyboardButton('Перейти к составленю запроса',
                                              callback_data='form')
            btn2 = types.InlineKeyboardButton('Указать тип занятости',
                                              callback_data='employment')
            markup.add(btn1, btn2)
            bot.send_message(message.chat.id, err, reply_markup=markup)
            flag = False
    if flag:
        employments_set_list = list(set(employments_list))
        params["employment"] = employments_set_list
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                          callback_data='send')
        markup.add(btn1, btn2)
        exp_msg = 'Тип занятости успешно записан. Выберете следующее действие'
        bot.send_message(message.chat.id, exp_msg, reply_markup=markup)


def salary(message):
    global params
    salary = message.text.strip()
    if salary.isdigit():
        params["salary"] = salary
        params["only_with_salary"] = "True"
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                          callback_data='send')
        markup.add(btn1, btn2)
        exp_msg = 'Заработная плата записана. Выберете следующее действие'
        bot.send_message(message.chat.id, exp_msg, reply_markup=markup)
    else:
        err = 'Неверный ввод. Введите зраработную плату числом'
        err += ' или перейдите к другим полям запроса'
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Перейти к составленю запроса',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Указать зарплату',
                                          callback_data='salary')
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, err, reply_markup=markup)


def city(message):
    global params
    city = message.text.strip().capitalize()
    if "text" in params:
        params["text"] += f" {city}"
    else:
        params["text"] = city
    city_msg = 'Город успешно записан. Выберете следующее действие'
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                      callback_data='form')
    btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                      callback_data='send')
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, city_msg, reply_markup=markup)


def temporary(message):
    global params
    temp = message.text.strip().lower()
    if temp == 'да':
        params["accept_temporary"] = "True"
        temp_msg = 'Будут подобраны вакансии только временной работы. '
        temp_msg += 'Выберете следующее действие'
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Добавить другие поля',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                          callback_data='send')
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, temp_msg, reply_markup=markup)
    else:
        temp_msg = 'Возможно неверный ввод. Нажмите "Указать временность работ'
        temp_msg += 'ы" и введите "Да", если Вас интересуют вакансии '
        temp_msg += 'временной работы или перейдите к другим полям запроса.'
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Перейти к составленю запроса',
                                          callback_data='form')
        btn2 = types.InlineKeyboardButton('Указать временность работы',
                                          callback_data='temporary')
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, temp_msg, reply_markup=markup)


def salary_flt(message):
    global filters_res
    filter_salary = message.text.strip()
    if filter_salary.isdigit():
        if filters_res != '':
            filters_res += f"AND salary > {filter_salary} "
        else:
            filters_res += f"salary > {filter_salary} "
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Добавить другие фильтры',
                                          callback_data='all_filters')
        btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                          callback_data='filters_send')
        markup.add(btn1, btn2)
        exp_msg = 'Заработная плата записана. Выберете следующее действие'
        bot.send_message(message.chat.id, exp_msg, reply_markup=markup)
    else:
        err = 'Неверный ввод. Введите зраработную плату числом'
        err += ' или перейдите к другим полям фильтрации.'
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Перейти к другим полям фильтрации',
                                          callback_data='filters')
        btn2 = types.InlineKeyboardButton('Указать зарплату',
                                          callback_data='salary_flt')
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, err, reply_markup=markup)


def city_flt(message):
    global filters_res
    filter_city = message.text.strip().capitalize()
    if filters_res != '':
        filters_res += f"AND area = '{filter_city}' "
    else:
        filters_res += f"area = '{filter_city}' "
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Добавить другие фильтры',
                                      callback_data='all_filters')
    btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                      callback_data='filters_send')
    markup.add(btn1, btn2)
    city_msg = 'Город записан. Выберете следующее действие'
    bot.send_message(message.chat.id, city_msg, reply_markup=markup)


def prof_flt(message):
    global filters_res
    filter_prof = message.text.strip().lower()
    if filters_res != '':
        filters_res += "AND CONCAT(' ', LOWER(title), ' ') "
        filters_res += f"LIKE '% {filter_prof} %' "
    else:
        filters_res += "CONCAT(' ', LOWER(title), ' ') "
        filters_res += f"LIKE '% {filter_prof} %' "
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton('Добавить другие фильтры',
                                      callback_data='all_filters')
    btn2 = types.InlineKeyboardButton('Сформировать запрос',
                                      callback_data='filters_send')
    markup.add(btn1, btn2)
    city_msg = 'Профессия записана. Выберете следующее действие'
    bot.send_message(message.chat.id, city_msg, reply_markup=markup)


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    global current_id
    global filters_res
    global my_filter_flag
    global request_flag
    if callback.data == 'start':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Начать поиск по вакансиям',
                                          callback_data='form')
        btn2_msg = 'Отфильтровать вакансии из базы данных'
        btn2 = types.InlineKeyboardButton(btn2_msg,
                                          callback_data='all_filters')
        markup.add(btn1)
        markup.add(btn2)
        bot.send_message(callback.message.chat.id,
                         'Вы можете найти подходящие для Вас вакансии.',
                         reply_markup=markup)

    if callback.data == 'form':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Опыт',
                                          callback_data='experience')
        btn2 = types.InlineKeyboardButton('Профессия',
                                          callback_data='profession')
        btn3 = types.InlineKeyboardButton('Тип занятости',
                                          callback_data='employment')
        btn4 = types.InlineKeyboardButton('Зарплата',
                                          callback_data='salary')
        btn5 = types.InlineKeyboardButton('Город',
                                          callback_data='city')
        btn6 = types.InlineKeyboardButton('Временная работа',
                                          callback_data='temporary')
        markup.add(btn2, btn1)
        markup.add(btn3, btn4)
        markup.add(btn5, btn6)
        form_msg = 'Выберите поля для формирования запроса.'
        bot.send_message(callback.message.chat.id,
                         form_msg, reply_markup=markup)

    if callback.data == 'experience':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        exp_message = 'Укажите опыт работы в годах.Если его нет, напишите 0.'
        bot.send_message(callback.message.chat.id, exp_message)
        bot.register_next_step_handler(callback.message, experience)

    if callback.data == 'profession':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        prof_message = 'Укажите желаемую професссию или должность'
        bot.send_message(callback.message.chat.id, prof_message)
        bot.register_next_step_handler(callback.message, profession)

    if callback.data == 'employment':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        emp_message = 'Укажите тип занятости: Полная, частичная, '
        emp_message += 'проектная, волонтерство или стажировка. '
        emp_message += 'Можно указать несколько значений через запятую.'
        bot.send_message(callback.message.chat.id, emp_message)
        bot.register_next_step_handler(callback.message, employment)

    if callback.data == 'salary':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        sal_message = 'Укажите размер заработной числом платы в рублях.'
        bot.send_message(callback.message.chat.id, sal_message)
        bot.register_next_step_handler(callback.message, salary)

    if callback.data == 'city':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        city_message = 'Укажите город.'
        bot.send_message(callback.message.chat.id, city_message)
        bot.register_next_step_handler(callback.message, city)

    if callback.data == 'temporary':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        temp_message = 'Напишите "Да", если Вас интересуют '
        temp_message += 'вакансии временной работы'
        bot.send_message(callback.message.chat.id, temp_message)
        bot.register_next_step_handler(callback.message, temporary)

    if callback.data == 'send':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        global params
        try:
            conn = psycopg2.connect(**db_config)
            create_table(conn)
            logging.info("Подключение для отправки сообщения установлено.")
        except Exception as err:
            logging.info("Не удалось установить подключение к БД.")
            logging.info(err)
            markup = types.InlineKeyboardMarkup()
            btn_msg = 'Сформировать новый запрос на поиск'
            btn1 = types.InlineKeyboardButton(btn_msg, callback_data='start')
            markup.add(btn1)
            bot.send_message(callback.message.chat.id,
                             'Извините, произошла внутренняя ошибка.',
                             reply_markup=markup)

        url = "https://api.hh.ru/vacancies"
        headers = {
            "Authorization": f"Bearer {os.getenv('API_TOKEN')}",
        }
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            res = ''
            vacancies_list = []
            data = response.json()
            vacancies = data.get("items", [])
            if vacancies != []:
                for vacancy in vacancies:
                    vacancy_title = vacancy["name"]
                    vacancy_area = vacancy["area"]["name"]
                    if vacancy["experience"]["name"] is not None:
                        vacancy_exp = vacancy["experience"]["name"]
                    else:
                        vacancy_exp = 'None'
                    if (vacancy["salary"] is not None) and (
                         vacancy["salary"]["from"] is not None):
                        vacancy_salary = f'{vacancy["salary"]["from"]}'
                        currency = f'{vacancy["salary"]["currency"]}'
                    else:
                        vacancy_salary = None
                        currency = ''
                    vacancy_url = vacancy["alternate_url"]
                    company_name = vacancy["employer"]["name"]
                    res = f"Title: {vacancy_title}\nArea: {vacancy_area}\n"
                    res += f"Company: {company_name}\n"
                    res += f"Experience: {vacancy_exp}\n"
                    res += f"Salary: От {vacancy_salary} {currency}\n"
                    res += f"URL: {vacancy_url}\n\n"
                    vacancies_list.append(res)
                    last_id = insert_vacancies(conn, vacancy_title,
                                               vacancy_area, company_name,
                                               vacancy_exp, vacancy_salary,
                                               currency, vacancy_url)
                for vacancy in vacancies_list[:5]:
                    bot.send_message(callback.message.chat.id, vacancy)
                current_id = f'{last_id - 100}'
                markup = types.InlineKeyboardMarkup()
                btn1_msg = 'Сформировать новый запрос на поиск'
                btn2_msg = 'Установить фильтры'
                btn1 = types.InlineKeyboardButton(btn1_msg,
                                                  callback_data='start')
                btn2 = types.InlineKeyboardButton(btn2_msg,
                                                  callback_data='choose_field')
                markup.add(btn1)
                markup.add(btn2)
                bot.send_message(callback.message.chat.id,
                                 'Выберите следующие действие',
                                 reply_markup=markup)
                remove_duplicates(conn)
                request_flag = 1
            else:
                markup = types.InlineKeyboardMarkup()
                btn_msg = 'Сформировать новый запрос на поиск'
                btn1 = types.InlineKeyboardButton(btn_msg,
                                                  callback_data='start')
                markup.add(btn1)
                not_found = 'Извинте, по запросу ничего не нашлось.'
                not_found += 'Попробуйте ввести другие поля для запроса.'
                bot.send_message(callback.message.chat.id, not_found,
                                 reply_markup=markup)

        else:
            logging.info(f"Ошибка запроса: {response.status_code}")
            markup = types.InlineKeyboardMarkup()
            btn_msg = 'Сформировать новый запрос на поиск'
            btn1 = types.InlineKeyboardButton(btn_msg, callback_data='start')
            markup.add(btn1)
            bot.send_message(callback.message.chat.id,
                             'Извините, произошла внутренняя ошибка.',
                             reply_markup=markup)
        params = {
            "area": 113,
            "per_page": 100
        }
        conn.close()

    if callback.data == 'my_filters':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        my_filter_flag = 1
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Минимальная зарплата',
                                          callback_data='salary_flt')
        btn2 = types.InlineKeyboardButton('Город',
                                          callback_data='city_flt')
        btn3 = types.InlineKeyboardButton('Профессия',
                                          callback_data='profession_flt')
        markup.add(btn1)
        markup.add(btn2)
        markup.add(btn3)
        bot.send_message(callback.message.chat.id,
                         'Выберите фильтр',
                         reply_markup=markup)

    if callback.data == 'all_filters':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton('Минимальная зарплата',
                                          callback_data='salary_flt')
        btn2 = types.InlineKeyboardButton('Город',
                                          callback_data='city_flt')
        btn3 = types.InlineKeyboardButton('Профессия',
                                          callback_data='profession_flt')
        markup.add(btn1)
        markup.add(btn2)
        markup.add(btn3)
        bot.send_message(callback.message.chat.id,
                         'Выберите фильтр',
                         reply_markup=markup)

    if callback.data == 'choose_field':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        markup = types.InlineKeyboardMarkup()
        btn2_msg = 'Установить фильтры на текущий запрос'
        btn3_msg = 'Установить фильтры на всю базу данных'
        btn2 = types.InlineKeyboardButton(btn2_msg,
                                          callback_data='my_filters')
        btn3 = types.InlineKeyboardButton(btn3_msg,
                                          callback_data='all_filters')
        if request_flag:
            markup.add(btn2)
        markup.add(btn3)
        bot.send_message(callback.message.chat.id,
                         'Выберите следующие действие',
                         reply_markup=markup)

    if callback.data == 'salary_flt':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        sal_message = 'Укажите минимальный размер заработной платы числом.'
        bot.send_message(callback.message.chat.id, sal_message)
        bot.register_next_step_handler(callback.message, salary_flt)

    if callback.data == 'city_flt':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        city_message = 'Укажите город.'
        bot.send_message(callback.message.chat.id, city_message)
        bot.register_next_step_handler(callback.message, city_flt)

    if callback.data == 'profession_flt':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        prof_message = 'Укажите желаемую професссию или должность.'
        bot.send_message(callback.message.chat.id, prof_message)
        bot.register_next_step_handler(callback.message, prof_flt)

    if callback.data == 'filters_send':
        bot.delete_message(callback.message.chat.id,
                           callback.message.message_id)
        try:
            conn = psycopg2.connect(**db_config)
            logging.info("Подключение к БД для фильтров установлено.")
        except Exception as err:
            logging.info("Не удалось установить подключение к БД.")
            logging.info(err)
            markup = types.InlineKeyboardMarkup()
            btn_msg = 'Сформировать новый запрос на поиск'
            btn1 = types.InlineKeyboardButton(btn_msg, callback_data='start')
            markup.add(btn1)
            bot.send_message(callback.message.chat.id,
                             'Извините, произошла внутренняя ошибка.',
                             reply_markup=markup)
        if my_filter_flag:
            filters_res += f"AND id > {current_id} "
        vacancies_list = filter_vacancies(conn, filters_res)
        if vacancies_list != []:
            for vacancy in vacancies_list:
                bot.send_message(callback.message.chat.id, vacancy)
            markup = types.InlineKeyboardMarkup()
            btn1_msg = 'Сформировать новый запрос на поиск'
            btn2_msg = 'Установить новые фильтры'
            btn1 = types.InlineKeyboardButton(btn1_msg,
                                              callback_data='start')
            btn2 = types.InlineKeyboardButton(btn2_msg,
                                              callback_data='choose_field')
            markup.add(btn1)
            markup.add(btn2)
            bot.send_message(callback.message.chat.id,
                             'Выберите следующие действие',
                             reply_markup=markup)
        else:
            btn1_msg = 'Сформировать новый запрос на поиск'
            markup = types.InlineKeyboardMarkup()
            btn1 = types.InlineKeyboardButton(btn1_msg,
                                              callback_data='start')
            btn2 = types.InlineKeyboardButton('Задать новые фильтры',
                                              callback_data='choose_field')
            markup.add(btn1)
            markup.add(btn2)
            not_found_msg = 'По заданным фильтрам ничего не найдено. '
            not_found_msg += 'Возможно, база данных пуста и Вам следует сдела'
            not_found_msg += 'ть пару запросов для начала. '
            not_found_msg += 'Выберите следующее действие.'
            bot.send_message(callback.message.chat.id, not_found_msg,
                             reply_markup=markup)

        filters_res = ''
        my_filter_flag = 0

        conn.close()


bot.polling(non_stop=True)
