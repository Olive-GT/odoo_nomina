#!/usr/bin/env python3
"""Verificador estático: cada método/campo l10n_gt_* referenciado en las
plantillas de reporte debe existir en el código Python de los módulos.
Atrapa bugs tipo AttributeError en render (como la regla ANTIC)."""
import os, re, glob, sys

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1) Recolectar TODO lo definido en Python: métodos y campos.
defined_methods = set()
defined_fields = set()
for py in glob.glob(f"{ROOT}/l10n_gt_*/**/*.py", recursive=True):
    if "__pycache__" in py:
        continue
    src = open(py, encoding="utf-8").read()
    for m in re.finditer(r"def\s+(_l10n_gt_\w+)\s*\(", src):
        defined_methods.add(m.group(1))
    # también helpers definidos sin prefijo pero usados en reportes
    for m in re.finditer(r"def\s+(_l10n_gt_line\w*|_l10n_gt_worked_days|_l10n_gt_lines_by_category|_l10n_gt_money|_l10n_gt_period_label|_l10n_gt_amount_words)\s*\(", src):
        defined_methods.add(m.group(1))
    for m in re.finditer(r"(l10n_gt_\w+)\s*=\s*fields\.", src):
        defined_fields.add(m.group(1))

# 2) Recolectar plantillas QWeb definidas (para validar t-call).
defined_templates = set()
for xml in glob.glob(f"{ROOT}/l10n_gt_*/**/*.xml", recursive=True):
    txt = open(xml, encoding="utf-8").read()
    mod = xml.replace(ROOT + "/", "").split("/")[0]
    for m in re.finditer(r'<template\s+id="([^"]+)"', txt):
        tid = m.group(1)
        defined_templates.add(tid)
        defined_templates.add(f"{mod}.{tid}")

# 3) Recolectar referencias en las plantillas de reporte (report/*.xml).
report_xmls = []
for xml in glob.glob(f"{ROOT}/l10n_gt_*/report/*.xml"):
    txt = open(xml, encoding="utf-8").read()
    if "<template" in txt:
        report_xmls.append(xml)

# Plantillas de Odoo core usadas con t-call (no están en nuestro repo).
CORE_TEMPLATES = {"web.html_container", "web.external_layout",
                  "web.basic_layout", "web.internal_layout"}

problems = []
used_methods = set()
used_fields = set()
for xml in sorted(report_xmls):
    raw = open(xml, encoding="utf-8").read()
    rel = xml.replace(ROOT + "/", "")
    # validar t-call contra plantillas definidas
    for m in re.finditer(r't-call="([^"]+)"', raw):
        tid = m.group(1)
        if tid not in defined_templates and tid not in CORE_TEMPLATES:
            line = raw[:m.start()].count("\n") + 1
            problems.append((rel, line, "T-CALL", tid))
    # t-set con nombre de builtin de Python (QWeb resuelve el builtin, no la
    # variable -> TypeError en render, p.ej. 'ord').
    PY_BUILTINS = {"ord", "sum", "min", "max", "abs", "round", "id", "type",
                   "dict", "list", "str", "int", "len", "map", "filter",
                   "format", "vars", "all", "any", "sorted", "zip", "range",
                   "next", "iter", "bytes", "bool", "set", "hash", "open", "dir"}
    for m in re.finditer(r't-set="([^"]+)"', raw):
        if m.group(1) in PY_BUILTINS:
            line = raw[:m.start()].count("\n") + 1
            problems.append((rel, line, "BUILTIN", m.group(1)))
    # quitar los valores de t-call para que no contaminen el escaneo de campos
    txt = re.sub(r't-call="[^"]+"', 't-call=""', raw)
    # llamadas a métodos: .algo(   con prefijo _l10n_gt_
    for m in re.finditer(r"\.\s*(_l10n_gt_\w+)\s*\(", txt):
        name = m.group(1)
        used_methods.add(name)
        if name not in defined_methods:
            line = txt[:m.start()].count("\n") + 1
            problems.append((rel, line, "MÉTODO", name))
    # accesos a campos: .l10n_gt_xxx  no seguido de (
    for m in re.finditer(r"\.\s*(l10n_gt_\w+)\b(?!\s*\()", txt):
        name = m.group(1)
        used_fields.add(name)
        if name not in defined_fields:
            line = txt[:m.start()].count("\n") + 1
            problems.append((rel, line, "CAMPO", name))

print("=" * 70)
print("VERIFICADOR ESTÁTICO DE REPORTES")
print("=" * 70)
print(f"Plantillas de reporte analizadas : {len(report_xmls)}")
print(f"Métodos _l10n_gt_* definidos      : {len(defined_methods)}")
print(f"Campos  l10n_gt_*  definidos      : {len(defined_fields)}")
print(f"Métodos referenciados en reportes : {len(used_methods)}")
print(f"Campos  referenciados en reportes : {len(used_fields)}")
print("-" * 70)
if not problems:
    print("✅ SIN PROBLEMAS: todas las referencias l10n_gt existen en el código.")
else:
    print(f"❌ {len(problems)} REFERENCIA(S) NO DEFINIDA(S):")
    for rel, line, kind, name in problems:
        print(f"  {rel}:{line}  [{kind}] {name}")
    sys.exit(1)
