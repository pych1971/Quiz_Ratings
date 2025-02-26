from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials

chromedriver_path = r'c:\chromedriver-win64\chromedriver.exe'

options = webdriver.ChromeOptions()
options.add_argument('--headless')

service = Service(executable_path=chromedriver_path)
driver = webdriver.Chrome(service=service, options=options)

# Google Sheets Setup
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_file('credentials.json', scopes=scopes)
gc = gspread.authorize(credentials)


def scrape_ratings(url, sheet_name):
    driver.get(url)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'rating-table')))

    current_page = 1
    data = [['Ранг', 'Команда', 'Игры', 'Баллы', 'Средние баллы за игру']]

    while True:
        print(f'Обработка страницы {current_page}')

        rows = driver.find_elements(By.CSS_SELECTOR, 'div.rating-table-row.flex-row')

        for row in rows:
            cells = row.find_elements(By.CSS_SELECTOR, 'div.rating-table-row-td1, div.rating-table-row-td2, div.rating-table-row-td3')

            if len(cells) == 3:
                rank_team_text = cells[0].text.split('.', 1)

                if len(rank_team_text) == 2:
                    games_played = int(cells[1].text.strip())
                    if games_played == 0:
                        continue

                    rank = rank_team_text[0].strip()
                    team_name = rank_team_text[1].strip()
                    points = float(cells[2].text.strip().replace(',', '.'))
                    avg_points = round(points / games_played, 2)

                    data.append([rank, team_name, games_played, points, avg_points])

        next_buttons = driver.find_elements(By.CSS_SELECTOR, 'ul.pagination li.next:not(.disabled) a')

        if next_buttons:
            next_page_link = next_buttons[0].get_attribute('href')
            driver.get(next_page_link)
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'rating-table')))
            current_page += 1
        else:
            print('Все страницы обработаны!')
            break

    # Сохранение данных в Google таблицу "Quiz" и закладки "Season" и "All"
    sheet = gc.open('Квиз').worksheet(sheet_name)
    sheet.clear()
    sheet.update(range_name='A1', values=data)


try:
    # Рейтинг за текущий сезон
    scrape_ratings('https://orenburg.quizplease.ru/rating?QpRaitingSearch[general]=0', 'Season')

    # Рейтинг за всё время
    scrape_ratings('https://orenburg.quizplease.ru/rating?QpRaitingSearch[general]=1', 'All')

finally:
    driver.quit()
