# TimeTracker - Руководство пользователя

## Содержание
1. [Установка и запуск программы](#-установка)  
2. [Интерфейс](#-интерфейс)  
3. [Основные функции](#-основные-функции)  
4. [Экспорт данных](#-экспорт-данных)  

---

## 🚀 Установка

### Требования
- **Операционная система**: Windows 10/11 (поддержка Linux/macOS в разработке)
- **Python**: версия 3.9 или новее
- **Зависимости**:
  ```bash
  pip install pystray Pillow openpyxl

## 🚀 Запуск программы

### Для Windows:
1. **Скачайте** файл `TimeTracker.py` из репозитория.
2. **Откройте командную строку**:
   - Нажмите `Win + R`, введите `cmd`, нажмите Enter.
3. **Перейдите в папку с программой**:
   ```bash
   cd C:\Путь\к\папке\с\программой
4. **Запустите программу**:
   ```bash
   python TimeTracker.py
5. **Примечание**:
Для использования программы в фоновом режиме (без консоли терминала, только GUI) запускайте приложение через команду:
	```bash
	pythonw TimeTracker.py  # Только для Windows


## 🖥 Интерфейс

### Основные элементы:
1. **Поле "Логин"**
Введите ваш уникальный идентификатор (логин на Стаффе) для отчетов.
2. **Форма создания задачи:**
- **Регресс**: поверхность.
- **Название**: Название рана (в квадратных скобках перед ссылкой на ран)
- **Ссылка**: URL рана
- **Доп. время**: Создает задачу для сопутствующих работ с пометкой [ДОП]. Создаём, если во время выполнения задачи могут возникнуть моменты, которые замедляют прохождение (настройка оборудования, проблемы с сетью и пр.)
3. **Список задач**

| ID | Регресс      | Название          | Статус     | Время  |
|----|--------------|-------------------|------------|--------|
| 1  | Тестирование | Проверка логина   | ▶ Активна | 1:15:00 |

4. **Панель управления**:

- 🗑️ **Удалить** — удаляет выбранную задачу.
- ⏳ **Общее время** — суммарное время всех задач.
- ⏸️ **Пауза** — останавливает все таймеры.
- ▶️ **Продолжить** — возобновляет трекинг.
- ✅ **Завершить день** — экспортирует данные и закрывает программу.

## 📌 Основные функции

**Создание задачи**
1. Заполните все поля в разделе **"Новая задача"**.
2. Нажмите кнопку **"Добавить"**.
3. При активации чекбокса **"Доп. время"**:
	+ Создается дополнительная задача с префиксом `[ДОП]`.

**Управление временем**
- **Старт трекера**: Кликните на задачу в списке.
- **Пауза**: Остановите все таймеры кнопкой ⏸️.
- **Переключение задач**: Новый клик = автоматическое сохранение времени предыдущей задачи.
- **Общее время**: Отображается в формате ЧЧ:ММ:СС (обновляется в реальном времени).

## 📁 Экспорт данных

### Как завершить рабочий день:
1. Нажмите **"Завершить день"**.
2. Подтвердите действие в диалоговом окне.
	+ Программа Сохранит отчет в Excel (например, report_20231025_153045.xlsx).
	+ Очистит данные текущего дня.
	+ Завершит работу.


 ### Формат отчета:
| Дата       | Логин  | Время    | Регресс      | Комментарий | Название рана       | Ссылка          |
|------------|--------|----------|--------------|-------------|---------------------|-----------------|
| 25.10.2023 | dev123 | 02:30:00 | ТВ           |             | Каналы              | https://task/1  |
