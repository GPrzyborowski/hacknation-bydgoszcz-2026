"""Buduje backend/app/seed/umb_demo.json z materiałów wyzwania UMB (folder źródłowy jest tylko czytany).

Wynik: 10 spraw z rejestru (Excel) z treścią wniosków, odpowiedzi i pism z toku sprawy oraz Zarządzenie
nr 535/2024 podzielone na paragrafy. Skany wymagają programu Tesseract z językiem polskim.

    python backend/scripts/build_demo_seed.py "C:/Hacknation 2026 - UMB" [--out ścieżka.json]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import config  # noqa: E402
import seed_data  # noqa: E402
from domain import DocumentKind, ProcedureMode  # noqa: E402
from services import deadlines, excel_import, extraction, legal_text  # noqa: E402

DEFAULT_OUTPUT = APP_DIR / "seed" / "umb_demo.json"
COORDINATOR_DEPARTMENT = "BKS"  # występuje w nagłówku każdego pisma, więc nie wskazuje komórki merytorycznej

# Wiersze nagłówka i stopki pism BKS w postaci, jaką zwraca odczyt PDF.
LETTERHEAD_LINE = re.compile(
    r"^(URZĄD MIASTA BYDGOSZCZY|Biuro Komunikacji Społecznej|Biuro Komunikacji Urząd Miasta|Bydgoszczy Społecznej|"
    r"Urząd Miasta Bydgoszczy|85\s*-\s*102 Bydgoszcz, ul\. Jezuicka 1|tel\.:? \(52\).*|e-?mail:\s*(bks|bip)@.*)\s*$",
    re.IGNORECASE,
)
DATE_LINE = re.compile(rf"^{config.OFFICE_CITY},\s*(?:dnia\s*)?\d{{1,2}}\s+\w+\s+\d{{4}}", re.IGNORECASE)
_PREFIX = r"\.\s*".join(re.escape(part) for part in config.CASE_NUMBER_PREFIX.split("."))
CASE_NUMBER_LINE = re.compile(rf"^{_PREFIX}\.\s*\d+\s*\.\s*\d{{4}}\s*$")
# Wiersze, które zaczynają nowy akapit, a nie kontynuują poprzedniego.
PARAGRAPH_START = re.compile(
    r"^(Ad\s*\d|\d+[.)]|Załącznik|Łączę|Z wyrazami|Szanown|[Ww] odpowiedzi|[Ww] związku|[Ww] nawiązaniu|[Oo]dpowiadając)"
)

DOCUMENT_KINDS = {
    "wniosek": DocumentKind.wniosek,
    "odpowiedź": DocumentKind.odpowiedz,
    "kwerenda": DocumentKind.kwerenda,
    "doprecyzowanie": DocumentKind.doprecyzowanie,
}
INTERIM_NOTES = {
    DocumentKind.kwerenda: "kwerenda — przedłużenie terminu (art. 13 ust. 2 u.d.i.p.)",
    DocumentKind.doprecyzowanie: "wezwanie do doprecyzowania wniosku",
}
UNREADABLE_REQUEST_NOTE = "Wniosek odręczny (skan) — OCR nieczytelny, treść wg rejestru"

# Błędy OCR w warstwie tekstowej Zarządzenia, zweryfikowane z obrazem 1. strony dokumentu.
ORDINANCE_FIXES = [
    ("ZARZĄDZENIE NR 536, 2024", "ZARZĄDZENIE NR 535/2024"),
    ("z dnia AŻ jytwe)/MDU_ 2024 r.", "z dnia 23 września 2024 r."),
    ("bipQQum.bydgoszcz.pl", "bip@um.bydgoszcz.pl"),
    ("www,bip.um.bydgoszcz.pl", "www.bip.um.bydgoszcz.pl"),
    ("udip, udesi i", "udip, udcsi i"),
    ("\n89.1. AIP", "\n§ 9. 1. AIP"),
    ("wniosek. dotyczy", "wniosek dotyczy"),
]
ORDINANCE_SIGNATURES = re.compile(r"\n\d\s*\nJh Y")  # nieczytelny OCR podpisów i pieczęci po § 15
ORDINANCE_TITLE = "Zarządzenie nr 535/2024 Prezydenta Miasta Bydgoszczy"
ORDINANCE_SOURCE = "Zarządzenie nr 535/2024 z dnia 23 września 2024 r. w sprawie zasad i trybu udostępniania informacji publicznej"


def reflow(lines: list[str]) -> str:
    """Skleja wiersze akapitów, które PDF łamie w środku zdań; zachowuje „Ad 1”, listy i zwroty grzecznościowe."""
    paragraphs: list[str] = []
    for line in (line.strip() for line in lines):
        if not line:
            if paragraphs and paragraphs[-1]:
                paragraphs.append("")
            continue
        previous = paragraphs[-1] if paragraphs else ""
        continues = previous and not PARAGRAPH_START.match(line)
        if continues and previous.endswith("-") and line[:1].islower():
            paragraphs[-1] = previous[:-1] + line
        elif continues and (line[:1].islower() or not re.search(r"[.:;,?!)”]$", previous)) and not re.match(r"^(Ad\s*\d|Szanown)", previous):
            paragraphs[-1] = f"{previous} {line}"
        else:
            paragraphs.append(line)
    return "\n".join(paragraphs).strip()


def letter_body(text: str) -> tuple[str, str | None]:
    """Treść pisma bez nagłówka i stopki BKS oraz data pisma (ISO)."""
    body, letter_date = [], None
    for line in (line.strip() for line in text.splitlines()):
        if DATE_LINE.match(line):
            parsed, _ = deadlines.parse_date(line)
            letter_date = parsed.isoformat() if parsed else letter_date
            continue
        if LETTERHEAD_LINE.match(line) or CASE_NUMBER_LINE.match(line):
            continue
        body.append(line)
    return reflow(body), letter_date


def departments_in(text: str) -> list[str]:
    """Komórki merytoryczne wymienione w pismach (nazwy bywają złamane między wierszami)."""
    flat = " ".join(text.split()).lower()
    return [code for code, name, _ in seed_data.DEPARTMENTS if code != COORDINATOR_DEPARTMENT and name.lower() in flat]


def case_documents(samples_dir: Path, record: dict) -> list[dict]:
    documents = []
    for path in sorted(samples_dir.glob(f"*{record['case_number']}*")):
        kind = DOCUMENT_KINDS.get(path.name.split(" - ")[0].strip().lower())
        if kind is None:
            continue
        extracted = extraction.extract(path.name, path.read_bytes())
        print(f"{record['case_number']:24} {kind:15} ocr={extracted.used_ocr} jakość={extracted.quality:.2f} znaki={len(extracted.text)}")
        if kind == DocumentKind.wniosek:
            if extracted.warning:
                record["notes"] = "; ".join(filter(None, [record.get("notes"), UNREADABLE_REQUEST_NOTE]))
                continue
            documents.append({"kind": kind, "filename": path.name, "text": extracted.text, "document_date": record["received_date"]})
        else:
            body, letter_date = letter_body(extracted.text)
            documents.append({"kind": kind, "filename": path.name, "text": body, "document_date": letter_date})
    return documents


def build_case(samples_dir: Path, record: dict) -> dict:
    documents = case_documents(samples_dir, record)
    letters = [document for document in documents if document["kind"] != DocumentKind.wniosek]
    record["departments"] = record["departments"] or departments_in(" ".join(document["text"] for document in letters))
    reply = next((document for document in letters if document["kind"] == DocumentKind.odpowiedz), None)
    if reply:
        record["response_text"] = reply["text"]
        if "nie jest dysponentem" in reply["text"]:
            record["procedure_mode"] = ProcedureMode.nie_dysponent
    for document in letters:
        note = INTERIM_NOTES.get(document["kind"])
        if note and note not in (record.get("notes") or ""):
            record["notes"] = "; ".join(filter(None, [record.get("notes"), note]))
    request = next((document for document in documents if document["kind"] == DocumentKind.wniosek), None)
    record["request_text"] = request["text"] if request else None
    record["documents"] = documents
    return record


def ordinance_rules(source_dir: Path) -> list[dict]:
    pdf = next((source_dir / "Dokumenty i podstawy prawne").glob("Zarządzenie*.pdf"))
    text = extraction.extract(pdf.name, pdf.read_bytes()).text
    for wrong, right in ORDINANCE_FIXES:
        text = text.replace(wrong, right)
    text = ORDINANCE_SIGNATURES.split(text)[0]
    return [{"title": title, "source": ORDINANCE_SOURCE, "content": content} for title, content in legal_text.split_units(text, ORDINANCE_TITLE)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, nargs="?", default=Path("C:/Hacknation 2026 - UMB"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    workbook = next((args.source / "Schemat kalendarium").glob("*.xlsx"))
    known_departments = {code for code, _, _ in seed_data.DEPARTMENTS}
    records, warnings = excel_import.parse_workbook(workbook.read_bytes(), known_departments)
    for warning in warnings:
        print("UWAGA:", warning)

    samples_dir = args.source / "Przykładowe wnioski i odpowiedzi"
    payload = {
        "description": "Dane testowe z materiałów wyzwania UMB (Hacknation 2026). Odpowiedzi zanonimizowane przez organizatora.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cases": [build_case(samples_dir, record) for record in records],
        "rules": ordinance_rules(args.source),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {args.out} — spraw: {len(payload['cases'])}, paragrafów zarządzenia: {len(payload['rules'])}")


if __name__ == "__main__":
    main()
