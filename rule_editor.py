"""
Rule editor for PVRS files.

Uses ANTLR4 parse tree + char offsets to locate and modify elements
(layerRef, constraint, expr) within RULE blocks, without altering
surrounding formatting.

Usage as library:
    from rule_editor import RuleEditor
    editor = RuleEditor("input.pvrs")
    for e in editor.elements("ant_met1"):
        print(e)

    editor.add_change(e, "new_value")
    editor.save()  # writes back, creates .bak

Extensibility: add new element types by extending ELEMENT_TYPES dict.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'grammar', 'gen'))

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener
from PVRSLexer import PVRSLexer
from PVRSParser import PVRSParser as _PVRSParser
from PVRSParserVisitor import PVRSParserVisitor


# ============================================================
# Element definition
# ============================================================

@dataclass
class Element:
    """A single modifiable element in a PVRS rule body."""
    element_type: str       # e.g. "layerRef", "constraint", "expr"
    rule_name: str          # the RULE this element belongs to
    text: str               # original text from source
    line: int               # 1-based line number
    char_start: int         # inclusive start offset into source text
    char_stop: int          # inclusive stop offset into source text
    context_type: str = ""  # ANTLR context class name (for debugging)

    @property
    def new_text(self) -> Optional[str]:
        return getattr(self, '_new_text', None)

    @property
    def modified(self) -> bool:
        return hasattr(self, '_new_text')

    def set_new_text(self, value: str):
        self._new_text = value

    def clear_change(self):
        if hasattr(self, '_new_text'):
            del self._new_text

    def __repr__(self):
        tag = " *" if self.modified else ""
        return (f"[{self.element_type}{tag}] line {self.line}: "
                f"{self.text!r} ({self.char_start}-{self.char_stop})")


# ============================================================
# Element type registry — extend here to add new collectable types
# ============================================================

class _ElementTypeSpec:
    """Descriptor for a collectable element type."""
    def __init__(self, label: str, visit_method: str,
                 filter_fn: Optional[Callable] = None,
                 desc: str = ""):
        self.label = label          # display name
        self.visit_method = visit_method  # visitor method name
        self.filter_fn = filter_fn  # optional filter(ctx) -> bool
        self.desc = desc


# Registry: key = human-readable type string
ELEMENT_TYPE_REGISTRY: Dict[str, _ElementTypeSpec] = {
    'layerRef': _ElementTypeSpec(
        'layerRef', 'visitLayerRef',
        desc='Layer reference (name, number, or quoted string)',
    ),
    'constraint': _ElementTypeSpec(
        'constraint', 'visitConstraint',
        desc='Constraint expression with comparison operator',
    ),
    'expr': _ElementTypeSpec(
        'expr', 'visitExpr',
        filter_fn=lambda ctx: not isinstance(ctx.parentCtx, _PVRSParser.ExprContext),
        desc='Top-level arithmetic expression',
    ),
}


# ============================================================
# ANTLR Visitor: collects elements inside RULE bodies
# ============================================================

class _RuleElementCollector(PVRSParserVisitor):
    """
    Walks the parse tree and collects Element objects within RULE blocks.

    Only elements covered by ELEMENT_TYPE_REGISTRY are collected.
    Expr dedup: only top-level exprs (parent is not expr) are collected.
    """

    def __init__(self, source_text: str):
        self.source = source_text
        self.elements: List[Element] = []
        self._current_rule_name: Optional[str] = None

    # -- helpers --

    def _rule_from_ctx(self, ctx) -> Optional[str]:
        """Extract the current rule name by walking up to rule_statement."""
        node = ctx
        while node is not None:
            if isinstance(node, _PVRSParser.Rule_statementContext):
                rn = node.ruleName()
                if rn is not None:
                    return rn.getText()
                return None
            node = node.parentCtx
        return None

    def _add_element(self, etype: str, ctx):
        if ctx.start is None or ctx.stop is None:
            return
        rule_name = self._rule_from_ctx(ctx)
        if not rule_name:
            return  # outside any RULE block, skip
        text = self.source[ctx.start.start:ctx.stop.stop + 1]
        elem = Element(
            element_type=etype,
            rule_name=rule_name,
            text=text,
            line=ctx.start.line,
            char_start=ctx.start.start,
            char_stop=ctx.stop.stop,
            context_type=type(ctx).__name__,
        )
        self.elements.append(elem)

    # -- visitor overrides —

    def visitRule_statement(self, ctx):
        self.visitChildren(ctx)
        return None

    def visitLayerRef(self, ctx):
        self._add_element('layerRef', ctx)
        # Don't visit children — layerRef is a leaf (ID|INT_LIT|STRING|EDGE)
        return None

    def visitConstraint(self, ctx):
        self._add_element('constraint', ctx)
        return self.visitChildren(ctx)

    def visitExpr(self, ctx):
        spec = ELEMENT_TYPE_REGISTRY['expr']
        if spec.filter_fn is None or spec.filter_fn(ctx):
            self._add_element('expr', ctx)
        return self.visitChildren(ctx)

    # Generic fallback: recurse into children for any unhandled node
    def visitChildren(self, ctx):
        result = super().visitChildren(ctx)
        return result


# ============================================================
# Parse error collector
# ============================================================

class _ParseErrorCollector(ErrorListener):
    def __init__(self):
        super().__init__()
        self.errors: list = []  # (line, col, msg)

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append((line, column, msg))


# ============================================================
# RuleEditor — main public API
# ============================================================

class RuleEditor:
    """
    Parse a PVRS file and provide access to modifiable elements within
    RULE blocks. Supports in-place text replacement with backup creation.
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        with open(filepath, 'r', encoding='utf-8', errors='replace', newline='') as f:
            raw = f.read()
        # Detect original line ending style, preserve raw for backup
        self._raw = raw
        self._crlf = '\r\n' in raw
        # Normalize CRLF -> LF so char offsets are consistent
        self.source = raw.replace('\r\n', '\n')

        # Parse: use InputStream with normalized text so offsets match self.source
        input_stream = InputStream(self.source)
        lexer = PVRSLexer(input_stream)
        stream = CommonTokenStream(lexer)
        parser = _PVRSParser(stream)
        parser.removeErrorListeners()
        error_listener = _ParseErrorCollector()
        parser.addErrorListener(error_listener)
        self._tree = parser.pvrFile()
        self._parse_errors = error_listener.errors  # list of (line, col, msg)

        # Collect elements
        collector = _RuleElementCollector(self.source)
        collector.visit(self._tree)
        self._elements: List[Element] = collector.elements

        # Pending changes: list of (element, new_text)
        self._changes: List[Element] = []

    # ---- query ----

    @property
    def parse_errors(self) -> list:
        """List of (line, col, msg) tuples for syntax errors found."""
        return list(self._parse_errors)

    @property
    def has_errors(self) -> bool:
        """True if the file has syntax errors. Elements may be unreliable."""
        return len(self._parse_errors) > 0

    @property
    def elements(self) -> List[Element]:
        """All collected elements."""
        return list(self._elements)

    def elements_by_rule(self, rule_name: str) -> List[Element]:
        """Elements within a specific rule (exact name match)."""
        name = rule_name.strip('"')
        return [e for e in self._elements
                if e.rule_name.strip('"') == name]

    def elements_by_type(self, element_type: str) -> List[Element]:
        """Elements of a specific type."""
        return [e for e in self._elements if e.element_type == element_type]

    def rule_names(self) -> List[str]:
        """Sorted list of unique rule names found."""
        seen = set()
        result = []
        for e in self._elements:
            if e.rule_name not in seen:
                seen.add(e.rule_name)
                result.append(e.rule_name)
        return result

    def rule_summaries(self) -> List[Dict[str, Any]]:
        """Return [{name, line, element_count}, ...] for each rule."""
        names = self.rule_names()
        result = []
        for name in names:
            elems = self.elements_by_rule(name)
            result.append({
                'name': name,
                'line': elems[0].line if elems else 0,
                'count': len(elems),
                'types': sorted(set(e.element_type for e in elems)),
            })
        return result

    def type_counts(self, rule_name: str) -> Dict[str, int]:
        """Count of each element type within a rule."""
        counts: Dict[str, int] = {}
        for e in self.elements_by_rule(rule_name):
            counts[e.element_type] = counts.get(e.element_type, 0) + 1
        return counts

    # ---- modify ----

    def add_change(self, element: Element, new_text: str):
        """Queue a change. The element must belong to this editor."""
        if element not in self._elements:
            raise ValueError("Element does not belong to this editor")
        if new_text == element.text:
            element.clear_change()
        else:
            element.set_new_text(new_text)
        # Keep track in changes list
        self._changes = [e for e in self._elements if e.modified]

    def pending_changes(self) -> List[Element]:
        """Return elements with pending changes."""
        return list(self._changes)

    def modified_text(self) -> str:
        """Return the source text with all pending changes applied."""
        if not self._changes:
            return self.source

        text = self.source
        # Apply from right-to-left to preserve char offsets
        for elem in sorted(self._changes, key=lambda e: -e.char_start):
            text = (text[:elem.char_start] + elem.new_text +
                    text[elem.char_stop + 1:])
        return text

    def clear_changes(self):
        """Discard all pending changes."""
        for e in self._elements:
            e.clear_change()
        self._changes = []

    # ---- save ----

    def save(self, output_path: Optional[str] = None, backup: bool = True):
        """
        Write the modified text to disk.

        If output_path is None, overwrites self.filepath.
        If backup is True, creates a .bak file of the original.
        """
        if backup and output_path is None:
            bak_path = self.filepath + '.bak'
            with open(bak_path, 'w', encoding='utf-8', newline='') as f:
                f.write(self._raw)

        text = self.modified_text()
        if self._crlf:
            text = text.replace('\n', '\r\n')

        target = output_path or self.filepath
        with open(target, 'w', encoding='utf-8', newline='') as f:
            f.write(text)


# ============================================================
# Convenience functions (used by CLI)
# ============================================================

def get_element_types() -> List[Dict[str, str]]:
    """Return registered element types for display."""
    return [
        {'key': k, 'label': v.label, 'desc': v.desc}
        for k, v in ELEMENT_TYPE_REGISTRY.items()
    ]


def iter_elements_by_rule(elements: List[Element],
                           rule_name: str) -> Dict[str, List[Element]]:
    """Group elements by type for a given rule. Returns {type: [Element]}."""
    groups: Dict[str, List[Element]] = {}
    name = rule_name.strip('"')
    for e in elements:
        if e.rule_name.strip('"') == name:
            groups.setdefault(e.element_type, []).append(e)
    return groups
