import os
import sys
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
import threading
import time
import shutil


# ------------------- ОПРЕДЕЛЕНИЕ ПУТЕЙ ДЛЯ EXE -------------------
def get_base_dir():
    """Возвращает путь к папке, где находится исполняемый файл (или скрипт)"""
    if getattr(sys, 'frozen', False):
        # Запущено как скомпилированный .exe
        return os.path.dirname(sys.executable)
    else:
        # Запущено как скрипт Python
        return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()

# Папки и файлы внутри BASE_DIR
NOTES_DIR = os.path.join(BASE_DIR, "notes")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")

# Создаём папку для заметок, если её нет
if not os.path.exists(NOTES_DIR):
    os.makedirs(NOTES_DIR)

# ------------------- ПРОВЕРКА MARKDOWN -------------------
try:
    import markdown

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# ------------------- ЦВЕТОВЫЕ ТЕМЫ -------------------
THEMES = {
    "Современная тёмная": {
        "bg": "#0F0F0F",
        "left_bg": "#1A1A1A",
        "right_bg": "#0F0F0F",
        "list_bg": "#1A1A1A",
        "list_select": "#3A3A3A",
        "btn_new": "#4CAF50",
        "btn_save": "#FF9800",
        "btn_del": "#F44336",
        "btn_rename": "#2196F3",
        "title_bg": "#2D2D2D",
        "text_bg": "#2D2D2D",
        "status_bg": "#1A1A1A",
        "search_bg": "#2D2D2D",
        "highlight": "#FFD700"
    },
    "Светлая": {
        "bg": "#F5F5F5",
        "left_bg": "#E8E8E8",
        "right_bg": "#FFFFFF",
        "list_bg": "#FFFFFF",
        "list_select": "#D3D3D3",
        "btn_new": "#4CAF50",
        "btn_save": "#FF9800",
        "btn_del": "#F44336",
        "btn_rename": "#2196F3",
        "title_bg": "#F0F0F0",
        "text_bg": "#FFFFFF",
        "status_bg": "#E8E8E8",
        "search_bg": "#FFFFFF",
        "highlight": "#FFD700"
    }
}


# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------
def safe_filename(title):
    return re.sub(r'[\\/*?:"<>|]', '_', title).strip() + ".md"


def get_title_from_content(content):
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip()
    return None


def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_favorites():
    return load_json(FAVORITES_FILE, [])


def save_favorites(favorites):
    save_json(FAVORITES_FILE, favorites)


def load_settings():
    settings = load_json(SETTINGS_FILE, {"theme": "Современная тёмная", "font_size": 10})
    if settings.get("theme") not in THEMES:
        settings["theme"] = "Современная тёмная"
    return settings


def save_settings(settings):
    save_json(SETTINGS_FILE, settings)


# ------------------- ОСНОВНОЙ КЛАСС -------------------
class ModernMarkdownNotes:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ Markdown Заметки")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self.current_file = None
        self.current_title = None
        self.unsaved_changes = False
        self.favorites = load_favorites()
        self.settings = load_settings()
        self.current_theme = self.settings.get("theme", "Современная тёмная")
        self.colors = THEMES[self.current_theme]
        self.font_size = self.settings.get("font_size", 10)
        self.search_filter = ""
        self.auto_save_running = True
        self.preview_window = None
        self.show_favorites_only = False

        self.create_widgets()
        self.refresh_notes_list()
        self.bind_shortcuts()
        self.start_auto_save()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Основной контейнер
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая панель (список заметок)
        left_frame = tk.Frame(main_paned, bg=self.colors['left_bg'], relief=tk.FLAT)
        main_paned.add(left_frame, weight=2)

        # Поиск
        search_frame = tk.Frame(left_frame, bg=self.colors['left_bg'])
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(search_frame, text="🔍 Поиск:", bg=self.colors['left_bg'],
                 fg="white" if self.current_theme == "Современная тёмная" else "black").pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search_frame, bg=self.colors['search_bg'], relief=tk.FLAT)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.search_entry.bind("<KeyRelease>", self.on_search)

        # Кнопка избранного
        self.fav_btn = tk.Button(left_frame, text="⭐ Избранное", command=self.toggle_fav_filter,
                                 bg=self.colors['btn_rename'], relief=tk.FLAT, padx=5, pady=2)
        self.fav_btn.pack(pady=(0, 5))

        # Список заметок
        tk.Label(left_frame, text="📄 Заметки", font=("Segoe UI", 12, "bold"),
                 bg=self.colors['left_bg'],
                 fg="white" if self.current_theme == "Современная тёмная" else "black").pack(pady=(5, 0))

        list_frame = tk.Frame(left_frame, bg=self.colors['list_bg'], relief=tk.FLAT)
        list_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, bg=self.colors['list_bg'],
                                  selectbackground=self.colors['list_select'],
                                  font=("Segoe UI", self.font_size), relief=tk.FLAT, bd=0,
                                  highlightthickness=0,
                                  fg="white" if self.current_theme == "Современная тёмная" else "black")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = tk.Scrollbar(list_frame, command=self.listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_note_select)

        # Кнопки управления заметками
        btn_frame = tk.Frame(left_frame, bg=self.colors['left_bg'])
        btn_frame.pack(pady=10)
        self.create_flat_button(btn_frame, "➕ Новая", self.new_note, self.colors['btn_new'], width=8)
        self.create_flat_button(btn_frame, "✏️ Переименовать", self.rename_note, self.colors['btn_rename'], width=10)
        self.create_flat_button(btn_frame, "🗑️ Удалить", self.delete_note, self.colors['btn_del'], width=8)

        # Кнопки экспорта/импорта
        import_export_frame = tk.Frame(left_frame, bg=self.colors['left_bg'])
        import_export_frame.pack(pady=5)
        self.create_flat_button(import_export_frame, "📤 Экспорт MD", self.export_markdown, self.colors['btn_save'],
                                width=10)
        self.create_flat_button(import_export_frame, "📥 Импорт MD", self.import_markdown, self.colors['btn_new'],
                                width=10)

        # Правая панель (редактор)
        right_frame = tk.Frame(main_paned, bg=self.colors['right_bg'])
        main_paned.add(right_frame, weight=5)

        # Панель инструментов
        toolbar = tk.Frame(right_frame, bg=self.colors['right_bg'])
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        self.create_flat_button(toolbar, "B", lambda: self.insert_format("**", "**"), self.colors['btn_save'], width=2)
        self.create_flat_button(toolbar, "I", lambda: self.insert_format("*", "*"), self.colors['btn_save'], width=2)
        self.create_flat_button(toolbar, "H1", lambda: self.insert_format("# ", ""), self.colors['btn_save'], width=2)
        self.create_flat_button(toolbar, "H2", lambda: self.insert_format("## ", ""), self.colors['btn_save'], width=2)
        self.create_flat_button(toolbar, "•", lambda: self.insert_format("- ", ""), self.colors['btn_save'], width=2)
        self.create_flat_button(toolbar, "🔗", lambda: self.insert_format("[", "](url)"), self.colors['btn_save'],
                                width=2)
        self.create_flat_button(toolbar, "⭐", self.toggle_favorite, self.colors['btn_rename'], width=2)

        # Настройки шрифта и темы
        settings_frame = tk.Frame(toolbar, bg=self.colors['right_bg'])
        settings_frame.pack(side=tk.RIGHT, padx=5)

        tk.Label(settings_frame, text="🔤", bg=self.colors['right_bg'],
                 fg="white" if self.current_theme == "Современная тёмная" else "black").pack(side=tk.LEFT)
        self.font_size_spin = tk.Spinbox(settings_frame, from_=8, to=20, width=3,
                                         command=self.change_font_size)
        self.font_size_spin.delete(0, tk.END)
        self.font_size_spin.insert(0, self.font_size)
        self.font_size_spin.pack(side=tk.LEFT)

        tk.Label(settings_frame, text="🎨", bg=self.colors['right_bg'],
                 fg="white" if self.current_theme == "Современная тёмная" else "black").pack(side=tk.LEFT, padx=(5, 0))
        self.theme_combo = ttk.Combobox(settings_frame, values=list(THEMES.keys()),
                                        state="readonly", width=15)
        self.theme_combo.set(self.current_theme)
        self.theme_combo.pack(side=tk.LEFT)
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)

        # Заголовок заметки
        title_frame = tk.Frame(right_frame, bg=self.colors['right_bg'])
        title_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(title_frame, text="Заголовок:", font=("Segoe UI", 10, "bold"),
                 bg=self.colors['right_bg'],
                 fg="white" if self.current_theme == "Современная тёмная" else "black").pack(side=tk.LEFT)
        self.title_entry = tk.Entry(title_frame, font=("Segoe UI", 11), bg=self.colors['title_bg'],
                                    relief=tk.FLAT, bd=1,
                                    fg="white" if self.current_theme == "Современная тёмная" else "black")
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        self.title_entry.bind("<KeyRelease>", lambda e: self.mark_unsaved())

        # Текстовая область
        text_frame = tk.Frame(right_frame, bg=self.colors['right_bg'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        self.text_area = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", self.font_size),
                                 bg=self.colors['text_bg'], relief=tk.FLAT, bd=1,
                                 undo=True,
                                 fg="white" if self.current_theme == "Современная тёмная" else "black")
        self.text_area.pack(fill=tk.BOTH, expand=True)

        scroll_text = tk.Scrollbar(self.text_area, command=self.text_area.yview)
        scroll_text.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.config(yscrollcommand=scroll_text.set)
        self.text_area.bind("<KeyRelease>", lambda e: self.mark_unsaved())

        # Кнопки действий
        action_frame = tk.Frame(right_frame, bg=self.colors['right_bg'])
        action_frame.pack(fill=tk.X, pady=5)
        self.create_flat_button(action_frame, "💾 Сохранить (Ctrl+S)", self.save_note, self.colors['btn_save'],
                                width=15)
        self.create_flat_button(action_frame, "👁️ Предпросмотр", self.preview_markdown, self.colors['btn_rename'],
                                width=12)

        # Статусная строка
        self.status_bar = tk.Label(self.root, text="Готово", font=("Segoe UI", 9),
                                   bg=self.colors['status_bg'],
                                   fg="white" if self.current_theme == "Современная тёмная" else "black",
                                   relief=tk.FLAT, anchor=tk.W, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_flat_button(self, parent, text, command, bg_color, width=None):
        btn = tk.Button(parent, text=text, command=command, bg=bg_color,
                        font=("Segoe UI", 9), relief=tk.FLAT, bd=0, padx=5, pady=2)
        if width:
            btn.config(width=width)
        btn.pack(side=tk.LEFT, padx=2)

        def on_enter(e):
            btn.config(bg=self.darken_color(bg_color))

        def on_leave(e):
            btn.config(bg=bg_color)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def darken_color(self, hex_color, factor=0.9):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r, g, b = int(r * factor), int(g * factor), int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def change_theme(self, event=None):
        theme_name = self.theme_combo.get()
        if theme_name in THEMES:
            self.current_theme = theme_name
            self.colors = THEMES[theme_name]
            self.settings["theme"] = theme_name
            save_settings(self.settings)
            self.root.destroy()
            new_root = tk.Tk()
            app = ModernMarkdownNotes(new_root)
            new_root.mainloop()

    def change_font_size(self):
        try:
            size = int(self.font_size_spin.get())
            self.font_size = size
            self.settings["font_size"] = size
            save_settings(self.settings)
            self.text_area.config(font=("Consolas", size))
            self.listbox.config(font=("Segoe UI", size))
        except:
            pass

    def insert_format(self, prefix, suffix):
        if self.text_area.tag_ranges("sel"):
            selected = self.text_area.get("sel.first", "sel.last")
            self.text_area.insert("sel.first", prefix)
            self.text_area.insert("sel.last", suffix)
            self.text_area.tag_add("sel", "sel.first", f"sel.last+{len(suffix)}c")
        else:
            self.text_area.insert(tk.INSERT, prefix + suffix)
            self.text_area.mark_set("insert", f"insert-{len(suffix)}c")
        self.mark_unsaved()

    def mark_unsaved(self):
        if not self.unsaved_changes:
            self.unsaved_changes = True
            self.status_bar.config(text="✏️ Есть несохранённые изменения")

    def clear_unsaved(self):
        self.unsaved_changes = False
        self.status_bar.config(text="✅ Заметка сохранена")
        self.root.after(2000, lambda: self.status_bar.config(text="Готово"))

    def start_auto_save(self):
        def auto_save_loop():
            while self.auto_save_running:
                time.sleep(30)
                if self.unsaved_changes and self.current_file:
                    self.root.after(0, self.save_note)

        thread = threading.Thread(target=auto_save_loop, daemon=True)
        thread.start()

    def on_search(self, event=None):
        self.search_filter = self.search_entry.get().strip().lower()
        self.refresh_notes_list()

    def toggle_fav_filter(self):
        self.show_favorites_only = not self.show_favorites_only
        self.fav_btn.config(relief=tk.SUNKEN if self.show_favorites_only else tk.RAISED)
        self.refresh_notes_list()

    def toggle_favorite(self):
        if not self.current_file:
            return
        if self.current_file in self.favorites:
            self.favorites.remove(self.current_file)
            self.status_bar.config(text="⭐ Удалено из избранного")
        else:
            self.favorites.append(self.current_file)
            self.status_bar.config(text="⭐ Добавлено в избранное")
        save_favorites(self.favorites)
        self.refresh_notes_list()

    def refresh_notes_list(self):
        self.listbox.delete(0, tk.END)
        files = [f for f in os.listdir(NOTES_DIR) if f.endswith(".md")]
        files.sort()
        self.files_list = []

        for file in files:
            path = os.path.join(NOTES_DIR, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    title = get_title_from_content(content) or file[:-3]
            except:
                title = file[:-3]

            # Фильтрация по поиску
            if self.search_filter and self.search_filter not in title.lower() and self.search_filter not in content.lower():
                continue

            # Фильтрация по избранному
            if self.show_favorites_only and file not in self.favorites:
                continue

            self.files_list.append(file)
            display = title
            if file in self.favorites:
                display = "⭐ " + display
            self.listbox.insert(tk.END, display)

    def get_current_file_from_index(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx < len(self.files_list):
            return self.files_list[idx]
        return None

    def on_note_select(self, event=None):
        filename = self.get_current_file_from_index()
        if not filename:
            return

        path = os.path.join(NOTES_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить заметку: {e}")
            return

        if self.unsaved_changes:
            if not messagebox.askyesno("Несохранённые изменения",
                                       "Текущая заметка не сохранена. Всё равно переключиться?"):
                return

        title = get_title_from_content(content) or filename[:-3]
        self.current_file = filename
        self.current_title = title
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, title)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)
        self.unsaved_changes = False
        self.status_bar.config(text=f"Заметка загружена: {title}")

    def new_note(self):
        if self.unsaved_changes:
            if messagebox.askyesno("Несохранённые изменения",
                                   "Сохранить текущую заметку перед созданием новой?"):
                self.save_note()
            else:
                self.unsaved_changes = False

        title = simpledialog.askstring("Новая заметка", "Введите заголовок:")
        if not title:
            return

        filename = safe_filename(title)
        path = os.path.join(NOTES_DIR, filename)

        if os.path.exists(path):
            messagebox.showerror("Ошибка", "Заметка с таким заголовком уже существует.")
            return

        content = f"# {title}\n\n"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать заметку: {e}")
            return

        self.refresh_notes_list()
        for i, fname in enumerate(self.files_list):
            if fname == filename:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(i)
                self.listbox.see(i)
                self.on_note_select()
                break
        self.status_bar.config(text="✨ Новая заметка создана")

    def save_note(self):
        if not self.current_file:
            messagebox.showinfo("Информация", "Сначала выберите или создайте заметку.")
            return

        new_title = self.title_entry.get().strip()
        if not new_title:
            messagebox.showwarning("Предупреждение", "Заголовок не может быть пустым.")
            return

        content = self.text_area.get("1.0", tk.END).rstrip("\n")
        lines = content.splitlines()
        if not lines or not lines[0].startswith("# "):
            content = f"# {new_title}\n\n{content}"

        new_filename = safe_filename(new_title)
        old_path = os.path.join(NOTES_DIR, self.current_file)
        new_path = os.path.join(NOTES_DIR, new_filename)

        if new_filename != self.current_file:
            if os.path.exists(new_path):
                messagebox.showerror("Ошибка", "Заметка с таким заголовком уже существует.")
                return
            try:
                os.rename(old_path, new_path)
                if self.current_file in self.favorites:
                    self.favorites.remove(self.current_file)
                    self.favorites.append(new_filename)
                save_favorites(self.favorites)
                self.current_file = new_filename
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось переименовать файл: {e}")
                return

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить заметку: {e}")
            return

        self.current_title = new_title
        self.refresh_notes_list()

        for i, fname in enumerate(self.files_list):
            if fname == self.current_file:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(i)
                self.listbox.see(i)
                break

        self.clear_unsaved()

    def delete_note(self):
        if not self.current_file:
            messagebox.showinfo("Информация", "Выберите заметку для удаления.")
            return

        if messagebox.askyesno("Подтверждение", f"Удалить заметку \"{self.current_title}\"?"):
            try:
                os.remove(os.path.join(NOTES_DIR, self.current_file))
                if self.current_file in self.favorites:
                    self.favorites.remove(self.current_file)
                save_favorites(self.favorites)
                self.current_file = None
                self.current_title = None
                self.title_entry.delete(0, tk.END)
                self.text_area.delete("1.0", tk.END)
                self.refresh_notes_list()
                self.status_bar.config(text="🗑️ Заметка удалена")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить: {e}")

    def rename_note(self):
        if not self.current_file:
            messagebox.showinfo("Информация", "Выберите заметку для переименования.")
            return

        new_title = simpledialog.askstring("Переименовать", "Новый заголовок:",
                                           initialvalue=self.current_title)
        if not new_title or new_title == self.current_title:
            return

        new_filename = safe_filename(new_title)
        old_path = os.path.join(NOTES_DIR, self.current_file)
        new_path = os.path.join(NOTES_DIR, new_filename)

        if os.path.exists(new_path):
            messagebox.showerror("Ошибка", "Заметка с таким заголовком уже существует.")
            return

        try:
            os.rename(old_path, new_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось переименовать файл: {e}")
            return

        if self.current_file in self.favorites:
            self.favorites.remove(self.current_file)
            self.favorites.append(new_filename)
        save_favorites(self.favorites)

        self.current_file = new_filename
        self.current_title = new_title
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, new_title)
        self.refresh_notes_list()
        self.status_bar.config(text="📝 Заметка переименована")

    def export_markdown(self):
        """Экспорт текущей заметки в формате Markdown"""
        if not self.current_file:
            messagebox.showinfo("Информация", "Выберите заметку для экспорта.")
            return

        content = self.text_area.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Предупреждение", "Заметка пуста.")
            return

        # Предлагаем сохранить файл
        default_filename = safe_filename(self.current_title).replace('.md', '')
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Экспорт заметки в Markdown"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.status_bar.config(text=f"✅ Заметка экспортирована: {os.path.basename(file_path)}")
                messagebox.showinfo("Успех", f"Заметка успешно экспортирована в:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось экспортировать заметку:\n{e}")
                self.status_bar.config(text="❌ Ошибка экспорта")

    def import_markdown(self):
        """Импорт заметки из файла Markdown"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")],
            title="Импорт заметки из Markdown"
        )

        if not file_path:
            return

        try:
            # Читаем содержимое файла
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Определяем заголовок из содержимого или из имени файла
            title = get_title_from_content(content)
            if not title:
                # Берём имя файла без расширения
                title = os.path.splitext(os.path.basename(file_path))[0]

            # Спрашиваем пользователя о заголовке
            new_title = simpledialog.askstring(
                "Импорт заметки",
                f"Введите заголовок для импортируемой заметки:",
                initialvalue=title
            )

            if not new_title:
                return

            # Создаём безопасное имя файла
            filename = safe_filename(new_title)
            save_path = os.path.join(NOTES_DIR, filename)

            # Проверяем, существует ли уже такая заметка
            if os.path.exists(save_path):
                overwrite = messagebox.askyesno(
                    "Заметка существует",
                    f"Заметка \"{new_title}\" уже существует.\nЗаменить её?"
                )
                if not overwrite:
                    return

            # Если в содержимом нет заголовка, добавляем его
            lines = content.splitlines()
            if not lines or not lines[0].startswith("# "):
                content = f"# {new_title}\n\n{content}"

            # Сохраняем заметку
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Обновляем список заметок
            self.refresh_notes_list()

            # Выбираем импортированную заметку
            for i, fname in enumerate(self.files_list):
                if fname == filename:
                    self.listbox.selection_clear(0, tk.END)
                    self.listbox.selection_set(i)
                    self.listbox.see(i)
                    self.on_note_select()
                    break

            self.status_bar.config(text=f"✅ Заметка импортирована: {new_title}")
            messagebox.showinfo("Успех", f"Заметка \"{new_title}\" успешно импортирована!")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось импортировать заметку:\n{e}")
            self.status_bar.config(text="❌ Ошибка импорта")

    def preview_markdown(self):
        if not MARKDOWN_AVAILABLE:
            messagebox.showerror("Ошибка", "Для предпросмотра установите библиотеку markdown:\npip install markdown")
            return

        content = self.text_area.get("1.0", tk.END).strip()
        if not content:
            return

        html = markdown.markdown(content)

        if self.preview_window and self.preview_window.winfo_exists():
            self.preview_window.destroy()

        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Предпросмотр Markdown")
        self.preview_window.geometry("700x600")

        preview_text = tk.Text(self.preview_window, wrap=tk.WORD, font=("Segoe UI", 11))
        preview_text.pack(fill=tk.BOTH, expand=True)

        clean_text = re.sub(r'<[^>]+>', '', html)
        preview_text.insert("1.0", clean_text)
        preview_text.config(state=tk.DISABLED)

        tk.Button(self.preview_window, text="Копировать в буфер",
                  command=lambda: self.copy_to_clipboard(clean_text)).pack(pady=5)

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_bar.config(text="Текст скопирован в буфер")

    def bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.save_note())
        self.root.bind("<Control-n>", lambda e: self.new_note())
        self.root.bind("<Delete>", lambda e: self.delete_note())
        self.root.bind("<Control-e>", lambda e: self.export_markdown())
        self.root.bind("<Control-i>", lambda e: self.import_markdown())

    def on_close(self):
        self.auto_save_running = False
        if self.unsaved_changes and self.current_file:
            if messagebox.askyesno("Несохранённые изменения", "Сохранить перед выходом?"):
                self.save_note()
        self.root.destroy()


if __name__ == "__main__":
    import json

    root = tk.Tk()
    app = ModernMarkdownNotes(root)
    root.mainloop()