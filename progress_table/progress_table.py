#  Copyright (c) 2022 Szymon Mikler

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import List

from colorama import Fore, Style

all_colors = [getattr(Fore, x) for x in dir(Fore) if not x.startswith("__")]
all_styles = [getattr(Style, x) for x in dir(Style) if not x.startswith("__")]
all_colors_styles = all_colors + all_styles


@dataclass
class Symbols:
    full: str = "■"
    empty: str = "□"
    dots: str = "…"

    horizontal: str = "─"
    vertical: str = "│"
    all: str = "┼"

    up_left: str = "┘"
    up_right: str = "└"
    down_left: str = "┐"
    down_right: str = "┌"

    no_left: str = "├"
    no_right: str = "┤"
    no_up: str = "┬"
    no_down: str = "┴"


class ProgressTable:
    def __init__(
        self,
        columns=(),
        default_column_width=8,
        progress_bar_fps=10,
        custom_format=None,
        print_row_on_setitem=True,
        reprint_header_every_n_rows=30,
        default_format_decimal_places=4,
    ):
        self.default_width = default_column_width

        self.columns = []
        self.num_rows = 0

        self.widths = {}
        self.values = defaultdict(str)
        self.colors = defaultdict(lambda: None)

        self.aggregate = {}
        self.aggregate_n = defaultdict(int)

        self.progress_bar_fps = progress_bar_fps
        self.header_printed = False
        self.last_header_printed_at_row_count = 0
        self.reprint_header_every_n_rows = reprint_header_every_n_rows
        self.print_row_on_setitem = print_row_on_setitem

        self.custom_format = custom_format or self.default_format_func
        self.default_format_decimal_places = default_format_decimal_places
        self.needs_line_ending = False
        self.finished_rows = []

        for column in columns:
            self.add_column(column)

    def default_format_func(self, x):
        if isinstance(x, int):
            return x
        else:
            try:
                return format(x, f".{self.default_format_decimal_places}f")
            except Exception:
                return x

    def add_column(self, name, width=None, color=None, aggregate=None):
        assert not self.header_printed, "Columns cannot be modified after printing the first row!"
        self.columns.append(name)

        width = width if width is not None else self.default_width
        if width < len(name):
            width = len(name)

        if color is not None:
            self._check_color(color)
            self.colors[name] = color

        assert aggregate in [None, "mean", "sum"], "Allowed aggregate types: [None, mean, sum]"
        self.aggregate[name] = aggregate
        self.widths[name] = width

    def next_row(self, save=True):
        self._print_row()
        self._maybe_line_ending()

        if save and len(self.values) > 0:
            self.finished_rows.append(self.values)
            self.num_rows += 1

        self.values = defaultdict(str)
        self.aggregate_n = defaultdict(int)

    def close(self):
        self._print_row()
        self.next_row()
        self._print_bottom_bar()
        self.header_printed = False
        print()

    def to_list(self):
        return [[row[col] for col in self.columns] for row in self.finished_rows]

    def to_numpy(self):
        import numpy as np

        return np.array(self.to_list())

    def to_df(self):
        import pandas as pd

        return pd.DataFrame(self.to_list(), columns=self.columns)

    def display(self):
        if self.header_printed:
            self.close()
        self._display_custom(self.to_list())

    def _bar(self, left: str, center: str, right: str):
        content_list: List[str] = []
        for col in self.columns:
            content_list.append(Symbols.horizontal * (self.widths[col] + 2))

        center = center.join(content_list)
        content = [left, center, right]
        print("".join(content), end="")

    def _print_top_bar(self):
        return self._bar(left=Symbols.down_right, center=Symbols.no_up, right=Symbols.down_left)

    def _print_bottom_bar(self):
        return self._bar(left=Symbols.up_right, center=Symbols.no_down, right=Symbols.up_left)

    def _print_center_bar(self):
        return self._bar(left=Symbols.no_left, center=Symbols.all, right=Symbols.no_right)

    def _check_color(self, color):
        assert color in all_colors_styles, "Only colorama colors are allowed, e.g. colorama.Fore.GREEN!"

    def _print_header(self, top=True):
        assert self.columns, "Columns are required! Use .add_column method or specify them in __init__!"

        if top:
            self._print_top_bar()
        else:
            self._print_center_bar()
        print()

        content = []
        for col in self.columns:
            width = self.widths[col]
            value = col[:width].center(width)

            if self.colors[col] is not None:
                self._check_color(self.colors[col])
                value = f"{self.colors[col]}{value}{Style.RESET_ALL}"

            content.append(value)
        print(Symbols.vertical, f" {Symbols.vertical} ".join(content), Symbols.vertical)

        self.last_header_printed_at_row_count = self.num_rows
        self.header_printed = True
        self._print_center_bar()
        print()

    def _print_row(self):
        if not self.header_printed:
            self._print_header(top=True)
        if self.num_rows - self.last_header_printed_at_row_count >= self.reprint_header_every_n_rows:
            self._print_header(top=False)

        if len(self.values) == 0:
            return
        self.needs_line_ending = True
        print(end="\r")

        content = []
        for col in self.columns:
            value = self.values[col]
            width = self.widths[col]

            if self.custom_format:
                value = self.custom_format(value)

            clipped = len(str(value)) > width
            end_symbol = Symbols.dots if clipped else " "
            value = str(value)[:width].center(width)
            value += end_symbol

            if self.colors[col] is not None:
                self._check_color(self.colors[col])
                value = f"{self.colors[col]}{value}{Style.RESET_ALL}"

            content.append(value)
        print(Symbols.vertical, " ", f"{Symbols.vertical} ".join(content), Symbols.vertical, end="", sep="")

    def _print_progress_bar(self, i, n, show_before=" ", show_after=" "):
        i = min(i, n)  # clip i to be not bigger than n
        tot_width = sum(self.widths.values()) + 3 * (len(self.widths) - 1) + 2
        tot_width = tot_width - len(show_before) - len(show_after)

        num_hashes = math.ceil(i / n * tot_width)
        num_empty = tot_width - num_hashes

        print(
            Symbols.vertical,
            show_before,
            Symbols.full * num_hashes,
            Symbols.empty * num_empty,
            show_after,
            Symbols.vertical,
            end="\r",
            sep="",
        )

    def _maybe_line_ending(self):
        if self.needs_line_ending:
            print()
            self.needs_line_ending = False

    def _display_custom(self, data):
        if self.header_printed:
            self.close()

        for row in data:
            assert len(row) == len(self.columns)
            for key, value in zip(self.columns, row):
                self.values[key] = value
            self._print_row()
            self.next_row(save=False)
        self.close()

    def __call__(self, iterator, length=None, prefix="", show_throughput=True):
        if not self.header_printed:
            self._print_header()

        assert length is not None or hasattr(iterator, "__len__"), "Provide length of the iterator!"
        length = length or len(iterator)

        t_last_printed = -float("inf")
        t_beginning = time.time()

        for idx, element in enumerate(iterator):
            if time.time() - t_last_printed > 1 / self.progress_bar_fps:
                print(end="\r")
                s = time.time() - t_beginning
                throughput = idx / s if s > 0 else 0.0

                full_prefix = [" [", prefix]
                if show_throughput:
                    full_prefix.append(f"{throughput: <.2f} it/s")
                full_prefix.append("] ")
                full_prefix = "".join(full_prefix)
                full_prefix = full_prefix if full_prefix != " [] " else " "
                self._print_progress_bar(idx, length, show_before=full_prefix)

                t_last_printed = time.time()

            yield element
        self._print_row()

    def __setitem__(self, key, value):
        assert key in self.columns, f"Column {key} not in {self.columns}"

        if self.aggregate[key] == "sum":
            aggr_value = self.values[key] if self.aggregate_n[key] > 0 else 0
            self.values[key] = aggr_value + value
            self.aggregate_n[key] += 1

        elif self.aggregate[key] == "mean":
            n = self.aggregate_n[key]
            aggr_value = self.values[key] if n > 0 else 0
            self.values[key] = (aggr_value * n + value) / (n + 1)
            self.aggregate_n[key] += 1

        else:
            self.values[key] = value

        if self.print_row_on_setitem:
            self._print_row()
