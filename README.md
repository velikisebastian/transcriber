# WolfTranscript

Видео и аудио в текст Markdown. Перетащите файл, подождите, заберите готовую расшифровку.

**Открыть: https://transcript.wolfcollab.space/**

Работает в Safari, Chrome и других браузерах на любом компьютере, ничего устанавливать не нужно. Распознавание делает [AssemblyAI](https://www.assemblyai.com), нужен ваш собственный API-ключ. Ключ запоминается только в вашем браузере, файл уходит напрямую в AssemblyAI и на наших серверах не хранится.

## Что умеет
- Загрузка нескольких файлов подряд: mp4, mov, mkv, mp3, m4a, wav и другие.
- Язык: автоопределение или явный выбор.
- Разделение по спикерам и метки времени, по желанию.
- Результат: файл `.md` с заголовком, длительностью, языком и абзацами.

## API-ключ
Ключ берётся здесь: https://www.assemblyai.com/dashboard/api-keys

## Программы для компьютера
Те же функции в виде программ: [Releases → latest](../../releases/latest)
- **Mac M1 и новее:** `Transkribator-mac.zip`
- **Mac на Intel и старые версии macOS:** `Transkribator-mac-old.zip` (упрощённый интерфейс). Программа не подписана Apple: на macOS 15 откройте «Системные настройки → Конфиденциальность и безопасность» и нажмите «Всё равно открыть».
- **Windows:** `Transkribator-windows.zip`, распаковать и запустить `Transkribator.exe`. Если Windows предупредит о неизвестном издателе: «Подробнее → Выполнить в любом случае».

## Запуск из исходников (Linux)
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

## Устройство
- `docs/` — веб-версия, один файл `index.html` без сборки и зависимостей.
- `core.py` — общая логика: загрузка, ожидание, сборка Markdown.
- `transcriber.py` — интерфейс на PySide6 (Linux, Windows, Mac M1+).
- `transcriber_tk.py` — упрощённый интерфейс на Tk для старых Mac.
- `.github/workflows/build.yml` — сборка программ и публикация релиза.

Сделано в [WolfTeam](https://wolfteam.one).
