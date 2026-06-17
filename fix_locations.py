import json
import re

with open('backups/jobs_backup_20260617_165012.json', 'r', encoding='utf-8') as f:
    backup_jobs = json.load(f)

backup_locations = {j['url']: j.get('location', '') for j in backup_jobs}

with open('jobs.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)

oulu_region = {'Oulu', 'Kempele', 'Liminka', 'Haukipudas', 'Oulunsalo', 'Kiiminki', 'Tyrnävä', 'Muhos', 'Lumijoki', 'Hailuoto'}
helsinki_region = {'Helsinki', 'Espoo', 'Vantaa', 'Kauniainen', 'Kerava', 'Sipoo', 'Kirkkonummi', 'Tuusula', 'Järvenpää', 'Nurmijärvi', 'Vihti', 'Porvoo', 'Lohja', 'Hyvinkää', 'Mäntsälä'}
turku_region = {'Turku', 'Kaarina', 'Raisio', 'Naantali', 'Lieto', 'Parainen', 'Paimio', 'Masku', 'Rusko', 'Nousiainen', 'Salo'}
tampere_region = {'Tampere', 'Nokia', 'Ylöjärvi', 'Kangasala', 'Lempäälä', 'Pirkkala', 'Orivesi', 'Valkeakoski', 'Vesilahti', 'Hämeenkyrö'}
jyvaskyla_region = {'Jyväskylä', 'Muurame', 'Laukaa', 'Äänekoski', 'Jämsä', 'Keuruu', 'Petäjävesi', 'Toivakka', 'Uurainen'}
rovaniemi_region = {'Rovaniemi', 'Ranua', 'Pello', 'Ylitornio', 'Kemijärvi', 'Sodankylä'}

def get_region(loc):
    if not loc or loc in ['N/A', 'Unknown', 'Extract via OpenClaw']:
        return loc
    base_city = loc.replace(', Finland', '').strip()
    
    words = set(re.findall(r'\b[A-ZÄÖÅa-zäöå]+\b', base_city.lower()))
    
    # Exact word match to avoid substring false positives
    for town in oulu_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Oulu Region, Finland'
    for town in helsinki_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Helsinki Region, Finland'
    for town in turku_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Turku Region, Finland'
    for town in tampere_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Tampere Region, Finland'
    for town in jyvaskyla_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Jyväskylä Region, Finland'
    for town in rovaniemi_region:
        if town.lower() in words or town.lower() in base_city.lower(): return 'Rovaniemi Region, Finland'
        
    return loc

restored = 0
for j in jobs:
    url = j['url']
    if url in backup_locations:
        original_loc = backup_locations[url]
        new_loc = get_region(original_loc)
        
        # Only append , Finland if it's explicitly a Finnish city that missed it in the original scrape
        # Wait, the prompt handles it now. Let's just leave original_loc as is if not in a region,
        # unless it is missing ', Finland' but we know it's in Finland. Actually, original_loc is fine.
        
        if j.get('location') != new_loc:
            j['location'] = new_loc
            restored += 1
    else:
        # newly scraped job
        j['location'] = get_region(j.get('location', ''))

with open('jobs.json', 'w', encoding='utf-8') as f:
    json.dump(jobs, f, indent=4, ensure_ascii=False)

print(f'Restored and mapped {restored} locations.')
