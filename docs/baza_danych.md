erDiagram
    CASES ||--o{ CASE_DEPARTMENTS : "kierowana do"
    DEPARTMENTS ||--o{ CASE_DEPARTMENTS : "uczestniczy w"
    CASES ||--o{ DOCUMENTS : "zawiera"
    CASES ||--o{ RESPONSE_DRAFTS : "posiada wersje"
    RESPONSE_DRAFTS ||--o{ ANONYMIZATION_ITEMS : "ma sugestie"
    CASES ||--o| CASES_FTS : "indeksowane w"

    LEGAL_RULES ||--o| LEGAL_RULES_FTS : "indeksowane w"
    ANONYMIZATION_CATEGORIES ||--o{ ANONYMIZATION_ITEMS : "kategoryzuje"

    CASES {
        int id PK
        int lp "Lp. z rejestru"
        text case_number UK "Numer sprawy (np. BKS.IV.1431.590.2026)"
        int year "Rok sprawy"
        text applicant "Wnioskodawca"
        text subject "Przedmiot zapytania"
        text extracted_text "Treść wniosku"
        date received_date "Data wpływu"
        date deadline_date "Wyznaczony termin (parsowany)"
        text raw_deadline_text "Oryginalny zapis terminu z Excela/pisma"
        text date_parse_warning "Ostrzeżenie walidatora dat"
        date response_date "Faktyczna data odpowiedzi"
        text assignee "Osoba odpowiedzialna"
        text status "Status toku sprawy"
        text procedure_mode "zwykla | bip | przetworzona | odmowa | nie_dysponent"
        bool is_in_knowledge_base "Czy sprawa służy jako wzorzec w bazie wiedzy"
        datetime updated_at
    }

    LEGAL_RULES {
        int id PK
        text rule_code UK "Kod reguły (np. UDIP_ART_13_2, ZARZ_535_2024)"
        text category "ustawa | zarzadzenie | instrukcja_bip | wzor_klauzuli"
        text title "Tytuł aktu / reguły"
        text legal_basis "Aktualny publikator (np. Dz. U. z 2022 r. poz. 902, z 2025 r. poz. 1844)"
        text content "Treść przepisu, procedury lub gotowej formułki do pism"
        text source_url "Link do ISAP / BIP UMB"
        date effective_from "Data obowiązywania od"
        bool is_active "Czy aktywna w promptach i walidacji"
        text updated_by "Kto zmodyfikował w urzędzie"
        datetime updated_at
    }

    ANONYMIZATION_CATEGORIES {
        int id PK
        int code UK "Numer kategorii (1..28+)"
        text name "Nazwa kategorii (edytowalna przez urząd)"
        text legal_basis "Podstawa prawna wyłączenia (np. art. 5 ust. 2 UDIP)"
        text regex_pattern "Opcjonalny wzorzec regex dla twardych danych"
        text detection_hint "Wskazówka kontekstowa dla LLM / urzędnika"
        text default_mask "Domyślna maska zaczernienia"
        bool is_active "Czy aktywna"
        datetime updated_at
    }

    DEPARTMENTS {
        int id PK
        text code UK "Symbol komórki (np. BKS, WAB, WSO)"
        text name "Nazwa Wydziału lub Biura UMB (edytowalna)"
        text unit_type "wydzial | biuro"
        text keywords "Słowa kluczowe kompetencji"
        text email "Adres kontaktowy komórki"
        bool is_active "Czy aktywna (obsługa likwidacji/zmian wydziałów)"
        datetime updated_at
    }

    CASE_DEPARTMENTS {
        int id PK
        int case_id FK
        int department_id FK
        text request_template
        text dept_status
        datetime updated_at
    }

    DOCUMENTS {
        int id PK
        int case_id FK
        int department_id FK
        text doc_role
        text original_filename
        text storage_path
        text extracted_text
        datetime uploaded_at
    }

    RESPONSE_DRAFTS {
        int id PK
        int case_id FK
        int version
        text raw_content
        text anonymized_content
        bool is_final
        datetime created_at
    }

    ANONYMIZATION_ITEMS {
        int id PK
        int draft_id FK
        int category_id FK
        text detection_source
        text original_text
        text replacement_mask
        int start_offset
        int end_offset
        text state
    }

    CASES_FTS {
        int case_id "UNINDEXED"
        text case_number
        text subject
        text extracted_text
        text final_response_text
    }

    LEGAL_RULES_FTS {
        int rule_id "UNINDEXED"
        text rule_code
        text title
        text legal_basis
        text content
    }