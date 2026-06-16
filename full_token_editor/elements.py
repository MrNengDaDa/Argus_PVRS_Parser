"""TokenElement 数据类 + token 类型映射。无依赖，可被任意模块导入。"""

from typing import Optional


class TokenElement:
    """op_statement 直接子节点的一个元素。"""

    def __init__(self, token=None, container='', idx=0,
                 source='', _text=None, _type='', _start=0, _stop=0, _line=0):
        if token is not None:
            self.text = token.text or ''
            self.type_name = _token_type_name(token.type)
            self.line = token.line
            self.char_start = token.start
            self.char_stop = token.stop
        else:
            self.text = _text or ''
            self.type_name = _type
            self.line = _line
            self.char_start = _start
            self.char_stop = _stop
        self.container = container
        self.index = idx

    @property
    def modified(self) -> bool:
        return hasattr(self, '_new_text')

    @property
    def new_text(self) -> Optional[str]:
        return getattr(self, '_new_text', None)

    def __repr__(self):
        t = f'[{self.type_name}]'
        m = ' *' if self.modified else ''
        return (f'<<{self.index}>> {t} {self.text!r}{m}  '
                f'(line {self.line}, {self.char_start}-{self.char_stop})')


# ---- Token 类型名映射 ----

def _build_token_map():
    from PVRSLexer import PVRSLexer
    vocab = PVRSLexer.__dict__
    tmap = {}
    for k, v in vocab.items():
        if isinstance(v, int) and not k.startswith('_'):
            tmap[v] = k
    return tmap

_TOKEN_MAP = _build_token_map()

def _token_type_name(ttype: int) -> str:
    return _TOKEN_MAP.get(ttype, f'UNKNOWN({ttype})')
