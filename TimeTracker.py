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
        self.setup_db()
        self.setup_ui()
        self.setup_tray()
        self.running_task = None
        self.paused = False
        self.total_time = 0
        self.root.after(1000, self.update_time)
        self.update_tasks()
        self.update_total_time()

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

    def setup_ui(self):
        # Инициализация UI
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Поле логина
        ttk.Label(main_frame, text="Логин:").grid(row=0, column=0, sticky=tk.W)
        self.login_entry = ttk.Entry(main_frame, width=30)
        self.login_entry.grid(row=0, column=1, padx=5)

        # Форма задачи
        task_frame = ttk.LabelFrame(main_frame, text="Новая задача", padding=10)
        task_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky=tk.W)

        ttk.Label(task_frame, text="Регресс:").grid(row=0, column=0)
        self.regress_entry = ttk.Entry(task_frame)
        self.regress_entry.grid(row=0, column=1, padx=5)

        ttk.Label(task_frame, text="Название:").grid(row=1, column=0)
        self.name_entry = ttk.Entry(task_frame)
        self.name_entry.grid(row=1, column=1, padx=5)

        ttk.Label(task_frame, text="Ссылка:").grid(row=2, column=0)
        self.link_entry = ttk.Entry(task_frame)
        self.link_entry.grid(row=2, column=1, padx=5)

        self.extra_time = tk.BooleanVar()
        ttk.Checkbutton(task_frame, text="Доп. время", variable=self.extra_time).grid(row=3, columnspan=2)

        ttk.Button(task_frame, text="Добавить", command=self.add_task).grid(row=4, columnspan=2, pady=5)

        # Список задач
        self.tasks_list = ttk.Treeview(main_frame, columns=('id', 'regress', 'name', 'status', 'time'), show='headings')
        self.tasks_list.heading('id', text='ID')
        self.tasks_list.heading('regress', text='Регресс')
        self.tasks_list.heading('name', text='Название')
        self.tasks_list.heading('status', text='Статус')
        self.tasks_list.heading('time', text='Время')
        self.tasks_list.column('status', width=100, anchor=tk.CENTER)
        self.tasks_list.grid(row=2, column=0, columnspan=2, pady=10)
        self.tasks_list.bind('<<TreeviewSelect>>', self.on_task_select)

        # Панель управления
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, columnspan=2, pady=10)

        ttk.Button(control_frame, text="Удалить", command=self.delete_task).pack(side=tk.LEFT, padx=5)
        self.total_time_label = ttk.Label(control_frame, text="Общее время: 00:00:00")
        self.total_time_label.pack(side=tk.LEFT, padx=10)
        self.pause_btn = ttk.Button(control_frame, text="Пауза", command=self.pause_all)
        self.pause_btn.pack(side=tk.LEFT)
        self.resume_btn = ttk.Button(control_frame, text="Продолжить", command=self.resume_all, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Завершить день", command=self.finish_day).pack(side=tk.LEFT)

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

            if self.extra_time.get():
                self.c.execute("INSERT INTO tasks (date, login, regress, name, link, time) VALUES (?,?,?,?,?,?)",
                               (data[0], data[1], data[2], "[ДОП] " + data[3], data[4], 0))

            self.conn.commit()
            self.update_tasks()
            self.clear_task_fields()
            self.update_total_time()
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))

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

        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)
            self.update_total_time()

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
        # Обновление отображения времени в таске
        if self.running_task and not self.paused:
            current_time = datetime.now()
            elapsed = (current_time - self.running_task['start_time']).total_seconds()
            total_task_time = self.get_task_time(self.running_task['id']) + int(elapsed)

            # Обновляем общее время
            current_total = self.total_time + int(elapsed)
            self.total_time_label.config(text=f"Общее время: {self.format_time(current_total)}")

            # Обновляем время текущей задачи
            for item in self.tasks_list.get_children():
                values = self.tasks_list.item(item)['values']
                if values[0] == self.running_task['id']:
                    self.tasks_list.item(item, values=(
                        values[0],
                        values[1],
                        values[2],
                        '▶ Активна',
                        self.format_time(total_task_time)
                    ))

        self.root.after(1000, self.update_time)

    def get_task_time(self, task_id):
        #Получение времени задачи из БД
        self.c.execute("SELECT time FROM tasks WHERE id=?", (task_id,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def pause_all(self):
        # Остановка всех таймеров по кнопке
        if self.running_task:
            elapsed = (datetime.now() - self.running_task['start_time']).total_seconds()
            self.update_task_time(self.running_task['id'], int(elapsed))
            self.total_time += int(elapsed)
            self.running_task = None
        self.paused = True
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)
        self.update_tasks()
        self.update_total_time()

    def resume_all(self):
        # Возобновление работы по кнопке
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

    def hide_to_tray(self):
        # Скрытие окна в трей ДОРАБОТАТЬ ФЛОУ ФОНОВОЙ РАБОТЫ
        self.root.withdraw()

    def restore_window(self, icon=None, item=None):
        # Восстановление окна из трея
        self.root.deiconify()

    def exit_app(self):
        # Корректный(?) выход из программы
        self.conn.close()
        self.tray_icon.stop()
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = TimeTracker(root)
    root.protocol('WM_DELETE_WINDOW', app.hide_to_tray)
    root.mainloop()
