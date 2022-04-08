import os
from typing import List


class CodeChunk:
    class Block:
        def __init__(self, codegen: "CodeChunk"):
            self.gen = codegen

        def __enter__(self):
            self.gen.indent()
            return self.gen

        def __exit__(self, *_, **__):  # type: ignore
            self.gen.unindent()

    def __init__(self):
        self.lines: List[str] = []
        self.level = 0

    def indent(self):
        self.level += 1

    def unindent(self):
        if self.level > 0:
            self.level -= 1

    @property
    def indent_string(self):
        return self.level * "    "

    def write(self, value: str):
        if value != "":
            value = self.indent_string + value
        self.lines.append(value)

    def write_lines(self, lines: List[str]):
        for line in lines:
            self.lines.append(self.indent_string + line)

    def block(self):
        return self.Block(self)

    def write_block(self, block_header: str):
        self.write(block_header)
        return self.block()

    def tell(self):
        return len(self.lines)

    def insert(self, pos: int, lines: List[str]):
        self.lines = self.lines[:pos] + lines + self.lines[pos:]

    def __str__(self):
        return os.linesep.join(self.lines)
