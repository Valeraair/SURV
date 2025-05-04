from tkinter import Toplevel, Label
import threading
import matplotlib
matplotlib.use('TkAgg')
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
from matplotlib import patheffects

class TimeTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Work Time Tracker")
        self.title_template = "[▶ {task}] {time} | Всего: {total}"
        self.dark_mode = False

        # Инициализация стилей
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Базовые настройки
        self.style.configure(".", relief="flat")
        self.style.map("TButton", relief=[('active', 'flat'), ('!active', 'flat')])

        try:
            self.light_icon = tk.PhotoImage(file='light_icon.png')
            self.dark_icon = tk.PhotoImage(file='dark_icon.png')
        except:
            # Fallback если файлы не найдены
            self.light_icon = tk.PhotoImage(data="""
                iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAA
                AsTAAALEwEAmpwYAAAAB3RJTUUH4AkEEjIZWYQo3QAAAB1pVFh0Q29tbWVudAAAAAAAQ3JlYXRlZCB3aX
                RoIEdJTVBkLmUHAAAAJklEQVQ4y2NgGAXDFmzatMmKAQ38v3///n8o+v/gwYP/Dx48+A9Vw4gGAAAZdA
                l3Xq8H1QAAAABJRU5ErkJggg==""")
            self.dark_icon = tk.PhotoImage(data="""
                iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAA
                AsTAAALEwEAmpwYAAAAB3RJTUUH4AkEEjMfQ1JQYQAAAB1pVFh0Q29tbWVudAAAAAAAQ3JlYXRlZCB3aX
                RoIEdJTVBkLmUHAAAAJklEQVQ4y2NgGAXDFmzatMmKAQ38v3///n8o+v/gwYP/Dx48+A9Vw4gGAADQ0Q
                l3Xq8H1QAAAABJRU5ErkJggg==""")

        # Остальная инициализация
        self.setup_db()
        self.setup_ui()
        self.setup_task_context_menu()
        self.setup_tray()
        self.running_task = None
        self.paused = False
        self.paused_task_id = None
        self.check_for_paused_task()
        self.total_time = 0
        self.current_graph_type = "bar"
        self.root.after(1000, self.update_time)
        self.update_tasks()
        self.update_total_time()
        self.load_theme()
        self.paused_task_time = 0
        self.title_template = "{regress} | {name} | {time} | Всего: {total}"
        self.tooltips = {}

    def setup_db(self):
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
        control_frame = ttk.Frame(self.stats_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(control_frame, text="Столбчатая",
                   command=lambda: self.switch_graph("bar")).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Круговая",
                   command=lambda: self.switch_graph("pie")).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Обновить",
                   command=self.update_graph).pack(side=tk.RIGHT, padx=5)
        self.graph_frame = ttk.Frame(self.stats_frame)
        self.graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(self.graph_frame, text="Данные загружаются...",
                  font=('Arial', 10), foreground='gray').pack(expand=True)

    def switch_graph(self, graph_type):
        """Переключает тип графика"""
        self.current_graph_type = graph_type
        self.update_graph()

    def setup_tracking_tab(self):
        """Настраивает вкладку трекинга задач"""
        tracking_frame = ttk.Frame(self.notebook)
        self.notebook.add(tracking_frame, text="Трекинг")

        # Верхняя панель с элементами управления
        top_panel = ttk.Frame(tracking_frame, padding=(5, 5, 5, 5))
        top_panel.pack(fill=tk.X)

        # Общее время в верхней панели
        self.total_time_label = ttk.Label(top_panel,
                                          text="Общее время: 00:00:00",
                                          font=('Arial', 10, 'bold'))
        self.total_time_label.pack(side=tk.LEFT, padx=10)

        # Получаем текущие цвета
        colors = self.get_current_colors()

        # Кнопка темы в верхней панели справа
        self.theme_btn = tk.Button(top_panel,
                                   image=self.dark_icon if self.dark_mode else self.light_icon,
                                   command=self.toggle_theme,
                                   bd=0,
                                   highlightthickness=0,
                                   activebackground=colors['active_bg'],
                                   background=colors['bg'])
        self.theme_btn.pack(side=tk.RIGHT, padx=5)

        # обновление фона панели
        top_panel.configure(style='TFrame')  # Для ttk.Frame

        # Основной контент
        main_frame = ttk.Frame(tracking_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)

        # Поле логина (центрированное и выровненное)
        login_frame = ttk.Frame(main_frame)
        login_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        login_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(login_frame, text="Логин:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.login_entry = ttk.Entry(login_frame)
        self.login_entry.grid(row=0, column=1, sticky=tk.EW)
        self.add_placeholder(self.login_entry, "Введите ваш логин")

        # Форма задачи с увеличенными отступами
        task_frame = ttk.LabelFrame(main_frame, text="Новая задача", padding=10)
        task_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.EW)
        task_frame.grid_columnconfigure(1, weight=1)

        # Увеличиваем отступы между полями (pady)
        ttk.Label(task_frame, text="Регресс:").grid(row=0, column=0, sticky=tk.W, pady=(0, 7))
        self.regress_entry = ttk.Entry(task_frame)
        self.regress_entry.grid(row=0, column=1, padx=10, sticky=tk.EW, pady=(0, 7))
        self.add_placeholder(self.regress_entry, "Название поверхности")

        ttk.Label(task_frame, text="Название:").grid(row=1, column=0, sticky=tk.W, pady=7)
        self.name_entry = ttk.Entry(task_frame)
        self.name_entry.grid(row=1, column=1, padx=10, sticky=tk.EW, pady=7)
        self.add_placeholder(self.name_entry, "Название тест-рана")

        ttk.Label(task_frame, text="Ссылка:").grid(row=2, column=0, sticky=tk.W, pady=(7, 0))
        self.link_entry = ttk.Entry(task_frame)
        self.link_entry.grid(row=2, column=1, padx=10, sticky=tk.EW, pady=(7, 0))
        self.add_placeholder(self.link_entry, "Ссылка на тест-ран")

        # Чекбокс и кнопки
        self.extra_time = tk.BooleanVar()
        ttk.Checkbutton(task_frame, text="Доп. время", variable=self.extra_time).grid(
            row=3, columnspan=2, pady=(10, 5))

        # Фрейм для кнопок с отступами
        buttons_frame = ttk.Frame(task_frame)
        buttons_frame.grid(row=4, columnspan=2, pady=(5, 0), sticky=tk.EW)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

        # Кнопки с отступами между ними
        add_btn = ttk.Button(buttons_frame, text="Добавить", command=self.add_task, style="Accent.TButton")
        add_btn.grid(row=0, column=0, padx=(0, 5), sticky=tk.EW)

        finish_btn = ttk.Button(buttons_frame, text="Завершить день", command=self.finish_day, style="Accent.TButton")
        finish_btn.grid(row=0, column=1, padx=(5, 0), sticky=tk.EW)

        # Список задач
        self.tasks_list = ttk.Treeview(main_frame,
                                       columns=('id', 'regress', 'name', 'status', 'time'),
                                       show='headings',
                                       height=12,
                                       style="Treeview")
        self.tasks_list.heading('id', text='ID')
        self.tasks_list.heading('regress', text='Регресс')
        self.tasks_list.heading('name', text='Название')
        self.tasks_list.heading('status', text='Статус')
        self.tasks_list.heading('time', text='Время')
        self.tasks_list.column('id', width=40, anchor=tk.CENTER)
        self.tasks_list.column('status', width=100, anchor=tk.CENTER)
        self.tasks_list.column('time', width=80, anchor=tk.CENTER)
        self.tasks_list.grid(row=2, column=0, columnspan=2, pady=5, sticky=tk.NSEW)
        self.tasks_list.bind('<<TreeviewSelect>>', self.on_task_select)

        # Настройка расширения
        main_frame.grid_rowconfigure(2, weight=1)

    def setup_ui(self):
        # Создаем панель вкладок
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Вкладка трекинга (первая - будет активной по умолчанию)
        self.setup_tracking_tab()

        # Вкладка статистики
        self.setup_stats_tab()

    def add_placeholder(self, entry, text):
        entry.insert(0, text)
        if self.dark_mode:
            entry.config(foreground='#7A7A7A', background='#252525')  # Серый текст на темном фоне
        else:
            entry.config(foreground='grey', background='white')

        entry.bind('<FocusIn>', lambda e: self.on_entry_focus_in(entry, text))
        entry.bind('<FocusOut>', lambda e: self.on_entry_focus_out(entry, text))

    def on_entry_focus_in(self, entry, placeholder):
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            if self.dark_mode:
                entry.config(foreground='#FFFFFF', background='#252525')  # Белый текст в темной теме
            else:
                entry.config(foreground='black', background='white')

    def on_entry_focus_out(self, entry, placeholder):
        if entry.get() == '':
            entry.insert(0, placeholder)
            if self.dark_mode:
                entry.config(foreground='#7A7A7A', background='#252525')
            else:
                entry.config(foreground='grey', background='white')

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
            elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())
            self.update_task_time(self.running_task['id'], elapsed)
            self.total_time += elapsed
        self.running_task = {'id': task_id, 'start_time': datetime.now()}
        self.paused = False
        self.update_tasks()
        self.update_title()

    def clear_task_fields(self):
        self.regress_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.link_entry.delete(0, tk.END)
        self.extra_time.set(False)

    def delete_task(self):
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

            # Обновляем paused_task_id если есть задачи
            if tasks and not self.running_task:
                self.paused_task_id = tasks[0][0]

        except Exception as e:
            messagebox.showerror("Ошибка обновления", str(e))

    def on_task_select(self, event):
        """Обработчик выбора задачи в списке"""
        selected = self.tasks_list.selection()
        if hasattr(self, 'edit_btn'):  # Проверяем существование кнопки
            self.edit_btn['state'] = tk.NORMAL if selected else tk.DISABLED

    def format_time(self, seconds):
        # Форматирование времени
        return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"

    def update_time(self):
        if self.running_task and not self.paused:
            elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())
            current_total = self.total_time + elapsed

            # Обновляем заголовок
            self.update_title()

            # Обновляем задачу в списке
            for item in self.tasks_list.get_children():
                values = self.tasks_list.item(item)['values']
                if values[0] == self.running_task['id']:
                    total_task_time = self.get_task_time(self.running_task['id']) + elapsed
                    self.tasks_list.item(item, values=(
                        values[0],
                        values[1],
                        values[2],
                        '▶ Активна',
                        self.format_time(total_task_time)  # Общее время задачи
                    ))
                    break

        self.root.after(1000, self.update_time)

    def get_task_time(self, task_id):
        """Возвращает сохранённое время задачи из БД"""
        self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def pause_all(self):
        """Остановка всех таймеров по кнопке"""
        if self.running_task:
            elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())
            self.update_task_time(self.running_task['id'], elapsed)
            self.total_time += elapsed
            # Сохраняем текущую задачу и накопленное время
            self.paused_task_id = self.running_task['id']
            self.paused_task_time = self.get_task_time(self.running_task['id'])  # Новое поле
            self.running_task = None

        self.paused = True
        self.update_tasks()
        self.update_total_time()
        self.root.title("Work Time Tracker (⏸)")

    def resume_all(self):
        """Возобновление работы с выбранной задачей"""
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
        if not self.task_exists(task_id):
            messagebox.showwarning("Ошибка", "Выбранная задача больше не существует")
            self.paused_task_id = None
            return

        # Запускаем задачу с сохранённым временем
        self.running_task = {
            'id': task_id,
            'start_time': datetime.now() - timedelta(
                seconds=self.paused_task_time if task_id == getattr(self, 'paused_task_id', None) else 0
            )
        }

        self.paused = False
        self.update_tasks()
        self.update_title()

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
            # Дополнительные настройки для темной темы
            matplotlib.rcParams['axes.facecolor'] = '#252525'
            matplotlib.rcParams['figure.facecolor'] = '#1E1E1E'
            matplotlib.rcParams['grid.color'] = '#3A3A3A'
        else:
            plt.style.use('default')
            # Сброс к стандартным настройкам
            matplotlib.rcParams.update(matplotlib.rcParamsDefault)

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
        # Обновляем иконку кнопки
        self.theme_btn.config(image=self.dark_icon if self.dark_mode else self.light_icon)
        self.apply_theme()
        self.save_theme()

    def apply_theme(self):
        """Применяет текущую тему ко всем элементам интерфейса"""
        if self.dark_mode:
            # Темная тема
            bg_color = "#1E1E1E"
            fg_color = "#E0E0E0"
            entry_bg = "#252525"
            entry_fg = "#FFFFFF"
            button_bg = "#333333"
            button_fg = "#E0E0E0"
            list_bg = "#252525"
            list_fg = "#FFFFFF"
            list_alt_bg = "#2D2D2D"
            frame_bg = "#252525"
            label_fg = "#E0E0E0"
            separator_color = "#3A3A3A"
            tab_bg = "#333333"
            tab_fg = "#E0E0E0"
            tab_selected_bg = "#252525"
        else:
            # Светлая тема
            bg_color = "#F5F5F5"
            fg_color = "#000000"
            entry_bg = "#FFFFFF"
            entry_fg = "#000000"
            button_bg = "#E0E0E0"
            button_fg = "#000000"
            list_bg = "#FFFFFF"
            list_fg = "#000000"
            list_alt_bg = "#F0F0F0"
            frame_bg = "#FFFFFF"
            label_fg = "#000000"
            separator_color = "#D0D0D0"
            tab_bg = "#F0F0F0"
            tab_fg = "#000000"
            tab_selected_bg = "#FFFFFF"

        style = ttk.Style()
        style.theme_use('clam')

        # Общие настройки
        style.configure(".",
                        background=bg_color,
                        foreground=fg_color,
                        fieldbackground=entry_bg,
                        insertcolor=fg_color)

        # Настройки для вкладок
        style.configure("TNotebook", background=bg_color)
        style.configure("TNotebook.Tab",
                        background=tab_bg,
                        foreground=tab_fg,
                        padding=[10, 5],
                        borderwidth=1)
        style.map("TNotebook.Tab",
                  background=[("selected", tab_selected_bg)],
                  foreground=[("selected", tab_fg)])

        # Настройки для Treeview (списка задач)
        style.configure("Treeview",
                        background=list_bg,
                        foreground=list_fg,
                        fieldbackground=list_bg,
                        borderwidth=0,
                        relief='flat')
        style.configure("Treeview.Heading",
                        background=button_bg,
                        foreground=button_fg,
                        borderwidth=1,
                        relief='flat')
        style.configure("Treeview.Separator",
                        background=separator_color)

        style.map("Treeview",
                  background=[('selected', '#0078D7')],
                  foreground=[('selected', 'white')])

        # Настройки для кнопок
        style.configure("TButton",
                        background=button_bg,
                        foreground=button_fg,
                        bordercolor=bg_color,
                        borderwidth=1)
        style.map("TButton",
                  background=[('active', button_bg)],
                  relief=[('active', 'flat'), ('!active', 'flat')])

        # Настройки для фреймов
        style.configure("TFrame", background=frame_bg)
        style.configure("TLabel", background=frame_bg, foreground=label_fg)
        style.configure("TEntry",
                        fieldbackground=entry_bg,
                        foreground=entry_fg,
                        insertcolor=fg_color)

        # Применяем цвета ко всем виджетам
        self.root.config(bg=bg_color)

        # Обновляем график
        self.update_graph_theme()

        # Принудительно обновляем стиль Treeview
        if hasattr(self, 'tasks_list'):
            self.tasks_list.config(style="Treeview")

        # Настройки для всех кнопок
        style.configure("TButton",
                        padding=5,
                        relief="flat",
                        borderwidth=1)

        style.map("TButton",
                  background=[('active', button_bg)],
                  relief=[('pressed', 'sunken'), ('!pressed', 'flat')])

        # Стиль для заголовков столбцов
        style.configure("Treeview.Heading",
                        font=('Arial', 9, 'bold'),
                        padding=(5, 3, 5, 3),
                        relief="flat")

        # Стиль для обычных кнопок
        style.configure("Accent.TButton",
                        font=('Arial', 9, 'bold'),
                        padding=5,
                        relief="flat")

        # Границы для фреймов
        style.configure("TLabelframe",
                        borderwidth=1,
                        relief="solid",
                        padding=5)

        style.configure("TLabelframe.Label",
                        font=('Arial', 9, 'bold'))

        style.configure("Treeview",
                        borderwidth=1,
                        relief="solid",
                        rowheight=25)

        style.configure("Treeview.Heading",
                        borderwidth=1,
                        relief="solid",
                        padding=5)

        style.configure("Treeview",
                        background=list_bg,
                        foreground=list_fg,
                        fieldbackground=list_bg,
                        borderwidth=1,
                        relief="solid",
                        rowheight=25)

        style.configure("Treeview.Heading",
                        background=button_bg,
                        foreground=button_fg,
                        borderwidth=1,
                        relief="solid",
                        padding=5,
                        font=('Arial', 9, 'bold'))

        style.map("Treeview.Heading",
                  background=[('active', button_bg)],
                  relief=[('pressed', 'sunken'), ('!pressed', 'solid')])

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

    def update_title(self):
        """Обновляет заголовок окна с полными названиями задач"""
        if self.running_task and not self.paused:
            elapsed = int((datetime.now() - self.running_task['start_time']).total_seconds())

            # Получаем полные данные задачи без обрезки
            self.c.execute("SELECT regress, name FROM tasks WHERE id=?", (self.running_task['id'],))
            regress, name = self.c.fetchone()

            total_task_time = self.get_task_time(self.running_task['id']) + elapsed

            self.root.title(
                self.title_template.format(
                    regress=regress,  # Полное название регресса
                    name=name,  # Полное название задачи
                    time=self.format_time(total_task_time),
                    total=self.format_time(self.total_time + elapsed)
                )
            )
        elif self.paused:
            self.root.title("Work Time Tracker (⏸)")
        else:
            self.root.title("Work Time Tracker")

    def get_task_name(self, task_id):
        """Возвращает название задачи по ID"""
        self.c.execute("SELECT name FROM tasks WHERE id=?", (task_id,))
        result = self.c.fetchone()
        return result[0] if result else "Новая задача"

    def get_task_details(self, task_id):
        """Возвращает кортеж (regress, name) для задачи"""
        self.c.execute("SELECT regress, name FROM tasks WHERE id=?", (task_id,))
        return self.c.fetchone() or ("", "")

    def setup_task_context_menu(self):
        """Создаёт контекстное меню для задач"""
        self.task_context_menu = tk.Menu(self.root, tearoff=0)

        if self.dark_mode:
            menu_bg = "#2D2D2D"
            menu_fg = "#E0E0E0"
            active_bg = "#2D5D7B"
            active_fg = "#FFFFFF"
        else:
            menu_bg = "#F5F5F5"
            menu_fg = "#000000"
            active_bg = "#0078D7"
            active_fg = "#FFFFFF"

        self.task_context_menu.configure(
            bg=menu_bg,
            fg=menu_fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            selectcolor=active_bg
        )

        # Элементы меню
        self.task_context_menu.add_command(
            label="Продолжить",
            command=self.resume_selected_task
        )
        self.task_context_menu.add_command(
            label="Пауза",
            command=self.pause_all
        )
        self.task_context_menu.add_command(
            label="Редактировать",
            command=self.edit_selected_task
        )
        self.task_context_menu.add_command(
            label="Копировать ссылку",
            command=self.copy_task_link
        )
        self.task_context_menu.add_separator()
        self.task_context_menu.add_command(
            label="Удалить",
            command=self.delete_selected_task
        )

        # Привязка к списку задач
        self.tasks_list.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            item = self.tasks_list.identify_row(event.y)
            if item:
                self.tasks_list.selection_set(item)
                task_id = self.tasks_list.item(item)['values'][0]
                is_active = self.running_task and self.running_task['id'] == task_id

                # Обновляем состояния пунктов меню
                self.task_context_menu.entryconfig("Продолжить",
                                                   state=tk.NORMAL if not self.running_task else tk.DISABLED)
                self.task_context_menu.entryconfig("Пауза",
                                                   state=tk.NORMAL if is_active else tk.DISABLED)
                self.task_context_menu.entryconfig("Редактировать",
                                                   state=tk.NORMAL)
                self.task_context_menu.entryconfig("Копировать ссылку",
                                                   state=tk.NORMAL)
                self.task_context_menu.entryconfig("Удалить",
                                                   state=tk.NORMAL)

                self.task_context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"Ошибка показа меню: {e}")

    def edit_selected_task(self):
        """Редактирует выбранную задачу"""
        self.edit_task()

    def copy_task_link(self):
        """Копирует ссылку задачи в буфер обмена"""
        selected = self.tasks_list.selection()
        if selected:
            task_id = self.tasks_list.item(selected[0])['values'][0]
            self.c.execute("SELECT link FROM tasks WHERE id=?", (task_id,))
            result = self.c.fetchone()
            if result and result[0]:
                self.root.clipboard_clear()
                self.root.clipboard_append(result[0])
                self.show_notification("Ссылка скопирована в буфер")

    def show_notification(self, message, duration=2000):
        """Показывает красивое всплывающее уведомление рядом с курсором"""
        colors = self.get_current_colors()

        # Получаем позицию курсора
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()

        notif = Toplevel(self.root)
        notif.overrideredirect(True)
        notif.geometry(f"+{x + 15}+{y + 15}")  # Смещаем немного от курсора
        notif.configure(bg=colors['bg'])

        Label(notif,
              text=message,
              bg=colors['bg'],
              fg=colors['fg'],
              padx=15,
              pady=5,
              font=('Arial', 9),
              relief="solid",
              borderwidth=1).pack()

        notif.after(duration, notif.destroy)

    def resume_selected_task(self):
        """Продолжает выбранную задачу из контекстного меню"""
        selected = self.tasks_list.selection()
        if selected:
            task_id = self.tasks_list.item(selected[0])['values'][0]
            if not self.running_task:  # Если нет активной задачи
                self.paused_task_id = task_id
                self.resume_all()

    def check_for_paused_task(self):
        """Проверяет есть ли задачи для продолжения при запуске"""
        if not self.running_task:
            try:
                self.c.execute("SELECT id FROM tasks WHERE date=? LIMIT 1",
                               (datetime.now().strftime("%d.%m.%Y"),))
                result = self.c.fetchone()
                if result:
                    self.paused_task_id = result[0]
            except Exception as e:
                print(f"Ошибка при проверке задач: {e}")

    def delete_selected_task(self):
        """Удаляет выбранную задачу через контекстное меню"""
        selected = self.tasks_list.selection()
        if selected:
            self.delete_task()

    def create_tooltip(self, widget, text):

        def enter(event):
            self.tooltips[widget] = tk.Toplevel(widget)
            tip = self.tooltips[widget]
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
            label = tk.Label(tip, text=text, background="#ffffe0",
                             relief="solid", borderwidth=1, padx=4, pady=2)
            label.pack()

        def leave(event):
            if widget in self.tooltips:
                self.tooltips[widget].destroy()
                del self.tooltips[widget]

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def get_current_colors(self):
        """Возвращает текущие цвета в зависимости от темы"""
        if self.dark_mode:
            return {
                'bg': "#1E1E1E",
                'fg': "#E0E0E0",
                'active_bg': "#2D2D2D",
                'button_bg': "#333333",
                'border': "#3A3A3A"
            }
        else:
            return {
                'bg': "#F5F5F5",
                'fg': "#000000",
                'active_bg': "#E0E0E0",
                'button_bg': "#F0F0F0",
                'border': "#D0D0D0"
            }

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