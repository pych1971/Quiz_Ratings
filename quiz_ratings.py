import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from google.oauth2.service_account import Credentials

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Константы (селекторы и т.д.)
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH', 'credentials.json')
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

RATING_TABLE_CLASS = 'rating-table'
ROW_SELECTOR = 'div.rating-table-row.flex-row'
CELL_SELECTOR = 'div.rating-table-row-td1, div.rating-table-row-td2, div.rating-table-row-td3'
NEXT_BUTTON_SELECTOR = 'ul.pagination li.next:not(.disabled) a'

MAX_RETRIES = 3


def init_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        prefs = {"profile.managed_default_content_settings.images": 2,
                 "profile.managed_default_content_settings.stylesheets": 2}
        options.add_experimental_option("prefs", prefs)

    service = Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)
    return driver


def init_gspread():
    credentials = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    return gspread.authorize(credentials)


def scrape_ratings(driver, gc, url, sheet_name):
    retries = MAX_RETRIES
    for attempt in range(retries):
        try:
            driver.get(url)
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, RATING_TABLE_CLASS)))
            break
        except Exception as e:
            logging.error(f'Ошибка загрузки страницы {url}, попытка {attempt + 1}: {e}')
            if attempt == retries - 1:
                logging.error('Максимальное количество попыток исчерпано. Переход к следующей странице.')
                return

    current_page = 1
    data = [['Ранг', 'Команда', 'Игры', 'Баллы', 'Средние баллы за игру']]

    while True:
        logging.info(f'Обработка страницы {current_page}')
        rows = driver.find_elements(By.CSS_SELECTOR, ROW_SELECTOR)

        for row in rows:
            cells = row.find_elements(By.CSS_SELECTOR, CELL_SELECTOR)
            if len(cells) != 3:
                continue

            rank_team_text = cells[0].text.split('.', 1)
            if len(rank_team_text) != 2:
                continue

            try:
                games_played = int(cells[1].text.strip())
                if games_played == 0:
                    continue

                rank = rank_team_text[0].strip()
                team_name = rank_team_text[1].strip()
                points = float(cells[2].text.strip().replace(',', '.'))
                avg_points = round(points / games_played, 2)

                data.append([rank, team_name, games_played, points, avg_points])
            except ValueError as ve:
                logging.warning(f'Ошибка парсинга строки на странице {current_page}: {ve}')
                continue

        next_buttons = driver.find_elements(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)
        if next_buttons:
            next_page_link = next_buttons[0].get_attribute('href')
            driver.get(next_page_link)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, RATING_TABLE_CLASS)))
            current_page += 1
        else:
            logging.info('Все страницы обработаны.')
            break

    try:
        sheet = gc.open('Квиз').worksheet(sheet_name)
        sheet.clear()
        sheet.update('A1', data)
        logging.info(f'Данные успешно загружены в лист "{sheet_name}"')
    except Exception as e:
        logging.error(f'Ошибка записи в Google Sheets: {e}')


def main():
    driver = init_driver(headless=True)
    gc = init_gspread()

    urls_and_sheets = [
        ('https://orenburg.quizplease.ru/rating?QpRaitingSearch[general]=0', 'Season'),
        ('https://orenburg.quizplease.ru/rating?QpRaitingSearch[general]=1', 'All')
    ]

    for url, sheet_name in urls_and_sheets:
        scrape_ratings(driver, gc, url, sheet_name)

    driver.quit()


if __name__ == "__main__":
    main()
