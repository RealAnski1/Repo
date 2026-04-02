"""
Интерактивный CLI для работы с REST API.

Запустите сервер:  python __init__.py
Затем этот файл:   python api_example.py

Доступные команды:
    profiles                  — все пользователи
    profile <id>              — профиль пользователя
    messages                  — все сообщения чата
    message <id>              — одно сообщение чата
    help                      — список команд
    exit / quit               — выход
"""

import json
import urllib.request
import urllib.error

BASE_URL = 'http://127.0.0.1:5000/api'

HELP = """
Команды:
  profiles              — список всех пользователей
  profile <id>          — профиль пользователя по ID
  messages              — все сообщения чата
  message <id>          — сообщение чата по ID
  help                  — эта справка
  exit                  — выход
"""


def get(path: str):
    url = BASE_URL + path
    try:
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        return body, e.code
    except urllib.error.URLError as e:
        print(f'  Ошибка подключения: {e.reason}')
        print('  Убедитесь, что сервер запущен: python __init__.py')
        return None, 0


def pretty(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def cmd_profiles():
    data, status = get('/profile')
    if data is None:
        return
    if status != 200:
        print(f'  Ошибка {status}: {data}')
        return
    print(f'Пользователей: {len(data)}')
    print(f'  {"ID":<5} {"Имя":<20} {"Админ":<7} {"Забанен":<8} {"Сообщ.":<8} {"Репут."}')
    print('  ' + '-' * 60)
    for u in data:
        print(f'  {u["id"]:<5} {u["username"]:<20} {"да" if u["admin"] else "нет":<7} '
              f'{"да" if u["is_banned"] else "нет":<8} {u["messages_count"]:<8} {u["reputation"]}')


def cmd_profile(user_id: str):
    if not user_id.isdigit():
        print('  Укажите числовой ID. Пример: profile 1')
        return
    data, status = get(f'/profile/{user_id}')
    if data is None:
        return
    if status != 200:
        print(f'  Ошибка {status}: {data.get("error", data)}')
        return
    print(pretty(data))


def cmd_messages():
    data, status = get('/community')
    if data is None:
        return
    if status != 200:
        print(f'  Ошибка {status}: {data}')
        return
    print(f'Сообщений: {len(data)}')
    print(f'  {"ID":<5} {"Автор":<20} {"Лайки":<7} {"Дата":<18} Текст')
    print('  ' + '-' * 75)
    for m in data:
        preview = m['text'][:35].replace('\n', ' ')
        print(f'  {m["id"]:<5} {m["username"]:<20} {m["likes"]:<7} {m["created_formatted"]:<18} {preview}')


def cmd_message(message_id: str):
    if not message_id.isdigit():
        print('  Укажите числовой ID. Пример: message 1')
        return
    data, status = get(f'/community/{message_id}')
    if data is None:
        return
    if status != 200:
        print(f'  Ошибка {status}: {data.get("error", data)}')
        return
    print(pretty(data))


def run():
    print('API CLI — введите "help" для списка команд, "exit" для выхода.')
    while True:
        try:
            raw = input('\n> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nВыход.')
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ''

        if cmd in ('exit', 'quit'):
            print('Выход.')
            break
        elif cmd == 'help':
            print(HELP)
        elif cmd == 'profiles':
            cmd_profiles()
        elif cmd == 'profile':
            cmd_profile(arg)
        elif cmd == 'messages':
            cmd_messages()
        elif cmd == 'message':
            cmd_message(arg)
        else:
            print(f'  Неизвестная команда: "{cmd}". Введите "help".')


if __name__ == '__main__':
    run()
