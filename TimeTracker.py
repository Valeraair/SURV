import threading
import matplotlib
matplotlib.use('TkAgg')  # Важно добавить перед другими импортами matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from datetime import timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import openpyxl
import pystray
from PIL import Image
import sys

class TimeTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Work Time Tracker")
        self.dark_mode = False

        # Инициализация стилей
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Убираем жирные границы у Notebook
        self.style.configure(".", relief="flat")
        self.style.map("TButton", relief=[('active', 'flat'), ('!active', 'flat')])
        self.style.configure("TNotebook", borderwidth=1)
        self.style.configure("TNotebook.Tab", padding=[10, 5])
        self.setup_db()
        self.setup_ui()
        self.setup_tray()
        self.running_task = None
        self.paused = False
        self.paused_task_id = None
        self.total_time = 0
        self.current_graph_type = "bar"
        self.root.after(1000, self.update_time)
        self.update_tasks()
        self.update_total_time()
        self.load_theme()  # Загружаем сохраненную тему

    def setup_db(self):
        # Инициализация БД
        self.conn = sqlite3.connect('timetracker.db')
        self.c = self.conn.cursor()
        self.c.execute('''CREATE TABLE IF NOT EXISTS tasks
                         (id INTEGER PRIMARY KEY,
                          date TEXT,
                          login TEXT,
                          regress TEXT,
                          name TEXT,
                          link TEXT,
                          time INTEGER)''')
        self.conn.commit()

    def setup_stats_tab(self):
        """Настраивает вкладку статистики"""
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Статистика")

        # Панель управления с кнопками
        control_frame = ttk.Frame(self.stats_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Кнопки переключения типа графика
        ttk.Button(control_frame, text="Столбчатая",
                   command=lambda: self.switch_graph("bar")).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Круговая",
                   command=lambda: self.switch_graph("pie")).pack(side=tk.LEFT, padx=5)

        # Кнопка "Обновить" справа
        ttk.Button(control_frame, text="Обновить",
                   command=self.update_graph).pack(side=tk.RIGHT, padx=5)

        # Область для графика
        self.graph_frame = ttk.Frame(self.stats_frame)
        self.graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Заглушка при запуске
        ttk.Label(self.graph_frame, text="Данные загружаются...",
                  font=('Arial', 10), foreground='gray').pack(expand=True)

    def switch_graph(self, graph_type):
        """Переключает тип графика"""
        self.current_graph_type = graph_type
        self.update_graph()

    def setup_tracking_tab(self):
        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, columnspan=2, pady=5)

        # Добавляем кнопку темы в начало панели управления
        self.theme_btn = ttk.Button(control_frame, text="🌙" if not self.dark_mode else "☀️",
                                  command=self.toggle_theme,
                                  width=3)
        self.theme_btn.pack(side=tk.LEFT, padx=10)

        # Остальные кнопки остаются как есть
        delete_btn = ttk.Button(control_frame, text="Удалить", command=self.delete_task)
        delete_btn.pack(side=tk.LEFT, padx=10)

        """Настраивает вкладку трекинга задач"""
        tracking_frame = ttk.Frame(self.notebook)
        self.notebook.add(tracking_frame, text="Трекинг")

        # Переносим весь основной UI сюда
        main_frame = ttk.Frame(tracking_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(main_frame, text="Логин:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.login_entry = ttk.Entry(main_frame)
        self.login_entry.grid(row=0, column=1, padx=10, sticky=tk.EW)
        self.add_placeholder(self.login_entry, "Твой логин")

    def setup_ui(self):
        # Создаем панель вкладок
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Вкладка трекинга (только задачи)
        self.setup_tracking_tab()

        # Вкладка статистики (только графики)
        self.setup_stats_tab()

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

    def setup_tray(self):
        """Инициализация иконки трея (без запуска)"""
        image = Image.new('RGB', (16, 16), 'black')
        self.tray_menu = pystray.Menu(
            pystray.MenuItem('Открыть', self.restore_window),
            pystray.MenuItem('Выход', self.exit_app)
        )
        self.tray_icon = None
        self.tray_thread = None

    def add_task(self):
        # Проверка заполнения обязательных полей
        login = self.login_entry.get().strip()
        regress = self.regress_entry.get().strip()
        name = self.name_entry.get().strip()
        link = self.link_entry.get().strip()

        if not login or login == "Введите ваш логин":
            messagebox.showerror("Ошибка", "Введите ваш логин")
            self.login_entry.focus_set()
            return

        if not regress or regress == "Название поверхности":
            messagebox.showerror("Ошибка", "Введите название поверхности")
            self.regress_entry.focus_set()
            return

        if not name or name == "Название тест-рана":
            messagebox.showerror("Ошибка", "Введите название тест-рана")
            self.name_entry.focus_set()
            return

        if not link or link == "Ссылка на тест-ран":
            messagebox.showerror("Ошибка", "Введите ссылку на тест-ран")
            self.link_entry.focus_set()
            return

        data = (
            datetime.now().strftime("%d.%m.%Y"),
            login,
            regress,
            name,
            link,
            0
        )

        try:
            self.c.execute("INSERT INTO tasks (date, login, regress, name, link, time) VALUES (?,?,?,?,?,?)", data)
            new_id = self.c.lastrowid

            if self.extra_time.get():
                self.c.execute("INSERT INTO tasks (date, login, regress, name, link, time) VALUES (?,?,?,?,?,?)",
                               (data[0], data[1], data[2], "[ДОП] " + data[3], data[4], 0))

            self.conn.commit()
            self.update_tasks()
            self.clear_task_fields()
            self.start_task_timer(new_id)
            self.update_graph()

        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось добавить задачу: {str(e)}")

    def start_task_timer(self, task_id):
        """Явный запуск таймера для задачи"""
        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)

        # Запускаем новую задачу
        self.running_task = {'id': task_id, 'start_time': datetime.now()}
        self.paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)
        self.edit_btn.config(state=tk.DISABLED)  # Блокируем кнопку при запуске
        self.update_tasks()
        self.update_total_time()

    def clear_task_fields(self):
        # Очистка полей ввода задачи
        self.regress_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.link_entry.delete(0, tk.END)
        self.extra_time.set(False)

    def delete_task(self):
        # Удаление выбранной задачи
        selected = self.tasks_list.selection()
        if not selected:
            return

        if messagebox.askyesno("Подтверждение", "Удалить выбранную задачу?"):
            try:
                task_id = self.tasks_list.item(selected[0])['values'][0]

                # Если удаляем задачу, которая была выбрана для продолжения
                if hasattr(self, 'paused_task_id') and self.paused_task_id == task_id:
                    self.paused_task_id = None
                    # Пытаемся найти другую задачу для продолжения
                    self.c.execute("SELECT id FROM tasks WHERE date=? AND id!=? LIMIT 1",
                                   (datetime.now().strftime("%d.%m.%Y"), task_id))
                    result = self.c.fetchone()
                    if result:
                        self.paused_task_id = result[0]

                # Получаем время задачи перед удалением
                self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
                task_time = self.c.fetchone()[0]

                # Удаляем задачу
                self.c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
                self.conn.commit()

                # Обновляем общее время
                self.total_time -= task_time
                self.update_total_time()

                self.update_tasks()

            except Exception as e:
                messagebox.showerror("Ошибка удаления", str(e))

    def update_tasks(self):
        # Обновление списка задач
        for item in self.tasks_list.get_children():
            self.tasks_list.delete(item)

        try:
            self.c.execute("SELECT id, regress, name, time FROM tasks WHERE date=?",
                           (datetime.now().strftime("%d.%m.%Y"),))
            tasks = self.c.fetchall()

            for row in tasks:
                task_id, regress, name, time = row
                if self.running_task and self.running_task['id'] == task_id:
                    status = '▶ Активна'
                    self.edit_btn['state'] = tk.DISABLED  # Блокируем кнопку для активной задачи
                else:
                    if self.paused and hasattr(self, 'paused_task_id') and self.paused_task_id == task_id:
                        status = '⏸ Выбрана'
                    else:
                        status = '⏸ Ожидание'

                self.tasks_list.insert('', tk.END, values=(
                    task_id,
                    regress,
                    name,
                    status,
                    self.format_time(time)
                ))

            # Обновляем состояние кнопок
            if not tasks:
                self.paused_task_id = None
                self.resume_btn.config(state=tk.DISABLED)
                self.edit_btn.config(state=tk.DISABLED)
            elif self.paused:
                self.resume_btn.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Ошибка обновления", str(e))

    def on_task_select(self, event):
        """Обработчик выбора задачи в списке"""
        selected = self.tasks_list.selection()
        # Кнопка "Изменить" всегда активна при выборе задачи
        self.edit_btn['state'] = tk.NORMAL if selected else tk.DISABLED

    def format_time(self, seconds):
        # Форматирование времени
        return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

    def update_time(self):
        if self.running_task and not self.paused:
            elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())
            current_total = self.total_time + elapsed
            self.total_time_label.config(text=f"Общее время: {self.format_time(current_total)}")

            # Обновляем отображение времени для текущей задачи
            for item in self.tasks_list.get_children():
                values = self.tasks_list.item(item)['values']
                if values[0] == self.running_task['id']:
                    total_task_time = self.get_task_time(self.running_task['id']) + elapsed
                    self.tasks_list.item(item, values=(
                        values[0],
                        values[1],
                        values[2],
                        '▶ Активна',
                        self.format_time(total_task_time)
                    ))  # <- Вот здесь была пропущена закрывающая скобка
                    break

        self.root.after(1000, self.update_time)

    def get_task_time(self, task_id):
        #Получение времени задачи из БД
        self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def pause_all(self):
        """Остановка всех таймеров по кнопке"""
        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)
            # Сохраняем текущую задачу как выбранную для продолжения
            self.paused_task_id = self.running_task['id']
            self.running_task = None

        self.paused = True
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)
        self.update_tasks()
        self.update_total_time()

    def resume_all(self):
        """Возобновление работы с выбранной задачей"""
        # Проверяем, есть ли выбранная задача в списке
        selected = self.tasks_list.selection()
        task_id = None

        if selected:
            task_id = self.tasks_list.item(selected[0])['values'][0]
        elif hasattr(self, 'paused_task_id') and self.paused_task_id:
            task_id = self.paused_task_id

        if not task_id:
            messagebox.showwarning("Ошибка", "Не выбрана задача для продолжения")
            return

        # Проверяем существование задачи
        self.c.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,))
        if not self.c.fetchone():
            messagebox.showwarning("Ошибка", "Выбранная задача больше не существует")
            self.paused_task_id = None
            self.resume_btn.config(state=tk.DISABLED)
            return

        # Запускаем задачу
        self.start_task_timer(task_id)
        self.paused = False
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)

    def update_total_time(self):
        # Обновление общего времени
        self.c.execute("SELECT SUM(time) FROM tasks WHERE date=?",
                       (datetime.now().strftime("%d.%m.%Y"),))
        total = self.c.fetchone()[0] or 0
        self.total_time = total
        self.total_time_label.config(text=f"Общее время: {self.format_time(total)}")

    def finish_day(self):
        if messagebox.askokcancel("Завершение дня", "Экспортировать данные и завершить работу?"):
            self.export_to_xlsx()
            self.clear_day_data()
            self.update_graph()  # Обновляем график после очистки данных
            messagebox.showinfo("Успех", "Данные экспортированы и очищены")

    def export_to_xlsx(self):
        # Экспорт в Excel
        today = datetime.now().strftime("%d.%m.%Y")
        self.c.execute("SELECT date, login, regress, name, link, time FROM tasks WHERE date=?", (today,))
        data = self.c.fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        headers = ['Дата', 'Логин', 'Время', 'Регресс', 'Комментарий', 'Название рана', 'Ссылка']
        ws.append(headers)

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

        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

    def clear_day_data(self):
        # Очистка данных за день после экспорта
        self.c.execute("DELETE FROM tasks WHERE date=?", (datetime.now().strftime("%d.%m.%Y"),))
        self.conn.commit()
        self.total_time = 0
        self.update_tasks()
        self.update_total_time()

    def run_tray_icon(self):
        """Метод для запуска иконки в отдельном потоке"""
        try:
            self.tray_icon.run()
        except Exception as e:
            print(f"Ошибка в трее: {e}")
        finally:
            self.tray_running = False

    def hide_to_tray(self):
        """Скрытие в трей с защитой от повторного запуска"""
        if self.tray_icon is not None:
            return

        self.root.withdraw()

        # Создаем новую иконку при каждом сворачивании
        image = Image.new('RGB', (16, 16), 'black')
        self.tray_icon = pystray.Icon("time_tracker", image, "Time Tracker", self.tray_menu)

        # Запускаем в отдельном потоке с обработкой ошибок
        def run_icon():
            try:
                self.tray_icon.run()
            except Exception as e:
                print(f"Ошибка трея: {e}")
            finally:
                self.tray_icon = None

        self.tray_thread = threading.Thread(target=run_icon, daemon=True)
        self.tray_thread.start()

    def restore_window(self, icon=None, item=None):
        """Восстановление окна с защитой от дублирования"""
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as e:
                print(f"Ошибка при остановке трея: {e}")
            finally:
                self.tray_icon = None

        if not self.root.winfo_viewable():
            self.root.deiconify()
            self.root.after(100, lambda: self.root.focus_force())

    def exit_app(self, icon=None, item=None):
        """Безопасный выход"""
        self.restore_window()
        self.root.after(200, self.safe_exit)

    def update_task_time(self, task_id, seconds):
        # Обновление времени задачи в БД
        self.c.execute("UPDATE tasks SET time = time + ? WHERE id=?", (seconds, task_id))
        self.conn.commit()

    def task_exists(self, task_id):
        """Проверяет, существует ли задача с указанным ID"""
        self.c.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,))
        return bool(self.c.fetchone())

    def edit_task(self):
        selected = self.tasks_list.selection()
        if not selected:
            return

        task_id = self.tasks_list.item(selected[0])['values'][0]

        # Проверяем, активна ли выбранная задача
        is_active = self.running_task and self.running_task['id'] == task_id

        # Получаем текущие данные задачи (кроме времени)
        self.c.execute("SELECT regress, name, link FROM tasks WHERE id=?", (task_id,))
        regress, name, link = self.c.fetchone()

        # Создаем окно редактирования
        edit_win = tk.Toplevel(self.root)
        edit_win.title("Редактирование задачи")
        edit_win.resizable(False, False)

        # Фрейм для полей ввода
        fields_frame = ttk.Frame(edit_win, padding=10)
        fields_frame.pack()

        # Поля формы
        ttk.Label(fields_frame, text="Регресс:").grid(row=0, column=0, sticky=tk.W, pady=5)
        regress_entry = ttk.Entry(fields_frame, width=40)
        regress_entry.grid(row=0, column=1, padx=5, pady=5)
        regress_entry.insert(0, regress)

        ttk.Label(fields_frame, text="Название:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(fields_frame, width=40)
        name_entry.grid(row=1, column=1, padx=5, pady=5)
        name_entry.insert(0, name)

        ttk.Label(fields_frame, text="Ссылка:").grid(row=2, column=0, sticky=tk.W, pady=5)
        link_entry = ttk.Entry(fields_frame, width=40)
        link_entry.grid(row=2, column=1, padx=5, pady=5)
        link_entry.insert(0, link)

        # Фрейм для кнопок
        buttons_frame = ttk.Frame(edit_win, padding=10)
        buttons_frame.pack()

        def save_changes():
            new_regress = regress_entry.get().strip()
            new_name = name_entry.get().strip()
            new_link = link_entry.get().strip()

            if not all([new_regress, new_name, new_link]):
                messagebox.showerror("Ошибка", "Все поля должны быть заполнены")
                return

            try:
                # Если задача активна, временно останавливаем таймер
                if is_active:
                    elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
                    self.update_task_time(task_id, int(elapsed))
                    self.total_time += int(elapsed)

                # Обновляем данные задачи
                self.c.execute("""
                               UPDATE tasks
                               SET regress = ?,
                                   name    = ?,
                                   link    = ?
                               WHERE id = ?
                               """, (new_regress, new_name, new_link, task_id))
                self.conn.commit()

                # Если задача была активна, возобновляем таймер
                if is_active:
                    self.running_task['start_time'] = datetime.now()

                self.update_tasks()
                edit_win.destroy()
                messagebox.showinfo("Успех", "Задача успешно обновлена")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось обновить задачу: {str(e)}")
                # Если задача была активна и произошла ошибка, возобновляем таймер
                if is_active:
                    self.running_task['start_time'] = datetime.now() - timedelta(seconds=elapsed)

        ttk.Button(buttons_frame, text="Сохранить", command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Отмена", command=edit_win.destroy).pack(side=tk.LEFT, padx=5)

    def setup_tracking_tab(self):
        """Настраивает вкладку трекинга задач"""
        tracking_frame = ttk.Frame(self.notebook)
        self.notebook.add(tracking_frame, text="Трекинг")

        # Переносим весь основной UI сюда
        main_frame = ttk.Frame(tracking_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)

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
        self.tasks_list.bind('<<TreeviewSelect>>', self.on_task_select)

        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, columnspan=2, pady=5)

        # Кнопка переключения темы (добавлена здесь)
        self.theme_btn = ttk.Button(control_frame, text="🌙",
                                    command=self.toggle_theme,
                                    width=3)
        self.theme_btn.pack(side=tk.LEFT, padx=10)

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

        self.edit_btn = ttk.Button(control_frame, text="Изменить", command=self.edit_task, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=10)

        # Настройка расширения
        main_frame.grid_rowconfigure(2, weight=1)

    def setup_stats_tab(self):
        """Настраивает вкладку статистики"""
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Статистика")

        # Контейнер для управления
        control_frame = ttk.Frame(self.stats_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Левая группа кнопок
        left_btn_frame = ttk.Frame(control_frame)
        left_btn_frame.pack(side=tk.LEFT)

        ttk.Button(left_btn_frame, text="Столбчатая",
                   command=lambda: self.switch_graph("bar")).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_btn_frame, text="Круговая",
                   command=lambda: self.switch_graph("pie")).pack(side=tk.LEFT, padx=5)

        # Кнопка "Обновить" справа
        ttk.Button(control_frame, text="Обновить",
                   command=self.update_graph).pack(side=tk.RIGHT, padx=5)

        # Область графика
        self.graph_frame = ttk.Frame(self.stats_frame)
        self.graph_frame.pack(fill=tk.BOTH, expand=True)

    def switch_graph(self, graph_type):
        """Переключает тип графика"""
        self.current_graph_type = graph_type
        self.update_graph()

    def update_graph(self):
        """Обновляет график с учётом текущей темы"""
        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        try:
            # Цвета для темной/светлой темы
            if self.dark_mode:
                bg_color = "#1E1E1E"
                text_color = "#E0E0E0"
                grid_color = "#3A3A3A"
                bar_color = "#4A6987"
            else:
                bg_color = "#FFFFFF"
                text_color = "#000000"
                grid_color = "#D0D0D0"
                bar_color = "#0078D7"

            # Создаем фигуру
            fig = Figure(figsize=(6, 4), dpi=100,
                         facecolor=bg_color)
            ax = fig.add_subplot(111,
                                 facecolor=bg_color)

            # Получаем данные
            self.c.execute("SELECT name, SUM(time) FROM tasks GROUP BY name")
            data = self.c.fetchall()

            if not data:
                ax.text(0.5, 0.5, "Нет данных для отображения",
                        ha='center', va='center',
                        color=text_color)
            else:
                names = [x[0] for x in data]
                times = [x[1] / 3600 for x in data]  # в часах

                if self.current_graph_type == "bar":
                    bars = ax.bar(names, times, color=bar_color)
                    ax.set_ylabel('Часы', color=text_color)
                    ax.set_title('Время по задачам', color=text_color)

                    # Настройка сетки и осей
                    ax.grid(color=grid_color, linestyle='--', alpha=0.5)
                    ax.tick_params(axis='x', colors=text_color, rotation=45)
                    ax.tick_params(axis='y', colors=text_color)

                    # Подписи значений
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width() / 2., height,
                                f'{height:.1f}',
                                ha='center', va='bottom',
                                color=text_color)
                else:
                    # Для круговой диаграммы используем приятные цвета
                    colors = ['#4A6987', '#5D8AA8', '#7EB6FF', '#003366', '#1E1E1E']
                    ax.pie(times, labels=names, autopct='%1.1f%%',
                           colors=colors[:len(times)],
                           textprops={'color': text_color})
                    ax.set_title('Распределение времени', color=text_color)

            # Встраиваем график
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            ttk.Label(self.graph_frame, text=f"Ошибка: {str(e)}",
                      foreground="red").pack()

    def update_graph_theme(self):
        """Обновление темы графиков"""
        if self.dark_mode:
            plt.style.use('dark_background')
        else:
            plt.style.use('default')
        self.update_graph()

    def safe_exit(self):
        """Безопасное завершение программы"""
        try:
            plt.close('all')  # Закрываем все фигуры matplotlib
            if hasattr(self, 'conn'):
                self.conn.close()
            if hasattr(self, 'tray_icon'):
                self.tray_icon.stop()
            self.root.quit()  # Корректное завершение mainloop
        except Exception as e:
            print(f"Ошибка при завершении: {e}")
        finally:
            sys.exit(0)

    def toggle_theme(self):
        """Переключение между светлой и темной темой"""
        self.dark_mode = not self.dark_mode
        self.theme_btn.config(text="☀️" if self.dark_mode else "🌙")  # Обновляем иконку
        self.apply_theme()
        self.save_theme()

    def apply_theme(self):
        """Применение выбранной темы"""
        if self.dark_mode:
            # Темная тема
            bg_color = "#1E1E1E"  # Основной фон
            fg_color = "#E0E0E0"  # Текст
            border_color = "#2D2D2D"  # Тёмные границы (почти сливаются с фоном)
            separator_color = "#333333"  # Цвет разделителей

            # Доп. цвета
            entry_bg = "#252525"
            button_bg = "#333333"
        else:
            # Светлая тема (оставляем как было)
            bg_color = "#F5F5F5"
            fg_color = "#000000"
            border_color = "#CCCCCC"
            separator_color = "#E0E0E0"

            # Доп. цвета
            entry_bg = "#FFFFFF"
            button_bg = "#E0E0E0"

        style = ttk.Style()
        style.theme_use('clam')

        # Основные настройки
        style.configure('.',
                        background=bg_color,
                        foreground=fg_color,
                        bordercolor=border_color,
                        darkcolor=border_color,
                        lightcolor=border_color)

        # Специально для разделителей
        style.configure("TSeparator",
                        background=separator_color)

        # Настройка Notebook (вкладок)
        style.configure("TNotebook",
                        background=bg_color,
                        bordercolor=border_color)
        style.configure("TNotebook.Tab",
                        background=bg_color,
                        foreground=fg_color,
                        bordercolor=border_color,
                        padding=[10, 5])

        # Treeview (список задач)
        style.configure("Treeview",
                        background=entry_bg,
                        foreground=fg_color,
                        fieldbackground=entry_bg,
                        bordercolor=border_color)

        # Кнопки и поля ввода
        style.configure("TButton",
                        background=button_bg,
                        foreground=fg_color)
        style.configure("TEntry",
                        fieldbackground=entry_bg,
                        foreground=fg_color)

        # LabelFrame
        style.configure("TLabelframe",
                        background=bg_color,
                        bordercolor=border_color)

        # Принудительно обновляем все элементы
        self.root.config(bg=bg_color)
        self.update_graph_theme()

    def save_theme(self):
        """Сохранение темы в файл"""
        with open('theme.cfg', 'w') as f:
            f.write('dark' if self.dark_mode else 'light')

    def load_theme(self):
        """Загрузка темы из файла"""
        try:
            with open('theme.cfg', 'r') as f:
                self.dark_mode = f.read() == 'dark'
            self.apply_theme()
        except:
            self.dark_mode = False

if __name__ == "__main__":
    root = tk.Tk()
    app = TimeTracker(root)

    # Обработчик закрытия окна
    def on_close():
        if messagebox.askyesno("Подтверждение", "Свернуть программу в трей?"):
            app.hide_to_tray()
        else:
            app.safe_exit()

    root.protocol('WM_DELETE_WINDOW', on_close)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.safe_exit()
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        app.safe_exit()