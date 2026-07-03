import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

def clean_page_text(text):
    lines = text.split('\n')
    cleaned_lines = []
    skip_patterns = [
        'evästeasetukset', 'evästekäytäntö', 'hyväksy kaikki eväste',
        'hylkää kaikki', 'käytämme evästeitä',
        'cookie settings', 'accept all cookies', 'reject all',
        'siirry sivun pääsisältöön', 'pääsisällön alku',
        'kirjaudu sisään', 'työnantajat / lähetä',
        'skip to main content', 'sign in',
        'etsi työpaikkoja', 'find jobs', 'search jobs',
        '© 20', 'indeed ja saavutettavuus', 'tietosuojakeskus',
        'dsa-ilmoitukset', 'verkkoturvallisuussivu',
        'selaa työpaikkoja', 'maat',
        'privacy center', 'accessibility',
        'sinun on luotava indeed-tili', 'hae työpaikkaa yrityksen sivustolla',
        'tee ilmoitus työpaikasta',
        'checking your browser', 'ddos-guard', 'please stand by',
        'please allow up to',
    ]
    nav_words = {'koti', 'home', 'mitä', 'missä', 'about', 'ohje', 'ehdot'}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(pat in lower for pat in skip_patterns):
            continue
        if lower in nav_words:
            continue
        if len(stripped) <= 2 or stripped == '&nbsp;':
            continue
        cleaned_lines.append(stripped)
    return '\n'.join(cleaned_lines)

def extract_location_from_text(text):
    lines = text.split('\n')
    postal_pattern = re.compile(r'\b(\d{5})\s+([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)?)\b')
    for line in lines:
        match = postal_pattern.search(line.strip())
        if match:
            city = match.group(2).strip()
            return f"{city}, Finland"
    for i, line in enumerate(lines):
        if line.strip().lower() == 'sijainti' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and len(next_line) > 2:
                match = postal_pattern.search(next_line)
                if match:
                    return f"{match.group(2).strip()}, Finland"
                if len(next_line) < 60:
                    return f"{next_line}, Finland"
    return None

def extract_company_from_text(text, job_title):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and job_title and stripped.lower() == job_title.lower():
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                if next_line and len(next_line) > 2 and len(next_line) < 80:
                    if re.match(r'^\d{5}\s', next_line):
                        continue
                    if next_line.lower() in ['vakituinen', 'sijainti', 'työpaikan tiedot', 'työpaikan tyyppi']:
                        continue
                    return next_line
    company_patterns = [
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*\s+(?:kunta|kaupunki|Oy|Ab|Oyj|ry))\b'),
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+n\s+kaupunki)\b'),
        re.compile(r'\b([A-ZÄÖÅ][a-zäöå]+n\s+kunta)\b'),
    ]
    for pattern in company_patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None

# Test on the saved Indeed page
text = open('scratch/indeed_page.txt', encoding='utf-8').read()
cleaned = clean_page_text(text)

job_title = "Henkilöstö- ja lakiasiainjohtaja"

location = extract_location_from_text(cleaned)
company = extract_company_from_text(cleaned, job_title)

print(f"Extracted Location: {location}")
print(f"Extracted Company: {company}")
