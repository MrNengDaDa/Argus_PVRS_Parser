"""TokenEditorPlugin — 声明式批量修改，接口与 RuleEditorPlugin 一致。"""

from .core import TokenEditor


class TokenEditorPlugin:
    """TokenEditor 的便捷包装。"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._editor = TokenEditor(filepath)

    @property
    def editor(self) -> TokenEditor:
        return self._editor

    @property
    def pending_count(self) -> int:
        return len(self._editor.pending_tokens())

    def check(self) -> dict:
        return self._editor.check()

    def show(self, container: str) -> tuple:
        text, segs = self._editor.annotated_text(container)
        return (text, segs, self._editor.annotated_legend(container))

    def replace_by_text(self, container: str, old_text: str,
                        new_text: str) -> bool:
        return self._editor.replace_by_text(container, old_text, new_text)

    def replace_by_index(self, container: str, index: int,
                         new_text: str) -> bool:
        return self._editor.replace_by_index(container, index, new_text)

    def save(self, output_path: str = None, backup: bool = True) -> dict:
        return self._editor.save(output_path=output_path, backup=backup)

    def discard(self):
        self._editor.clear_changes()
