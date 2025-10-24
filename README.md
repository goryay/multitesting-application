# MWR (Multi-Workload Runner)

MWR (Multi-Workload Runner) — это десктопное приложение, разработанное для автоматизации тестирования различных компонентов системы. Программа позволяет пользователю выбирать и запускать несколько стресс-тестов для оценки стабильности и производительности компьютера или сервера.

## Основные функции:

- **Выбор тестов:** Пользователь может выбрать один или несколько тестов для запуска, включая Aida Business, Furmark, Fio.
- **Автоматическое определение GPU:** Программа автоматически определяет наличие дискретной видеокарты и включает или отключает стресс-тест GPU в зависимости от этого.
- **Управление временем тестирования:** Пользователь может установить продолжительность тестирования (не менее 12 часов).
- **Принудительное завершение:** Возможность принудительно завершить все тесты с предупреждением.
- **Создание скриншотов:** Перед завершением тестов программа автоматически создает скриншоты работающих приложений.

## Как это работает:

1. **Выбор тестов:** Пользователь выбирает, какие тесты он хочет запустить, используя чекбоксы в интерфейсе.
2. **Установка времени:** Пользователь указывает продолжительность тестирования в часах.
3. **Запуск тестов:** После нажатия кнопки "Запустить тестирование" выбранные тесты начинают выполняться.
4. **Мониторинг и завершение:** Пользователь может в любой момент принудительно завершить тестирование, после чего будут созданы скриншоты.

## Требования:

- Python 3.x
- Библиотеки: `tkinter`, `subprocess`, `threading`, `PIL`, `GPUtil`
- Установленные программы для тестирования: Aida64, Furmark, Fio

## Установка и запуск:

1. Установите необходимые библиотеки:
```bash
   pip install pillow gputil
```
2. Скачайте или скопируйте файлы проекта.
3. Запустите программу с помощью команды:
```bash
   python main.py
```

---

### 🚀 Сборка готового приложения

Для создания переносимой версии приложения:

1. Убедитесь, что используется **64-битная версия Python 3.12**.  
   Проверка:
```bash
   python -c "import platform; print(platform.architecture())"
```
   Должен вернуть `('64bit', ...)`.

2. Установите зависимости:
```bash
   pip install -r requirements.txt
```

3. Установите `pyinstaller`:
```bash
   pip install pyinstaller
```

4. Выполните сборку:
```bash
   pyinstaller main.py --onefile --noconfirm `
  --add-data "SoftForTest;SoftForTest" `
  --add-data "aida_fio_furmark.ps1;." `
  --add-data "install_dependencies.ps1;." `
  --add-data "smart.ps1;." `
  --hidden-import pyautogui `
  --hidden-import pygetwindow `
  --hidden-import pyscreeze `
  --hidden-import mss `
  --hidden-import pymsgbox `
  --hidden-import pytweening `
  --hidden-import mouseinfo `
  --hidden-import pyperclip `
  --hidden-import pillow `
  --hidden-import psutil
```
OR

```bash
pyinstaller --noconfirm --onefile --windowed `    
 --add-data "screen.py;." `                                                                                                                                                                                                       
 --add-data "aida_fio_furmark.ps1;." `                                                                                                                                                                                            
 --add-data "Generate_SoftwareReport.ps1;." `                                                                                                                                                                                     
 --add-data "smart.ps1;." `                                                                                                                                                                                                       
 --add-data "AllUnin.ps1;." `                                                                                                                                                                                                     
 --add-data "install_dependencies.ps1;." `                                                                                                                                                                                        
 --add-data "SoftForTest;SoftForTest" `                                                                                                                                                                                           
 main.py
```

5. После сборки:
   - В папку `dist` **необходимо вручную добавить каталог `SoftForTest`**, содержащий AIDA64, FurMark и т.п.
   - В `dist` будет лежать `main.exe` — готовое к запуску приложение.

---

### 📸 Скриншоты окон тестирования

Скрипт `screen.py` делает снимки только тех окон, которые соответствуют ключевым словам:  
`aida64`, `furmark`, `fio`, `cmd.exe`, `System Stability Test`, `FurMark`.

**Пример использования (автоматически вызывается в конце теста):**
```bash
python screen.py
```

Скриншоты сохраняются в:
```
C:\\Users\\<Имя>\\Desktop\\Report\\<Имя ПК>\\
```

---

### ⚠️ Требования к структуре проекта

Для корректной работы приложения необходимо:

```
multitesting-application/
├── dist/
│   ├── main.exe
│   └── SoftForTest/
│       ├── AIDA64/
│       │   └── AIDA64Port.exe
│       └── FurMark/
│           └── furmark.exe
├── screen.py
├── main.py
├── aida_fio_furmark.ps1
├── smart.ps1
├── requirements.txt
```
