"""Modele żądań i odpowiedzi API (widoczne w Swagger UI: /docs)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from domain import CaseStatus, DeptStatus, DocumentKind, LetterKind, ProcedureMode, Urgency
from seed_data import MASK


# --- system --------------------------------------------------------------------------------------

class Health(BaseModel):
    status: str
    offline_mode: bool
    model: str
    llm_enabled: bool


class AppConfig(BaseModel):
    """Ustawienia, których potrzebuje interfejs, żeby nie powielać konfiguracji backendu."""

    case_number_prefix: str
    max_upload_mb: int
    request_extensions: list[str]
    knowledge_extensions: list[str]
    spreadsheet_extensions: list[str]
    answer_days: int
    soon_days: int = Field(description="Termin w ciągu tylu dni jest oznaczany jako zbliżający się (urgency = soon).")
    clarification_reply_days: int
    clarification_deadline_days: int = Field(description="Domyślny nowy termin przy wezwaniu do doprecyzowania.")
    model: str
    llm_enabled: bool
    offline_mode: bool


class DeadlineSuggestion(BaseModel):
    received_date: str
    deadline_date: str
    max_extended_deadline: str
    days_remaining: int
    urgency: Urgency
    note: str | None = Field(None, description="Ostrzeżenie, gdy termin wypada w dzień wolny.")


# --- przyjęcie wniosku -----------------------------------------------------------------------------

class ParsedRequest(BaseModel):
    wnioskodawca: str | None = None
    typ_wnioskodawcy: str | None = None
    adres_do_odpowiedzi: str | None = None
    forma_odpowiedzi: str | None = None
    data_na_pismie: str | None = None
    temat_skrot: str = ""
    pytania: list[str] = []
    kategoria: str = "inne"
    czy_to_wniosek_udip: bool = True
    uwagi: str = ""


class ExtractionInfo(BaseModel):
    has_text_layer: bool
    used_ocr: bool
    text_length: int
    quality: float = Field(description="Jakość odczytu 0–1 (udział rozpoznanych słów).")
    warning: str | None = Field(None, description="Np. pismo odręczne nieczytelne dla OCR — wpisz treść ręcznie.")
    manual_text_used: bool = False


class SimilarCase(BaseModel):
    id: int
    case_number: str
    received_date: str | None
    response_date: str | None
    applicant: str
    subject: str
    procedure_mode: ProcedureMode
    departments: list[str]
    response_text: str
    score: float | None = Field(None, description="Trafność (BM25) — im wyżej, tym bardziej podobna sprawa.")


class DepartmentSuggestion(BaseModel):
    code: str
    name: str
    reason: str


class ExternalEntitySuggestion(BaseModel):
    id: int
    name: str
    reason: str


class IntakeResponse(BaseModel):
    intake_id: int = Field(description="Przekaż do POST /api/cases/register, aby powiązać sprawę z treścią wniosku.")
    filename: str
    extraction: ExtractionInfo
    llm_used: bool
    parsed_request: ParsedRequest
    similar_cases: list[SimilarCase]
    suggested_departments: list[DepartmentSuggestion]
    suggested_external_entities: list[ExternalEntitySuggestion] = Field(
        description="Podmioty spoza UMB, które mogą być dysponentem informacji (pismo „nie_dysponent”)."
    )
    suggested_deadline: DeadlineSuggestion
    text_preview: str = Field(description="Początek wyodrębnionego tekstu (do weryfikacji odczytu).")


# --- rejestr spraw -----------------------------------------------------------------------------------

class CaseListItem(BaseModel):
    id: int
    ordinal: int | None = None
    case_number: str
    year: int
    applicant: str
    subject: str
    received_date: str | None
    deadline_date: str | None
    response_date: str | None = None
    date_parse_warning: str | None = None
    status: CaseStatus
    procedure_mode: ProcedureMode = ProcedureMode.zwykla
    departments: list[str] = []
    initials: str | None = Field(None, description="Osoba odpowiedzialna / inicjały (kolumna rejestru UMB).")
    notes: str | None = None
    days_remaining: int | None = Field(description="Dni do terminu; 0 dla spraw zakończonych (jak w rejestrze UMB).")
    answered_on_time: bool | None = Field(None, description="Dla spraw zakończonych: czy odpowiedź udzielona w terminie.")
    deadline_note: str | None = None
    original_deadline_date: str | None = Field(None, description="Termin 14-dniowy (przed przedłużeniem).")
    extension_days: int = Field(0, description="O ile dni przedłużono termin (kwerenda / doprecyzowanie).")
    max_deadline_date: str | None = Field(None, description="Najpóźniejszy dopuszczalny termin: 2 miesiące od wpływu (art. 13 ust. 2).")
    dept_total: int = 0
    dept_answered: int = 0
    dept_waiting: list[str] = []
    dept_clarification: list[str] = []
    urgency: Urgency = Field(description="Podświetlenie: overdue (po terminie), today, tomorrow, soon (≤3 dni), normal, done.")


class DepartmentStatusOut(BaseModel):
    code: str
    name: str
    status: DeptStatus
    status_label: str
    requested_at: str | None
    answered_at: str | None
    clarification_count: int
    note: str | None


class DepartmentAdd(BaseModel):
    code: str


class DepartmentStatusUpdate(BaseModel):
    status: DeptStatus
    note: str | None = None


class ClarificationIn(BaseModel):
    details: str | None = Field(None, description="Czego brakuje w odpowiedzi wydziału.")


class ClarificationOut(BaseModel):
    code: str
    text: str = Field(description="Treść prośby do wydziału — do skopiowania i wysłania przez urzędnika.")
    departments: list[DepartmentStatusOut]


class DepartmentReplyOut(BaseModel):
    id: int
    department: str | None
    filename: str | None
    text: str
    created_at: str


class AnonymizationCandidate(BaseModel):
    id: int
    quote: str
    category: str
    reason: str
    start: int
    end: int
    mask: str
    active: bool
    source: str


class DraftOut(BaseModel):
    id: int
    kind: LetterKind
    draft_text: str
    anonymization_candidates: list[AnonymizationCandidate]
    final_text: str | None
    generated_format: str | None
    llm_used: bool
    created_at: str


class CaseEvent(BaseModel):
    event: str
    detail: str | None
    created_at: str


class CaseDocument(BaseModel):
    id: int
    kind: DocumentKind
    filename: str | None
    text: str
    document_date: str | None
    created_at: str


class CaseDetail(CaseListItem):
    applicant_contact: str | None = None
    request_text: str | None = None
    parsed_request: ParsedRequest | None = None
    response_text: str | None = None
    department_status: list[DepartmentStatusOut] = []
    documents: list[CaseDocument] = []
    department_replies: list[DepartmentReplyOut] = []
    drafts: list[DraftOut] = []
    events: list[CaseEvent] = []


class RegisterCase(BaseModel):
    case_number: str | None = Field(None, description="Znak sprawy; puste = nadany automatycznie (CASE_NUMBER_PREFIX.n.rok).")
    year: int | None = None
    applicant: str
    applicant_contact: str | None = None
    subject: str
    received_date: date
    deadline_date: date | None = Field(None, description="Puste = 14 dni od daty wpływu.")
    departments: list[str] = []
    initials: str | None = None
    procedure_mode: ProcedureMode = ProcedureMode.zwykla
    notes: str | None = None
    intake_id: int | None = None
    parsed_request: ParsedRequest | None = None
    generate_dept_request_template: bool = False


class RegisterResponse(BaseModel):
    id: int
    case_number: str
    status: CaseStatus
    deadline_date: str
    departments: list[str]
    request_templates: dict[str, str] = {}


class UpdateCase(BaseModel):
    case_number: str | None = None
    applicant: str | None = None
    applicant_contact: str | None = None
    subject: str | None = None
    received_date: date | None = None
    deadline_date: date | None = None
    response_date: date | None = None
    departments: list[str] | None = None
    initials: str | None = None
    procedure_mode: ProcedureMode | None = None
    notes: str | None = None


class StatusUpdate(BaseModel):
    status: CaseStatus
    deadline_date: date | None = Field(
        None, description="Opcjonalnie nowy termin, np. przy kwerendzie/przedłużeniu (maks. 2 miesiące od wpływu)."
    )
    note: str | None = None


class StatusResponse(BaseModel):
    case_id: int
    status: CaseStatus
    deadline_date: str | None = None
    days_remaining: int | None = None


class LetterRequest(BaseModel):
    kind: LetterKind
    new_deadline: date | None = Field(None, description="Kwerenda/doprecyzowanie: nowy termin (domyślnie wyliczany, maks. 2 miesiące).")
    external_entity_id: int | None = Field(None, description="nie_dysponent: podmiot właściwy (GET /api/knowledge/external-entities).")
    department: str | None = Field(None, description="Symbol komórki, np. WAB (doprecyzowanie).")
    details: str | None = Field(None, description="Doprecyzowanie: czego ma dotyczyć.")
    apply_status: bool = Field(True, description="Ustaw status sprawy (kwerenda/doprecyzowanie) i nowy termin.")


class DraftResult(BaseModel):
    case_id: int
    status: CaseStatus
    kind: LetterKind
    deadline_date: str | None = None
    warning: str | None = None
    draft_id: int
    draft_text: str
    llm_used: bool
    anonymization_candidates: list[AnonymizationCandidate]


# --- odpowiedź i anonimizacja -------------------------------------------------------------------------

class AnonymizationItem(BaseModel):
    start: int
    end: int
    mask: str = MASK
    active: bool = True


class GenerateRequest(BaseModel):
    draft_id: int
    content: str
    format: Literal["docx", "pdf", "txt"] = "docx"
    anonymization_items: list[AnonymizationItem] = []


class SendRequest(BaseModel):
    case_id: int
    draft_id: int | None = None
    final_content: str = Field(description="Treść wysłanego pisma; zaznaczone fragmenty maskuje serwer.")
    anonymization_items: list[AnonymizationItem] = []
    response_date: date | None = None


class SendResponse(BaseModel):
    case_id: int
    status: CaseStatus
    response_date: str


class AnonymizePreviewRequest(BaseModel):
    text: str
    known_people: list[str] = []


# --- baza wiedzy ------------------------------------------------------------------------------------

class RuleIn(BaseModel):
    title: str
    source: str = ""
    content: str
    is_active: bool = True


class RuleUpdate(BaseModel):
    title: str | None = None
    source: str | None = None
    content: str | None = None
    is_active: bool | None = None


class RuleOut(RuleIn):
    id: int
    created_at: str
    updated_at: str


class CategoryIn(BaseModel):
    name: str
    legal_basis: str = ""
    regex: str | None = None
    mask: str = MASK
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = None
    legal_basis: str | None = None
    regex: str | None = None
    mask: str | None = None
    is_active: bool | None = None


class CategoryOut(CategoryIn):
    id: int


class DepartmentIn(BaseModel):
    code: str
    name: str
    keywords: str = ""
    is_active: bool = True


class DepartmentOut(DepartmentIn):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = None
    keywords: str | None = None
    is_active: bool | None = None


class ExternalEntityIn(BaseModel):
    name: str
    name_genitive: str = Field(description="Nazwa w dopełniaczu, np. „Zarządu Dróg Miejskich…” (do formuły „winien się zwrócić do …”).")
    contact: str = ""
    keywords: str = ""
    is_active: bool = True


class ExternalEntityUpdate(BaseModel):
    name: str | None = None
    name_genitive: str | None = None
    contact: str | None = None
    keywords: str | None = None
    is_active: bool | None = None


class ExternalEntityOut(ExternalEntityIn):
    id: int


class ManualCase(BaseModel):
    case_number: str
    year: int | None = None
    applicant: str = ""
    subject: str
    received_date: date | None = None
    response_date: date | None = None
    procedure_mode: ProcedureMode = ProcedureMode.zwykla
    departments: list[str] = []
    request_text: str | None = None
    response_text: str = ""


class ManualCaseOut(BaseModel):
    id: int
    case_number: str


class ImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    warnings: list[str]
