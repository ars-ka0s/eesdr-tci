import asyncio
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import tkinter as tk
from tkinter import ttk

from eesdr_tci import tci
from eesdr_tci.Listener import Listener
from eesdr_tci.tci import TciCommandSendAction

from config import Config

@dataclass
class Spot:
    call: str = ''
    mode: str = ''
    freq: str = ''
    note: str = ''
    created: datetime = None
    posted: datetime = None

    def __str__(self):
        if self.note == '':
            return self.call.upper()
        return f'{self.call} [{self.note}]'.upper()

class MemoWindow:
    def _configure_root(self):
        self.root.title('Contest Memo Spots')
        self.root.resizable(False, False)
        self.root.option_add('*tearOff', False)

    def _add_spot_table(self):
        f = ttk.Frame(self.root, padding='6 6 6 6')
        f.grid(column=0, row=0, sticky='nsew')
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        cols = ('freq', 'mode', 'txt', 'age')
        self.spot_table = ttk.Treeview(f, columns=cols, show='headings', selectmode='none')
        self.spot_table.heading('freq', text='Frequency')
        self.spot_table.heading('mode', text='Mode')
        self.spot_table.heading('txt', text='Callsign / Note')
        self.spot_table.heading('age', text='Created')
        self.spot_table.grid(column=0, row=0, sticky='nsew')
        for c in cols:
            self.spot_table.column(c, anchor='center')

        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self.spot_table.yview)
        self.spot_table.configure(yscroll=sb.set)
        sb.grid(column=1, row=0, sticky='nsw')
        self.spot_table.bind('<Double-1>', self._delete_spot_via_table)

    def _add_values_disp(self):
        f = ttk.Frame(self.root, padding='6 6 6 6')
        f.grid(column=0, row=1, sticky='nsew')
        self.root.rowconfigure(1, weight=1)

        ttk.Label(f, text='Frequency').grid(column=0, row=0, sticky='nsew', padx=5)
        ttk.Label(f, text='Mode').grid(column=1, row=0, sticky='nsew', padx=5)
        ttk.Label(f, text='Callsign').grid(column=2, row=0, sticky='nsew', padx=5)
        ttk.Label(f, text='Note').grid(column=3, row=0, sticky='nsew', padx=5)

        self.freq_val = tk.StringVar()
        e = ttk.Entry(f, state='readonly', textvariable=self.freq_val, width=20)
        e.grid(column=0, row=1, sticky='nsew')

        self.mod_val = tk.StringVar()
        e = ttk.Entry(f, state='readonly', textvariable=self.mod_val, width=20)
        e.grid(column=1, row=1, sticky='nsew')

        self.call_val = tk.StringVar()
        self.call_entry = ttk.Entry(f, textvariable=self.call_val, width=20)
        self.call_entry.grid(column=2, row=1, sticky='nsew')

        self.note_val = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.note_val, width=20)
        e.grid(column=3, row=1, sticky='nsew')

        self.root.bind('<Return>', self._submit_spot)
        self.root.bind('<Escape>', self._clear_spot)

        ttk.Button(f, text='Spot', command=self._submit_spot).grid(column=4, row=1, sticky='nsew')
        ttk.Button(f, text='Clear All', command=self._clear_all).grid(column=6, row=1, sticky='nsew')

        for c in range(7):
            f.columnconfigure(c, weight=1)

    def _delete_spot_via_table(self, evt):
        call = self.spot_table.set(self.spot_table.identify_row(evt.y), 'txt')
        if call and call in self.active_spots:
            del self.active_spots[call]
            self.deleted_spots += [call]

    def _clear_spot(self, *_):
        self.call_val.set('')
        self.note_val.set('')
        self.call_entry.focus_set()

    def _submit_spot(self, *_):
        s = Spot(call=self.call_val.get(), mode=self.mod_val.get(),
                 freq=self.freq_val.get(), note=self.note_val.get(),
                 created=datetime.now())
        self.active_spots[str(s)] = s
        self._clear_spot()

    def _clear_all(self, *_):
        self.deleted_spots = []
        self.active_spots = {}
        self.request_clear = True

    def sync_spot_table(self):
        in_list = {self.spot_table.set(ch, 'txt'): ch for ch in self.spot_table.get_children('')}
        sb_list = sorted(self.active_spots.items(), key=lambda x: x[1].created)
        for call, item in in_list.items():
            if call not in self.active_spots:
                self.spot_table.delete(item)
        for call, spot in sb_list:
            if call not in in_list.keys():
                self.spot_table.insert('', tk.END, values=(spot.freq, spot.mode, str(spot), ''))
        in_list = {self.spot_table.set(ch, 'txt'): ch for ch in self.spot_table.get_children('')}
        for idx, (call, spot) in enumerate(sb_list):
            self.spot_table.move(in_list[call], '', idx)
            self.spot_table.set(in_list[call], 'age', elapsed_str(spot.created))

    def __init__(self):
        self.root = tk.Tk()
        self.last_click_call = ''
        self.last_click_time = None

        self._configure_root()
        self._add_spot_table()
        self._add_values_disp()

        self.closing = False
        self.root.protocol('WM_DELETE_WINDOW', self.dismiss)

        self.active_spots = {}
        self.deleted_spots = []
        self.request_clear = False

    def dismiss(self):
        self.closing = True
        self.root.destroy()

def elapsed(time):
    if time is None:
        return float('inf')
    return (datetime.now() - time).total_seconds()

def elapsed_str(time):
    ela = elapsed(time)
    days, rem = divmod(ela, 60*60*24)
    hrs, rem = divmod(rem, 60*60)
    mins, rem = divmod(rem, 60)
    secs = int(rem)
    days = int(days)
    hrs = int(hrs)
    mins = int(mins)

    res = ''
    if days:
        res += f'{days}d '
    if hrs or days:
        res += f'{hrs}h '
    if mins or hrs or days:
        res += f'{mins}m '
    res += f'{secs}s ago'

    return res

async def spot_clicked(win, _name, _rx, _subrx, params):
    call = params[0]
    if call != win.last_click_call:
        win.last_click_call = call
    elif elapsed(win.last_click_time) < 0.25:
        if call in win.active_spots:
            del win.active_spots[call]
        win.deleted_spots += [call]
    win.last_click_time = datetime.now()

async def new_freq(win, _name, _rx, _subrx, params):
    win.freq_val.set(str(params))

async def new_mod(win, _name, _rx, _subrx, params):
    win.mod_val.set(params)

async def main(uri, respot_time, color_val):
    tci_listener = Listener(uri)

    win = MemoWindow()

    spot_cmd = tci.COMMANDS['SPOT']
    del_cmd = tci.COMMANDS['SPOT_DELETE']
    clr_cmd = tci.COMMANDS['SPOT_CLEAR']

    tci_listener.add_param_listener('RX_CLICKED_ON_SPOT', partial(spot_clicked, win))
    tci_listener.add_param_listener('VFO', partial(new_freq, win))
    tci_listener.add_param_listener('MODULATION', partial(new_mod, win))

    await tci_listener.start()
    await tci_listener.ready()

    while not win.closing:
        await asyncio.sleep(0.050)
        win.sync_spot_table()
        win.root.update()
        to_post = [s for s in win.active_spots.values() if elapsed(s.posted) > respot_time]
        for spot in to_post:
            cmd_str = spot_cmd.prepare_string(TciCommandSendAction.WRITE, params=[str(spot), spot.mode, spot.freq, color_val, ''])
            print(cmd_str)
            await tci_listener.send(cmd_str)
            spot.posted = datetime.now()
        to_delete = list(win.deleted_spots)
        for spot in to_delete:
            cmd_str = del_cmd.prepare_string(TciCommandSendAction.WRITE, params=[spot])
            print(cmd_str)
            await tci_listener.send(cmd_str)
            win.deleted_spots.remove(spot)
        if win.request_clear:
            cmd_str = clr_cmd.prepare_string(TciCommandSendAction.WRITE)
            print(cmd_str)
            await tci_listener.send(cmd_str)
            win.request_clear = False

cfg = Config('example_config.json')
uri = cfg.get('uri', required=True)
respot_time = cfg.get("respot_time", default=60)
spot_color = cfg.get("spot_color", default="#aa2222")
color_val = int("0xFF" + spot_color.lstrip("#"), 16)

asyncio.run(main(uri, respot_time, color_val))
