# Транскрибатор

Видео и аудио → текст в Markdown через [AssemblyAI](https://www.assemblyai.com).
Перетащите файл в окно, выберите папку для результатов — получите `.md`.

## Скачать
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
