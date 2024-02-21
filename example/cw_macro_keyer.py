import asyncio
from dataclasses import dataclass
from functools import partial
import json
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import sys

from eesdr_tci import tci
from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciCommandSendAction

from config import Config

@dataclass
class Macro:
    title = ''
    macro = ''

class Macros:
    VALID_KEYS = [f'F{n}' for n in range(1, 13)]
    FILE_TYPES = [('CW Macro Files', '*.cwm')]

    def __init__(self):
        self.macros = {k: Macro() for k in Macros.VALID_KEYS}
        self.button_strs = {k: tk.StringVar() for k in Macros.VALID_KEYS}
        self.loaded_from = None
        self.update_all_text()

    def __getitem__(self, k):
        return self.macros[k]

    def str_var(self, k):
        return self.button_strs[k]

    def update_text(self, k):
        macro = self.macros[k]
        self.button_strs[k].set(f'{k}\n{macro.title}\n<{macro.macro}>')

    def update_all_text(self):
        for k in Macros.VALID_KEYS:
            self.update_text(k)

    def clear(self):
        self.macros = {k: Macro() for k in Macros.VALID_KEYS}
        self.loaded_from = None
        self.update_all_text()

    def load(self, filename):
        if not filename:
            return 0

        with open(filename, 'r', encoding='utf-8') as f:
            load_macros = json.load(f)

        self.macros = {k: Macro() for k in Macros.VALID_KEYS}
        loaded_count = 0
        for k in Macros.VALID_KEYS:
            if k in load_macros:
                loaded_data = False
                loaded = load_macros[k]
                macro = self.macros[k]
                if 'title' in loaded:
                    macro.title = loaded['title']
                    loaded_data = True
                if 'macro' in loaded:
                    macro.macro = loaded['macro']
                    loaded_data = True
                if loaded_data:
                    loaded_count += 1

        self.update_all_text()
        if loaded_count > 0:
            self.loaded_from = filename

        return loaded_count

    def save(self, filename=None):
        if not filename:
            filename = self.loaded_from

        if not filename:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.macros, f, default=vars)

        self.loaded_from = filename

class EditPopup:
    def __init__(self, parent, button, macro):
        self.success = False
        self.title_var = tk.StringVar(value=macro.title)
        self.macro_var = tk.StringVar(value=macro.macro)
        self.edit_macro = macro
        min_width = max(len(macro.title), len(macro.macro)) + 5

        self.win = tk.Toplevel(parent)

        self.win.title(f'{button} Macro Details')
        self.win.resizable(True, False)

        f = ttk.Frame(self.win, padding='6 6 6 6')
        f.grid(column=1, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.win.columnconfigure(1, weight=1)
        self.win.rowconfigure(1, weight=3)

        ttk.Label(f, text='Button').grid(column=1, row=1, sticky=tk.E)
        ttk.Label(f, text=f'{button}').grid(column=2, row=1, sticky=(tk.E, tk.W))

        ttk.Label(f, text='Title').grid(column=1, row=2, sticky=tk.E)
        ttk.Entry(f, textvariable=self.title_var, width=min_width).grid(
            column=2, row=2, sticky=(tk.E, tk.W))

        ttk.Label(f, text='Macro').grid(column=1, row=3, sticky=tk.E)
        macro_entry = ttk.Entry(f, textvariable=self.macro_var, width=min_width)
        macro_entry.grid(column=2, row=3, sticky=(tk.E, tk.W))

        f.columnconfigure(2, weight=1)
        f.rowconfigure(1, weight=1)
        f.rowconfigure(2, weight=1)
        f.rowconfigure(3, weight=1)
        for child in f.winfo_children():
            child.grid_configure(padx=5, pady=5)

        f = ttk.Frame(self.win, padding='6 6 6 6')
        f.grid(column=1, row=2, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.win.rowconfigure(2, weight=1)

        ttk.Button(f, text='Cancel', command=self.dismiss).grid(
            column=1, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        ttk.Button(f, text='Save', command=self.save).grid(
            column=2, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))

        f.rowconfigure(1, weight=1)
        f.columnconfigure(1, weight=1)
        f.columnconfigure(2, weight=1)
        for child in f.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.win.protocol('WM_DELETE_WINDOW', self.dismiss)
        self.win.bind('<Escape>', self.dismiss)
        self.win.bind('<Return>', self.save)
        self.win.transient(parent)
        self.win.wait_visibility()
        self.win.focus()
        macro_entry.focus()
        self.win.grab_set()
        self.win.wait_window()

    def dismiss(self, *_):
        self.win.grab_release()
        self.win.destroy()

    def save(self, *_):
        self.success = True
        self.edit_macro.title = self.title_var.get()
        self.edit_macro.macro = self.macro_var.get()
        self.dismiss()

class MacrosWindow:
    def _configure_root(self):
        self.root.title('CW Macros')
        self.root.resizable(False, False)
        self.root.option_add('*tearOff', False)

    def _configure_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root['menu'] = menu_bar
        self.file_menu = tk.Menu(menu_bar)
        menu_bar.add_cascade(menu=self.file_menu, label='File', underline=0)

        self.file_menu.add_command(label='New', underline=0,
            accelerator='Ctrl+N', command=self.new_macros)
        self.root.bind('<Control-n>', self.new_macros)

        self.file_menu.add_command(label='Open...', underline=0,
            accelerator='Ctrl+O', command=self.open_macros)
        self.root.bind('<Control-o>', self.open_macros)

        self.file_menu.add_command(label='Save', underline=0,
            accelerator='Ctrl+S', state=tk.DISABLED, command=self.save_macros)
        self.root.bind('<Control-s>', self.save_macros)

        self.file_menu.add_command(label='Save As...', underline=5,
            accelerator='Ctrl+Alt+S', command=self.save_macros_as)
        self.root.bind('<Control-Alt-s>', self.save_macros_as)

        self.file_menu.add_command(label='Exit', underline=1,
            accelerator='Alt+F4', command=self.dismiss)

    def _add_macro_buttons(self):
        f = ttk.Frame(self.root, padding='6 6 6 6')
        f.grid(column=0, row=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Style().configure('TButton', justify=tk.CENTER)

        row = 0
        for i, button_name in enumerate(Macros.VALID_KEYS):
            button_str = self.macros.str_var(button_name)
            b = ttk.Button(f, textvariable=button_str)
            row = i // 4
            b.grid(column=i % 4, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))

            cmd = partial(self.show_edit, button_name)
            b.bind('<Button-2>', cmd)
            b.bind('<Button-3>', cmd)

            cmd = partial(self.send_from_button, button_name)
            b.bind('<Button-1>', cmd)
            self.root.bind(f'<{button_name}>', cmd)

        return f, row + 1

    def _add_freeform_and_slider(self, f, row):
        self.freeform_var = tk.StringVar()
        self.freeform_entry = ttk.Entry(f, textvariable=self.freeform_var)
        self.freeform_entry.grid(column=0, columnspan=3, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))
        ttk.Button(f, text='>>', command=self.send_freeform).grid(
            column=3, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))

        def _clear_ffv(_):
            self.freeform_var.set('')
        self.root.bind('<Escape>', _clear_ffv)
        self.freeform_entry.bind('<Return>', self.send_freeform)

        row += 1
        self.wpm_var = tk.IntVar()
        self.wpm_callback = lambda: None
        def _wpm_callback(*_):
            self.wpm_callback()
        self.wpm_var.trace_add('write', _wpm_callback)
        ttk.Label(f, text='Macro WPM').grid(column=0, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))
        def _make_scale_int(val):
            int_val = int(float(val))
            self.wpm_var.set(int_val)
        ttk.Scale(f, from_=5, to=50, variable=self.wpm_var, command=_make_scale_int).grid(
            column=1, columnspan=2, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))
        ttk.Label(f, textvariable=self.wpm_var).grid(
            column=3, row=row, sticky=(tk.N, tk.S, tk.E, tk.W))
        def _increment_and_constrain(amt, _, min_val=5, max_val=50):
            curr_val = self.wpm_var.get() + amt
            curr_val = min(max_val, max(min_val, curr_val))
            self.wpm_var.set(curr_val)
        self.root.bind('+', partial(_increment_and_constrain, 1))
        self.root.bind('-', partial(_increment_and_constrain, -1))
        self.root.bind('<Prior>', partial(_increment_and_constrain, 5))
        self.root.bind('<Next>', partial(_increment_and_constrain, -5))
        def _reset_wpm(_):
            self.wpm_var.set(25)
        self.root.bind('=', _reset_wpm)

    def __init__(self, macro_queue):
        self.root = tk.Tk()
        self.macros = Macros()
        self.queue = macro_queue

        self._configure_root()
        self._configure_menu()
        f, next_row = self._add_macro_buttons()
        self._add_freeform_and_slider(f, next_row)

        for child in f.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.protocol('WM_DELETE_WINDOW', self.dismiss)

    def show_edit(self, button_name, *_):
        macro = self.macros[button_name]
        popup = EditPopup(self.root, button_name, macro)
        if popup.success:
            self.macros.update_text(button_name)

    def send_from_button(self, button_name, *_):
        macro = self.macros[button_name].macro
        if macro != '':
            self.queue.put_nowait(('M', macro))

    def send_freeform(self, *_):
        macro = self.freeform_var.get()
        if macro != '':
            self.queue.put_nowait(('M', macro))
            self.freeform_var.set('')
            self.freeform_entry.focus()

    def new_macros(self, *_):
        self.macros.clear()
        self.file_menu.entryconfigure('Save', state=tk.DISABLED)

    def open_macros(self, *_):
        filename = filedialog.askopenfilename(parent=self.root, filetypes=Macros.FILE_TYPES)
        if not filename:
            return
        self.open_macros_from_filename(filename)

    def open_macros_from_filename(self, filename):
        try:
            load_count = self.macros.load(filename)
        except json.JSONDecodeError:
            messagebox.showerror(title='Load Error', message='CW Macros file failed to decode.')
            return
        except OSError:
            messagebox.showerror(title='Load Error', message='CW Macros file failed to open.')
            return

        if load_count == 0:
            messagebox.showerror(title='Load Error', message='File parsed but no info loaded.')
        else:
            self.file_menu.entryconfigure('Save', state=tk.NORMAL)

    def save_macros(self, *_):
        try:
            self.macros.save()
        except OSError:
            messagebox.showerror(title='Save Error', message='Error writing to CW Macros file.')

    def save_macros_as(self, *_):
        filename = filedialog.asksaveasfilename(
            parent=self.root, filetypes=Macros.FILE_TYPES, defaultextension='.cwm')
        if not filename:
            return

        try:
            self.macros.save(filename)
        except OSError:
            messagebox.showerror(title='Save Error', message='Error writing to CW Macros file.')
            return

        self.file_menu.entryconfigure('Save', state=tk.NORMAL)

    def dismiss(self):
        self.queue.put_nowait(('', ''))
        self.root.destroy()

last_wpm_val = None

async def update_wpm_disp(win, name, rx, subrx, params):
    global last_wpm_val

    if name != 'CW_MACROS_SPEED' or rx is not None or subrx is not None:
        return
    last_wpm_val = int(params)
    win.wpm_var.set(params)
    print("Got new WPM", last_wpm_val)

def wpm_callback(win, queue, *_):
    global last_wpm_val

    new_wpm = int(win.wpm_var.get())
    if new_wpm != last_wpm_val:
        queue.put_nowait(('W', str(new_wpm)))
        last_wpm_val = new_wpm

async def main(uri, autoload_file):
    tci_listener = Listener(uri)

    macro_queue = asyncio.Queue()
    win = MacrosWindow(macro_queue)
    if autoload_file:
        win.open_macros_from_filename(autoload_file)

    macro_cmd = tci.COMMANDS['CW_MACROS']
    wpm_cmd = tci.COMMANDS['CW_MACROS_SPEED']

    tci_listener.add_param_listener('CW_MACROS_SPEED', partial(update_wpm_disp, win))
    win.wpm_callback = partial(wpm_callback, win, macro_queue)
    await tci_listener.start()
    await tci_listener.ready()

    while True:
        if macro_queue.qsize() == 0:
            await asyncio.sleep(0.050)
            win.root.update()
        else:
            item = await macro_queue.get()
            if item[0] == '':
                break
            elif item[0] == 'M':
                print('Sending Macro', item[1])
                str = macro_cmd.prepare_string(TciCommandSendAction.WRITE, rx=0, params=[item[1]])
                print(str)
                await tci_listener.send(str)
            elif item[0] == 'W':
                print('Sending WPM', item[1])
                str = wpm_cmd.prepare_string(TciCommandSendAction.WRITE, params=[item[1]])
                print(str)
                await tci_listener.send(str)

cfg = Config('example_config.json')
uri = cfg.get('uri', required=True)

if len(sys.argv) == 1:
    autoload_file = cfg.get('cw_macros_default')
else:
    autoload_file = sys.argv[1]

asyncio.run(main(uri, autoload_file))
