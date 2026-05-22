#!/usr/bin/env python3
"""
Script to populate Polish and English translations in .po files.
"""

import re

# Translation dictionary: English -> Polish
translations = {
    # Navigation
    "Home": "Strona główna",
    "Persons": "Osoby",
    "Baptisms": "Chrzty",
    "Marriages": "Śluby",
    "Deaths": "Zgony",
    "Duplicates": "Duplikaty",
    "Graph": "Graf",
    "Korzen": "Korzen",
    
    # Common terms
    "Error": "Błąd",
    "Sort by": "Sortuj według",
    "Ascending": "Rosnąco",
    "Descending": "Malejąco",
    "Search": "Szukaj",
    "Filter": "Filtruj",
    "Apply Filters": "Zastosuj filtry",
    "Reset": "Resetuj",
    "Cancel": "Anuluj",
    "Yes": "Tak",
    "No": "Nie",
    "None": "Brak",
    "Unknown": "Nieznany",
    "All": "Wszystkie",
    
    # Gender
    "Male": "Mężczyzna",
    "Female": "Kobieta",
    "Gender": "Płeć",
    "All Genders": "Wszystkie płcie",
    
    # Dates and places
    "Date": "Data",
    "Birth Date": "Data urodzenia",
    "Death Date": "Data śmierci",
    "Baptism Date": "Data chrztu",
    "Marriage Date": "Data ślubu",
    "Burial Date": "Data pogrzebu",
    "Birth Place": "Miejsce urodzenia",
    "Death Place": "Miejsce śmierci",
    "Parish": "Parafia",
    "Village": "Wieś",
    
    # Person details
    "Name": "Imię i nazwisko",
    "Child Name": "Imię dziecka",
    "Surname": "Nazwisko",
    "First Name": "Imię",
    "Last Name": "Nazwisko",
    "Full Name:": "Pełne imię i nazwisko:",
    "Maiden Name:": "Nazwisko panieńskie:",
    "née": "z domu",
    "Father": "Ojciec",
    "Mother": "Matka",
    "Child": "Dziecko",
    "Children": "Dzieci",
    "Parents": "Rodzice",
    "Father:": "Ojciec:",
    "Mother:": "Matka:",
    "Number of Children:": "Liczba dzieci:",
    
    # Status
    "Status": "Status",
    "All Status": "Wszystkie statusy",
    "Legitimate": "Ślubne",
    "Illegitimate": "Nieślubne",
    "Married (M)": "Żonaty",
    "Married (F)": "Zamężna",
    "Married (Conjugatus)": "Żonaty (Conjugatus)",
    "Married (Conjugata)": "Zamężna (Conjugata)",
    "Widower": "Wdowiec",
    "Widow": "Wdowa",
    "Widower (Viduus)": "Wdowiec (Viduus)",
    "Widow (Vidua)": "Wdowa (Vidua)",
    "Bachelor": "Kawaler",
    "Spinster": "Panna",
    "Bachelor (Juvenis)": "Kawaler (Juvenis)",
    "Spinster (Virgo)": "Panna (Virgo)",
    "Unmarried": "Niezamężna/Nieżonaty",
    "Unmarried (Virgo)": "Niezamężna (Virgo)",
    "Marital Status": "Stan cywilny",
    "All Marital Status": "Wszystkie stany cywilne",
    
    # Marriage details
    "married to": "poślubił(a)",
    "Spouse 1": "Małżonek 1",
    "Spouse 2": "Małżonek 2",
    "Groom Surname": "Nazwisko pana młodego",
    "Bride Surname": "Nazwisko panny młodej",
    "Groom's father": "Ojciec pana młodego",
    "Groom's mother": "Matka pana młodego",
    "Bride's father": "Ojciec panny młodej",
    "Bride's mother": "Matka panny młodej",
    "Banns": "Zapowiedzi",
    "Witnesses": "Świadkowie",
    "Marriage": "Ślub",
    "Details": "Szczegóły",
    
    # Death details
    "Deceased Name": "Imię i nazwisko zmarłego",
    "Deceased": "Zmarły",
    "Sacraments": "Sakramenty",
    "All Sacraments": "Wszystkie sakramenty",
    "Received": "Otrzymane",
    "Not Received": "Nie otrzymane",
    "Age": "Wiek",
    "years": "lat",
    "Age/Status": "Wiek/Status",
    
    # Records
    "Birth": "Urodzenie",
    "Death": "Zgon",
    "Records": "Rekordy",
    "Related Records": "Powiązane rekordy",
    "Baptism Records:": "Rekordy chrztu:",
    "Marriage Records:": "Rekordy ślubu:",
    "Death Records:": "Rekordy zgonu:",
    "As Father:": "Jako ojciec:",
    "As Mother:": "Jako matka:",
    "Record Type": "Typ rekordu",
    "All Types": "Wszystkie typy",
    "Record 1": "Rekord 1",
    "Record 2": "Rekord 2",
    "Record not found": "Nie znaleziono rekordu",
    
    # Counts and statistics
    "Total Baptisms": "Łącznie chrztów",
    "Total Marriages": "Łącznie ślubów",
    "Total Deaths": "Łącznie zgonów",
    "Total Persons": "Łącznie osób",
    "Total Detected": "Łącznie wykrytych",
    "Displayed (Filtered)": "Wyświetlone (Filtrowane)",
    "Current Page": "Bieżąca strona",
    
    # Pagination
    "First": "Pierwsza",
    "Previous": "Poprzednia",
    "Prev": "Poprz.",
    "Next": "Następna",
    "Last": "Ostatnia",
    "First page": "Pierwsza strona",
    "Previous page": "Poprzednia strona",
    "Next page": "Następna strona",
    "Last page": "Ostatnia strona",
    
    # Duplicate detection
    "Duplicate Detection": "Wykrywanie duplikatów",
    "Pending Review": "Oczekujące na przegląd",
    "Confirmed Duplicates": "Potwierdzone duplikaty",
    "Rejected": "Odrzucone",
    "Pending": "Oczekujące",
    "Confirmed": "Potwierdzone",
    "Minimum Score": "Minimalny wynik",
    "Similarity Breakdown": "Rozkład podobieństwa",
    "Vector Similarity": "Podobieństwo wektorowe",
    "Phonetic Similarity": "Podobieństwo fonetyczne",
    "Date Similarity": "Podobieństwo dat",
    "Location Similarity": "Podobieństwo lokalizacji",
    "Not a Duplicate": "Nie jest duplikatem",
    "Confirm Duplicate": "Potwierdź duplikat",
    "Detected": "Wykryto",
    "Method": "Metoda",
    "Reviewed by": "Przejrzane przez",
    "on": "dnia",
    "Notes": "Notatki",
    "Notes:": "Notatki:",
    
    # Graph/Tree
    "Family Tree Visualizer": "Wizualizator drzewa genealogicznego",
    "Person Limit": "Limit osób",
    "Generations": "Pokolenia",
    "Number of descendant generations to show": "Liczba pokoleń potomków do pokazania",
    "Load Family Tree": "Załaduj drzewo genealogiczne",
    "Reset View": "Resetuj widok",
    "Clear Ancestor": "Wyczyść przodka",
    "View Mode": "Tryb widoku",
    "Tree View": "Widok drzewa",
    "Family Clusters": "Klastry rodzinne",
    "Hide father-to-child edges": "Ukryj krawędzie ojciec-dziecko",
    "People": "Osoby",
    "Ancestor": "Przodek",
    "Loading graph data": "Ładowanie danych grafu",
    "Node Details": "Szczegóły węzła",
    "Family Tree Legend": "Legenda drzewa genealogicznego",
    "Parent → Child": "Rodzic → Dziecko",
    "Marriage 💑 (grouped together)": "Małżeństwo 💑 (zgrupowane razem)",
    
    # Upload and file management
    "Korzen - GEDCOM Upload": "Korzen - Przesyłanie GEDCOM",
    "Upload your GEDCOM file to begin processing genealogical data": "Prześlij plik GEDCOM, aby rozpocząć przetwarzanie danych genealogicznych",
    "Click to select or drag & drop": "Kliknij, aby wybrać lub przeciągnij i upuść",
    "GEDCOM files (.ged) - Max 16MB": "Pliki GEDCOM (.ged) - Maks. 16MB",
    "Upload File": "Prześlij plik",
    "Uploaded Files": "Przesłane pliki",
    "Sort by:": "Sortuj według:",
    "Upload Date": "Data przesłania",
    "Filename": "Nazwa pliku",
    "File Size": "Rozmiar pliku",
    "Parse GEDCOM": "Parsuj GEDCOM",
    "Selected:": "Wybrano:",
    "Please select a file first": "Najpierw wybierz plik",
    "Please select a valid GEDCOM file (.ged or .gedcom)": "Wybierz prawidłowy plik GEDCOM (.ged lub .gedcom)",
    "Uploading...": "Przesyłanie...",
    "Upload failed": "Przesyłanie nie powiodło się",
    "Parsing...": "Parsowanie...",
    "Parsing failed": "Parsowanie nie powiodło się",
    
    # Database operations
    "Reset Database": "Resetuj bazę danych",
    "Confirm Database Reset": "Potwierdź reset bazy danych",
    "Warning:": "Ostrzeżenie:",
    "This action will permanently delete all data from the database, including:": "Ta akcja trwale usunie wszystkie dane z bazy danych, w tym:",
    "All uploaded files": "Wszystkie przesłane pliki",
    "All persons": "Wszystkie osoby",
    "All baptisms, marriages, and deaths": "Wszystkie chrzty, śluby i zgony",
    "This action cannot be undone!": "Tej akcji nie można cofnąć!",
    "Resetting...": "Resetowanie...",
    "Reset failed": "Reset nie powiódł się",
    
    # Statistics
    "Import Statistics:": "Statystyki importu:",
    "Persons:": "Osoby:",
    "Baptisms:": "Chrzty:",
    "Marriages:": "Śluby:",
    "Deaths:": "Zgony:",
    "AGE Graph Import:": "Import grafu AGE:",
    "Time:": "Czas:",
    "Vertices created:": "Utworzone wierzchołki:",
    "Edges created:": "Utworzone krawędzie:",
    "Errors:": "Błędy:",
    "Warnings:": "Ostrzeżenia:",
    "Total in Graph:": "Łącznie w grafie:",
    "Events:": "Wydarzenia:",
    "Parent-child edges:": "Krawędzie rodzic-dziecko:",
    "Marriage edges:": "Krawędzie małżeństwa:",
    
    # Person details
    "Basic Information": "Podstawowe informacje",
    "Gender:": "Płeć:",
    "Occupation": "Zawód",
    "Occupation:": "Zawód:",
    "Birth Information": "Informacje o urodzeniu",
    "Birth Date:": "Data urodzenia:",
    "estimated": "szacowana",
    "Birth Place:": "Miejsce urodzenia:",
    "Death Information": "Informacje o śmierci",
    "Death Date:": "Data śmierci:",
    "Death Place:": "Miejsce śmierci:",
    "Lifespan:": "Długość życia:",
    "Location Information": "Informacje o lokalizacji",
    "Parish:": "Parafia:",
    "Residence:": "Miejsce zamieszkania:",
    "House Number:": "Numer domu:",
    "Additional Information": "Dodatkowe informacje",
    "GEDCOM ID:": "ID GEDCOM:",
    "b.": "ur.",
    
    # Messages
    "No Baptism Records Found": "Nie znaleziono rekordów chrztu",
    "No Marriage Records Found": "Nie znaleziono rekordów ślubu",
    "No Death Records Found": "Nie znaleziono rekordów zgonu",
    "No Persons Found": "Nie znaleziono osób",
    "No Duplicate Candidates Found": "Nie znaleziono kandydatów na duplikaty",
    "Upload and parse a GEDCOM file to see baptism records in the database.": "Prześlij i sparsuj plik GEDCOM, aby zobaczyć rekordy chrztu w bazie danych.",
    "Upload and parse a GEDCOM file to see marriage records in the database.": "Prześlij i sparsuj plik GEDCOM, aby zobaczyć rekordy ślubu w bazie danych.",
    "Upload and parse a GEDCOM file to see death records in the database.": "Prześlij i sparsuj plik GEDCOM, aby zobaczyć rekordy zgonu w bazie danych.",
    "Upload and parse a GEDCOM file to see persons in the database.": "Prześlij i sparsuj plik GEDCOM, aby zobaczyć osoby w bazie danych.",
    "Try adjusting your filters or import GEDCOM files to detect duplicates.": "Spróbuj dostosować filtry lub zaimportować pliki GEDCOM, aby wykryć duplikaty.",
    "No files uploaded yet. Upload your first GEDCOM file above!": "Nie przesłano jeszcze żadnych plików. Prześlij swój pierwszy plik GEDCOM powyżej!",
    
    # Search placeholders
    "Search by child name, parents, parish, or village...": "Szukaj po imieniu dziecka, rodzicach, parafii lub wsi...",
    "Search by spouse names, parish, or village...": "Szukaj po imionach małżonków, parafii lub wsi...",
    "Search by deceased name, parish, village, or cemetery...": "Szukaj po imieniu zmarłego, parafii, wsi lub cmentarzu...",
    "Search by name, place, or occupation...": "Szukaj po imieniu, miejscu lub zawodzie...",
    
    # Duplicate actions
    "Confirming duplicate. Add notes - optional": "Potwierdzanie duplikatu. Dodaj notatki - opcjonalnie",
    "Rejecting duplicate. Add notes - optional": "Odrzucanie duplikatu. Dodaj notatki - opcjonalnie",
    "Processing...": "Przetwarzanie...",
    "Duplicate confirmed successfully!": "Duplikat potwierdzony pomyślnie!",
    "Duplicate rejected successfully!": "Duplikat odrzucony pomyślnie!",
    "Unknown error": "Nieznany błąd",
    "Network error": "Błąd sieci",
    "Error:": "Błąd:",
    
    # Footer
    "Korzen Genealogy Application": "Aplikacja genealogiczna Korzen",
    "About": "O aplikacji",
    "Help": "Pomoc",
    "Privacy": "Prywatność",
    
    # Language
    "Polish": "Polski",
    "English": "Angielski",
    
    # Title
    "Korzen - Genealogy Application": "Korzen - Aplikacja genealogiczna",
    "Persons - Korzen": "Osoby - Korzen",
}

def populate_po_file(po_file_path, is_polish=True):
    """Populate a .po file with translations."""
    with open(po_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Process each msgid/msgstr pair
    lines = content.split('\n')
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Look for msgid lines
        if line.startswith('msgid "') and not line.startswith('msgid ""'):
            # Extract the msgid value
            msgid_match = re.match(r'msgid "(.*)"', line)
            if msgid_match:
                msgid_value = msgid_match.group(1)
                
                # Look ahead for msgstr line
                if i + 1 < len(lines) and lines[i + 1].startswith('msgstr ""'):
                    # We have an empty msgstr, fill it
                    if is_polish and msgid_value in translations:
                        # Polish translation
                        new_lines.append(f'msgstr "{translations[msgid_value]}"')
                        i += 2  # Skip the original msgstr line
                        continue
                    elif not is_polish:
                        # English - keep the original English text
                        new_lines.append(f'msgstr "{msgid_value}"')
                        i += 2
                        continue
        
        i += 1
    
    # Write back
    with open(po_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print(f"✓ Populated {po_file_path}")

if __name__ == "__main__":
    print("Populating translation files...")
    print("=" * 60)
    
    # Populate Polish translations
    populate_po_file('src/app/translations/pl/LC_MESSAGES/messages.po', is_polish=True)
    
    # Populate English translations (keep original English)
    populate_po_file('src/app/translations/en/LC_MESSAGES/messages.po', is_polish=False)
    
    print("=" * 60)
    print("✓ Translation files populated successfully!")
    print("\nNext step: Compile translations with:")
    print("  pybabel compile -d src/app/translations")
