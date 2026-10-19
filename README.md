# Транскрибатор

Видео и аудио → текст в Markdown через [AssemblyAI](https://www.assemblyai.com).
Перетащите файл в окно, выберите папку для результатов — получите `.md`.

## WolfTranscript в браузере (самый надёжный способ, особенно для Mac)
https://transcript.wolfcollab.space/ (запасной адрес: https://velikisebastian.github.io/transcriber/) — ничего устанавливать не нужно, работает в Safari и Chrome на любом компьютере. Ключ AssemblyAI запоминается в самом браузере.

## Скачать программу
Готовые программы: [Releases → latest](../../releases/latest)
- **Mac M1 и новее** (Apple Silicon): `Transkribator-mac.zip`.
- **Старые Mac / Intel**: `Transkribator-mac-old.zip` (упрощённый интерфейс, запускается на старых версиях macOS). Первый запуск: правой кнопкой → «Открыть».
- **Windows**: `Transkribator-windows.zip`, распаковать и запустить `Transkribator.exe`. Если Windows предупредит о неизвестном издателе: «Подробнее» → «Выполнить в любом случае».

## API-ключ
Нужен собственный ключ AssemblyAI: https://www.assemblyai.com/dashboard/api-keys
Вставьте его в поле «API-КЛЮЧ» один раз, он запомнится на вашем компьютере.

## Запуск из исходников (Linux)
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

## Выкладка сайта на поддомен
`python deploy_sftp.py` (пароль SFTP берётся из `~/.wolfcollab_sftp` или переменной `WOLFCOLLAB_SFTP_PASS`, в репозитории его нет). Новая папка `sites/transcript`, существующие сайты не трогаются; обновление — с `--force`. Сертификат на поддомен выдаётся сам через 1–2 минуты после первого обращения.
