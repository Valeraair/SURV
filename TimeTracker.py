import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import openpyxl
import pystray
from PIL import Image
import sys

class TimeTracker:
    # Константы
    DB_NAME = 'timetracker.db'
    DATE_FORMAT = "%d.%m.%Y"
    EXCEL_DATE_FORMAT = "%Y%m%d_%H%M%S"
    EXCEL_HEADERS = ['Дата', 'Логин', 'Время', 'Регресс', 'Комментарий', 'Название рана', 'Ссылка']

    # Улучшенный метод работы с БД
    def db_execute(self, query, params=()):
        """Безопасное выполнение запроса к БД"""
        try:
            with self.conn:
                return self.c.execute(query, params)
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", f"Database error: {str(e)}")
            raise

    def __init__(self, root):
        self.root = root
        self.root.title("Work Time Tracker")
        self.setup_db()
        self.setup_ui()
        self.setup_tray()
        self.running_task = None
        self.paused = False
        self.paused_task_id = None  # Новое: для хранения ID задачи на паузе
        self.total_time = 0
        self.root.after(1000, self.update_time)
        self.update_tasks()
        self.update_total_time()
        self._is_exiting = False  # Флаг для отслеживания выхода
        self.paused_task = None  # Заменяем paused_task_id на полный объект задачи

    def add_placeholder(self, entry, text):
        entry.insert(0, text)
        entry.config(foreground='grey')
        entry.bind('<FocusIn>', lambda e: self.on_entry_focus_in(entry, text))
        entry.bind('<FocusOut>', lambda e: self.on_entry_focus_out(entry, text))

    def on_entry_focus_in(self, entry, placeholder):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(foreground='black')

    def on_entry_focus_out(self, entry, placeholder):
        if entry.get() == '':
            entry.insert(0, placeholder)
            entry.config(foreground='grey')

    def setup_db(self):
        """Инициализация базы данных"""
        try:
            self.conn = sqlite3.connect(self.DB_NAME)
            self.c = self.conn.cursor()
            self.db_execute('''CREATE TABLE IF NOT EXISTS tasks
                               (
                                   id
                                   INTEGER
                                   PRIMARY
                                   KEY,
                                   date
                                   TEXT,
                                   login
                                   TEXT,
                                   regress
                                   TEXT,
                                   name
                                   TEXT,
                                   link
                                   TEXT,
                                   time
                                   INTEGER
                               )''')
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", f"Не удалось инициализировать БД: {str(e)}")
            sys.exit(1)

    def setup_ui(self):
        # Инициализация UI
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)

        # Стиль для элементов
        style = ttk.Style()
        style.configure('TEntry', padding=5, font=('Arial', 10))
        style.configure('TButton', padding=5, font=('Arial', 10))
        style.configure('TLabel', font=('Arial', 10))

        # Поле логина
        ttk.Label(main_frame, text="Логин:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.login_entry = ttk.Entry(main_frame)
        self.login_entry.grid(row=0, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(self.login_entry, "Введите ваш логин")

        # Форма задачи
        task_frame = ttk.LabelFrame(main_frame, text="Новая задача", padding=10)
        task_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.EW)
        task_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(task_frame, text="Регресс:").grid(row=0, column=0, sticky=tk.W)
        self.regress_entry = ttk.Entry(task_frame)
        self.regress_entry.grid(row=0, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(self.regress_entry, "Название поверхности")

        ttk.Label(task_frame, text="Название:").grid(row=1, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(task_frame)
        self.name_entry.grid(row=1, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(self.name_entry, "Название тест-рана")

        ttk.Label(task_frame, text="Ссылка:").grid(row=2, column=0, sticky=tk.W)
        self.link_entry = ttk.Entry(task_frame)
        self.link_entry.grid(row=2, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(self.link_entry, "Ссылка на тест-ран")

        self.extra_time = tk.BooleanVar()
        ttk.Checkbutton(task_frame, text="Доп. время", variable=self.extra_time).grid(row=3, columnspan=2, pady=5)

        add_btn = ttk.Button(task_frame, text="Добавить", command=self.add_task)
        add_btn.grid(row=4, columnspan=2, pady=5)

        # Список задач
        self.tasks_list = ttk.Treeview(main_frame, columns=('id', 'regress', 'name', 'status', 'time'), show='headings')
        self.tasks_list.heading('id', text='ID')
        self.tasks_list.heading('regress', text='Регресс')
        self.tasks_list.heading('name', text='Название')
        self.tasks_list.heading('status', text='Статус')
        self.tasks_list.heading('time', text='Время')
        self.tasks_list.column('status', width=100, anchor=tk.CENTER)
        self.tasks_list.grid(row=2, column=0, columnspan=2, pady=5, sticky=tk.NSEW)

        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, columnspan=2, pady=5)

        delete_btn = ttk.Button(control_frame, text="Удалить", command=self.delete_task)
        delete_btn.pack(side=tk.LEFT, padx=10)

        self.total_time_label = ttk.Label(control_frame, text="Общее время: 00:00:00")
        self.total_time_label.pack(side=tk.LEFT, padx=10)

        self.pause_btn = ttk.Button(control_frame, text="Пауза", command=self.pause_all)
        self.pause_btn.pack(side=tk.LEFT, padx=10)

        self.resume_btn = ttk.Button(control_frame, text="Продолжить", command=self.resume_all, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=10)

        finish_btn = ttk.Button(control_frame, text="Завершить день", command=self.finish_day)
        finish_btn.pack(side=tk.LEFT, padx=10)

        # В панель управления (после finish_btn)
        close_btn = ttk.Button(control_frame, text="Закрыть", command=self.confirm_and_exit)
        close_btn.pack(side=tk.LEFT, padx=10)

        # Настройка расширения
        main_frame.grid_rowconfigure(2, weight=1)

    def setup_tray(self):
        # Настройка иконки в системном трее
        image = Image.new('RGB', (64, 64), 'black')
        menu = pystray.Menu(
            pystray.MenuItem('Открыть', self.restore_window),
            pystray.MenuItem('Выход', self.exit_app)
        )
        self.tray_icon = pystray.Icon("time_tracker", image, "Time Tracker", menu)

    def add_task(self):
        # Добавление новой задачи в БД
        if not all([self.regress_entry.get(), self.name_entry.get(), self.link_entry.get()]):
            messagebox.showerror("Ошибка", "Заполните все поля задачи")
            return

        data = (
            datetime.now().strftime("%d.%m.%Y"),
            self.login_entry.get(),
            self.regress_entry.get(),
            self.name_entry.get(),
            self.link_entry.get(),
            0
        )

        try:
            self.c.execute("INSERT INTO tasks (date, login, regress, name, link, time) VALUES (?,?,?,?,?,?)", data)
            new_id = self.c.lastrowid  # Получаем ID новой задачи

            if self.extra_time.get():
                self.c.execute("INSERT INTO tasks (date, login, regress, name, link, time) VALUES (?,?,?,?,?,?)",
                               (data[0], data[1], data[2], "[ДОП] " + data[3], data[4], 0))

            self.conn.commit()
            self.update_tasks()
            self.clear_task_fields()

            # Принудительно запускаем таймер для новой задачи
            self.start_task_timer(new_id)

        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))

    def start_task_timer(self, task_id):
        """Явный запуск таймера для задачи"""
        if self.running_task:
            # Останавливаем текущую задачу
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)

        # Запускаем новую задачу
        self.running_task = {'id': task_id, 'start_time': datetime.now()}
        self.update_tasks()
        self.update_total_time()

    def on_task_select(self, event):
        """Обработчик выбора задачи в списке"""
        if self.paused:
            return

        selected = self.tasks_list.selection()
        if not selected:
            return

        task_id = self.tasks_list.item(selected[0])['values'][0]
        self.start_task_timer(task_id)

    def clear_task_fields(self):
        # Очистка полей ввода задачи
        self.regress_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.link_entry.delete(0, tk.END)
        self.extra_time.set(False)

    def delete_task(self):
        """Удаление выбранной задачи"""
        selected = self.tasks_list.selection()
        if not selected:
            return

        task_id = self.tasks_list.item(selected[0])['values'][0]

        if messagebox.askyesno("Подтверждение", "Удалить выбранную задачу?"):
            try:
                # Если удаляем задачу на паузе - сбрасываем paused_task
                if self.paused_task and self.paused_task['id'] == task_id:
                    self.paused_task = None
                    self.resume_btn.config(state=tk.DISABLED)

                # Остальная логика удаления...
                self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
                task_time = self.c.fetchone()[0]

                self.c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
                self.conn.commit()

                self.total_time -= task_time
                self.update_tasks()
                self.update_total_time()

            except Exception as e:
                messagebox.showerror("Ошибка удаления", str(e))

    def update_tasks(self):
        # Обновление списка задач после удаления
        for item in self.tasks_list.get_children():
            self.tasks_list.delete(item)

        try:
            self.c.execute("SELECT id, regress, name, time FROM tasks WHERE date=?",
                           (datetime.now().strftime("%d.%m.%Y"),))
            for row in self.c.fetchall():
                task_id, regress, name, time = row
                status = '▶ Активна' if self.running_task and self.running_task['id'] == task_id else '⏸ Ожидание'
                self.tasks_list.insert('', tk.END, values=(
                    task_id,
                    regress,
                    name,
                    status,
                    self.format_time(time)
                ))
        except Exception as e:
            messagebox.showerror("Ошибка обновления", str(e))

    def on_task_select(self, event):
        # Обработчик выбора задачи
        if self.paused:
            return

        selected = self.tasks_list.selection()
        if not selected:
            return

        new_task_id = self.tasks_list.item(selected[0])['values'][0]

        # Если уже есть активная задача - сохраняем ее время
        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)
            self.update_total_time()

        # Запускаем новую задачу
        self.running_task = {'id': new_task_id, 'start_time': datetime.now()}
        self.update_tasks()

    def update_task_time(self, task_id, seconds):
        # Обновление времени задачи в БД
        self.c.execute("UPDATE tasks SET time = time + ? WHERE id=?", (seconds, task_id))
        self.conn.commit()

    def format_time(self, seconds):
        # Форматирование времени
        return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

    def update_time(self):
        """Обновление отображения времени"""
        if not self.running_task or self.paused:
            self.root.after(1000, self.update_time)
            return

        elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())
        current_total = self.total_time + elapsed
        self.total_time_label.config(text=f"Общее время: {self.format_time(current_total)}")

        # Обновляем только активную задачу
        task_id = self.running_task['id']
        for item in self.tasks_list.get_children():
            values = self.tasks_list.item(item)['values']
            if values[0] == task_id:
                total_task_time = self.get_task_time(task_id) + elapsed
                self.tasks_list.item(item, values=(
                    values[0],
                    values[1],
                    values[2],
                    '▶ Активна',
                    self.format_time(total_task_time)
                ))
                break

        self.root.after(1000, self.update_time)

    def get_task_time(self, task_id):
        #Получение времени задачи из БД
        self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def pause_all(self):
        """Постановка задач на паузу"""
        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)

            # Сохраняем всю информацию о задаче
            self.paused_task = {
                'id': self.running_task['id'],
                'start_time': datetime.now()  # Фиксируем время паузы
            }
            self.running_task = None

        self.paused = True
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)
        self.update_tasks()
        self.update_total_time()

    def resume_all(self):
        """Возобновление задач"""
        if self.paused_task:
            # Проверяем, что задача еще существует
            self.c.execute("SELECT id FROM tasks WHERE id=?", (self.paused_task['id'],))
            if self.c.fetchone():  # Если задача существует
                self.running_task = {
                    'id': self.paused_task['id'],
                    'start_time': datetime.now()  # Новое время старта
                }
            self.paused_task = None

        self.paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self.update_tasks()

    def update_total_time(self):
        # Обновление общего времени
        self.c.execute("SELECT SUM(time) FROM tasks WHERE date=?",
                       (datetime.now().strftime("%d.%m.%Y"),))
        total = self.c.fetchone()[0] or 0
        self.total_time = total
        self.total_time_label.config(text=f"Общее время: {self.format_time(total)}")

    def finish_day(self):
        # Завершение рабочего дня
        if messagebox.askokcancel("Завершение дня", "Экспортировать данные и завершить работу?"):
            self.export_to_xlsx()
            self.clear_day_data()
            messagebox.showinfo("Успех", "Данные экспортированы и очищены")
            self.exit_app()

    def export_to_xlsx(self):
        """Экспорт данных в Excel файл"""
        try:
            today = datetime.now().strftime(self.DATE_FORMAT)
            data = self.db_execute(
                "SELECT date, login, regress, name, link, time FROM tasks WHERE date=?",
                (today,)
            ).fetchall()

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(self.EXCEL_HEADERS)

            for row in data:
                date, login, regress, name, link, time = row
                ws.append([
                    date,
                    login,
                    self.format_time(time),
                    regress,
                    "",  # Пустой столбец для комментариев
                    name,
                    link
                ])

            filename = f"report_{datetime.now().strftime(self.EXCEL_DATE_FORMAT)}.xlsx"
            wb.save(filename)
            return True
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Не удалось экспортировать данные: {str(e)}")
            return False

    def clear_day_data(self):
        # Очистка данных за день после экспорта
        self.c.execute("DELETE FROM tasks WHERE date=?", (datetime.now().strftime("%d.%m.%Y"),))
        self.conn.commit()
        self.total_time = 0
        self.update_tasks()
        self.update_total_time()

    def hide_to_tray(self):
        """Скрытие окна в трей"""
        self.root.withdraw()  # Просто скрываем окно без подтверждения

    def restore_window(self, icon=None, item=None):
        # Восстановление окна из трея
        self.root.deiconify()

    def exit_app(self):
        """Корректный выход из программы"""
        if not hasattr(self, '_is_exiting'):
            self._is_exiting = True
            if self.confirm_exit() and self._finish_operations(True):
                self.conn.close()
                self.tray_icon.stop()
                self.root.destroy()
                sys.exit(0)
            self._is_exiting = False

    def confirm_exit(self):
        """Окно подтверждения выхода с тремя вариантами"""
        result = messagebox.askyesnocancel(
            "Подтверждение выхода",
            "Хотите экспортировать данные перед выходом?\n\n"
            "Да - экспорт и выход\n"
            "Нет - выход без экспорта\n"
            "Отмена - продолжить работу"
        )

        if result is None:  # Отмена
            return False
        elif result:  # Да
            self.export_to_xlsx()
            self.clear_day_data()
            return True
        else:  # Нет
            return True

    def db_execute(self, query, params=()):
        """Безопасное выполнение запроса к БД"""
        try:
            with self.conn:
                return self.c.execute(query, params)
        except sqlite3.Error as e:
            messagebox.showerror("Ошибка БД", f"Database error: {str(e)}")
            raise

    def create_entry_field(self, parent, label_text, placeholder, row):
        """Универсальное создание поля ввода с подсказкой"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W)
        entry = ttk.Entry(parent)
        entry.grid(row=row, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(entry, placeholder)
        return entry

    def _finish_operations(self, with_export):
        """Общие операции завершения работы"""
        try:
            if with_export:
                if not self.export_to_xlsx():
                    return False
                self.clear_day_data()
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при завершении: {str(e)}")
            return False

    def confirm_and_exit(self):
        """Подтверждение и выход"""
        result = messagebox.askyesnocancel(
            "Подтверждение выхода",
            "Хотите экспортировать данные перед выходом?\n\n"
            "Да - экспорт и выход\n"
            "Нет - выход без экспорта\n"
            "Отмена - продолжить работу"
        )

        if result is None:  # Отмена
            return
        elif result:  # Да
            self.export_to_xlsx()
            self.clear_day_data()

        self.conn.close()
        self.tray_icon.stop()
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = TimeTracker(root)
    root.protocol('WM_DELETE_WINDOW', app.hide_to_tray)  # Оставляем только hide_to_tray
    root.mainloop()

