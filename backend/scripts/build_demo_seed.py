"""Buduje backend/app/seed/umb_demo.json z materiałów wyzwania UMB.

Użycie (z katalogu repozytorium, wymaga Tesseract z językiem pol dla skanów):
    python backend/scripts/build_demo_seed.py "C:/Hacknation 2026 - UMB"

Folder źródłowy jest tylko czytany. Wynik: 10 spraw z rejestru (Excel) wzbogaconych o treść wniosków,
odpowiedzi i pism z toku sprawy + Zarządzenie nr 535/2024 podzielone na paragrafy.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import seed_data  # noqa: E402
from services import deadlines, excel_import, extraction, legal_text  # noqa: E402

OUT = APP / "seed" / "umb_demo.json"

LETTERHEAD = re.compile(
    r"^(URZĄD MIASTA BYDGOSZCZY|Biuro Komunikacji Społecznej|Biuro Komunikacji Urząd Miasta|Bydgoszczy Społecznej|"
    r"Urząd Miasta Bydgoszczy|85\s*-\s*102 Bydgoszcz, ul\. Jezuicka 1|tel\.:? \(52\).*|e-?mail:\s*(bks|bip)@.*|email: bks.*)\s*$",
    re.IGNORECASE,
)
DATE_LINE = re.compile(r"^Bydgoszcz,\s*(?:dnia\s*)?(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", re.IGNORECASE)
CASE_LINE = re.compile(r"^BKS\.\s*IV\.1431\.\s*\d+\s*\.\s*\d{4}\s*$")

# Poprawki błędów OCR w warstwie tekstowej Zarządzenia — zweryfikowane z obrazem 1. strony dokumentu.
ORDINANCE_FIXES = [
    ("ZARZĄDZENIE NR 536, 2024", "ZARZĄDZENIE NR 535/2024"),
    ("z dnia AŻ jytwe)/MDU_ 2024 r.", "z dnia 23 września 2024 r."),
    ("bipQQum.bydgoszcz.pl", "bip@um.bydgoszcz.pl"),
    ("www,bip.um.bydgoszcz.pl", "www.bip.um.bydgoszcz.pl"),
    ("udip, udesi i", "udip, udcsi i"),
    ("\n89.1. AIP", "\n§ 9. 1. AIP"),
    ("wniosek. dotyczy", "wniosek dotyczy"),
]
ORDINANCE_TITLE = "Zarządzenie nr 535/2024 Prezydenta Miasta Bydgoszczy"
ORDINANCE_SOURCE = "Zarządzenie nr 535/2024 z dnia 23 września 2024 r. w sprawie zasad i trybu udostępniania informacji publicznej"


def reflow(lines: list[str]) -> str:
    """Skleja wiersze akapitu (PDF łamie je w środku zdań), zachowuje „Ad 1”, listy i zwroty."""
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        prev = out[-1] if out else ""
        joinable = prev and prev != "" and not re.match(
            r"^(Ad\s*\d|\d+[.)]|Załącznik|Łączę|Z wyrazami|Szanown|[Ww] odpowiedzi|[Ww] związku|[Ww] nawiązaniu|[Oo]dpowiadając)", line
        )
        if joinable and prev.endswith("-") and line[:1].islower():
            out[-1] = prev[:-1] + line
        elif joinable and (line[:1].islower() or not re.search(r"[.:;,?!)”]$", prev)) and not re.match(r"^(Ad\s*\d|Szanown)", prev):
            out[-1] = prev + " " + line
        else:
            out.append(line)
    return "\n".join(out).strip()


def letter_body(text: str) -> tuple[str, str | None]:
    """Treść pisma bez nagłówka/stopki BKS; zwraca (treść, data pisma ISO)."""
    body, letter_date = [], None
    for line in text.splitlines():
        s = line.strip()
        m = DATE_LINE.match(s)
        if m:
            month = deadlines._MONTHS_PL.get(m.group(2).lower())
            if month:
                letter_date = f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"
            continue
        if LETTERHEAD.match(s) or CASE_LINE.match(s.replace(" ", "")) or CASE_LINE.match(s):
            continue
        body.append(s)
    return reflow(body), letter_date


def departments_in(text: str) -> list[str]:
    text = " ".join(text.split())  # nazwy wydziałów bywają złamane między wierszami
    found = []
    for code, name, _ in seed_data.DEPARTMENTS:
        if code == "BKS":  # koordynator — występuje w nagłówku każdego pisma
            continue
        if name.lower() in text.lower() and code not in found:
            found.append(code)
    return found


def main(src: Path) -> None:
    samples = src / "Przykładowe wnioski i odpowiedzi"
    xlsx = next((src / "Schemat kalendarium").glob("*.xlsx"))
    known = {code for code, _, _ in seed_data.DEPARTMENTS}
    records, warnings = excel_import.parse_workbook(xlsx.read_bytes(), known)
    for w in warnings:
        print("UWAGA:", w)

    cases = []
    for rec in records:
        nr = rec["case_number"]
        docs = []
        request_text = None
        for path in sorted(samples.glob(f"*{nr}*")):
            kind = path.name.split(" - ")[0].strip().lower()
            kind = {"wniosek": "wniosek", "odpowiedź": "odpowiedz", "kwerenda": "kwerenda", "doprecyzowanie": "doprecyzowanie"}.get(kind)
            if not kind:
                continue
            ext = extraction.extract(path.name, path.read_bytes())
            print(f"{nr:24} {kind:15} ocr={ext.used_ocr} jakość={ext.quality:.2f} znaki={len(ext.text)}")
            if kind == "wniosek":
                if ext.warning:
                    rec["notes"] = "; ".join(filter(None, [rec.get("notes"), "Wniosek odręczny (skan) — OCR nieczytelny, treść wg rejestru"]))
                    continue
                request_text = ext.text
                docs.append({"kind": kind, "filename": path.name, "text": ext.text, "document_date": rec["received_date"]})
            else:
                body, letter_date = letter_body(ext.text)
                docs.append({"kind": kind, "filename": path.name, "text": body, "document_date": letter_date})

        reply = next((d for d in docs if d["kind"] == "odpowiedz"), None)
        # Komórki merytoryczne wskazane w pismach sprawy (odpowiedź, kwerenda, doprecyzowanie).
        rec["departments"] = rec["departments"] or departments_in(" ".join(d["text"] for d in docs if d["kind"] != "wniosek"))
        if reply:
            rec["response_text"] = reply["text"]
            if "nie jest dysponentem" in reply["text"]:
                rec["procedure_mode"] = "nie_dysponent"
        for d in docs:
            if d["kind"] in ("kwerenda", "doprecyzowanie"):
                note = "kwerenda — przedłużenie terminu (art. 13 ust. 2 u.d.i.p.)" if d["kind"] == "kwerenda" else "wezwanie do doprecyzowania wniosku"
                if note not in (rec.get("notes") or ""):
                    rec["notes"] = "; ".join(filter(None, [rec.get("notes"), note]))
        rec["request_text"] = request_text
        rec["documents"] = docs
        cases.append(rec)

    ordinance_pdf = next((src / "Dokumenty i podstawy prawne").glob("Zarządzenie*.pdf"))
    text = extraction.extract(ordinance_pdf.name, ordinance_pdf.read_bytes()).text
    for old, new in ORDINANCE_FIXES:
        text = text.replace(old, new)
    # Odcinamy nieczytelny OCR podpisów/pieczęci po § 15.
    text = re.split(r"\n\d\s*\nJh Y", text)[0]
    rules = [{"title": t, "source": ORDINANCE_SOURCE, "content": c} for t, c in legal_text.split_units(text, ORDINANCE_TITLE)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "Dane testowe z materiałów wyzwania UMB (Hacknation 2026). Odpowiedzi zanonimizowane przez organizatora.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cases": cases,
        "rules": rules,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {OUT} — spraw: {len(cases)}, paragrafów zarządzenia: {len(rules)}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "C:/Hacknation 2026 - UMB"))
