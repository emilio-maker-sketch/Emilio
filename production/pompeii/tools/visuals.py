"""Sentence-level visual matching: what the narrator says is what the viewer sees.
Priority per sentence: 1) a generated AI image made for that exact sentence (script/ai_shots.json),
2) keyword rules -> curated library themes, 3) the paragraph's own [v:] themes.
"""
import json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AIDIR = os.path.join(ROOT, 'build', 'img', 'ai')

AIT = {  # generated images reused (with different crops) for closely related sentences
    'AIGLAD': [10, 9], 'AISIEGE': [4], 'AIQUAKE': [11, 13], 'AISTREET': [5, 0, 6], 'AIBAR': [0], 'AIERUPT': [2, 34, 30],
    'AIFLEE': [20, 3, 46, 42, 44], 'AIDARK': [47, 31, 36], 'AISHIP': [26, 24, 27, 28], 'AIPLINY': [27, 25, 32, 17],
    'AIYOUNG': [43, 46], 'AIWRITE': [18], 'AIBOAT': [35, 36, 37], 'AISCROLL': [39, 59], 'AIEXCAV': [50, 52, 53, 54],
    'AIASH': [48, 40], 'AIROOF': [22, 19], 'AIPRAY': [15], 'AIBEACH': [23, 32, 45],
    'AIBODY': [33], 'AIFOUNTAIN': [6], 'AIDYING': [32], 'AIMOTHER': [46, 43], 'AIBACCHUS': [8],
}
RULES = [  # (regex, themes) — first match wins, checked in order
    (r'gladiat|amphitheatre|spectators|\bbrawl\b|\bgames\b', ['AIGLAD']),
    (r'\bsiege\b|catapult|(?<!Trojan )\bwar\b|veterans|rebellion|Sulla', ['AISIEGE', 'PORTRAIT']),
    (r'earthquakes?|tremors?|\btremble|Herculaneum had collapsed|\bdamage\b|laid low|unsafe', ['AIQUAKE', 'RUINS']),
    (r'\broofs?\b|ceilings?|roof beams', ['AIROOF', 'PUMICEFX']),
    (r'pumice|stones were falling|\bhail\b|rattling|falling stones', ['PUMICEFX']),
    (r'\bsurges?\b|\bcurrents?\b|avalanche|scalding|\bheat\b|burning|\bflames?\b|\bfire\b|\bburned\b', ['FLOWFX', 'AIERUPT', 'ERUPT']),
    (r'\bpine\b|branches|trunk', ['PINE', 'ERUPT']),
    (r'\bcloud\b|\bcolumn\b|eruptions?|\berupt|plume|blast|stratosphere|magma', ['ERUPT', 'AIERUPT', 'ASHFX']),
    (r'\bash\b|snow|buried', ['AIASH', 'ASHFX']),
    (r'boat sheds|vaulted', ['AIBOAT']),
    (r'doorways?|\bgates?\b|city walls', ['GATE', 'AIFLEE', 'STREET']),
    (r'\bstreets?\b|paving|pavements?|stepping stones|\bruts\b|\broads?\b', ['STREET', 'AISTREET', 'RUINS']),
    (r'commerce|merchants|business|basilica|\bshops?\b|bakeries|\bbars\b|workshops', ['AIBAR', 'STREET', 'FOOD']),
    (r'mosaics?|House of the Faun', ['ISSUS', 'MOSAIC']),
    (r'\btemples?\b|\bforum\b|Jupiter|Apollo|Isis', ['TEMPLE', 'RUINS']),
    (r'\bbaths?\b|bathing', ['BATHS']),
    (r'\bwine\b|vineyards?|\bvines\b|grapes|amphora|\bjars?\b|fertile|plenty', ['AMPHORA']),
    (r'fish sauce|garum|lentils|\bfood\b|\bmeal\b|\bbread\b|loaves|\bate\b|pomegranates|chestnuts|walnuts|\bdined\b|\blunch\b', ['FOOD', 'AMPHORA']),
    (r'paint(ed|ing|ings)?\b|frescoe?s?|colours|coloured|\bthe rich\b|wealthy|grand homes|in style', ['FRESCO']),
    (r'inscriptions?|graffit|slogans?|\bvote\b|candidates|scrawl|scratched|\bwritten\b|lovers|passions|boasted|voices of', ['INSCRIPT', 'FRAG']),
    (r'gardens?|courtyards?|peristyle', ['GARDEN']),
    (r'statues?|\bgods?\b|goddess|\bshrine\b|\baltar\b|sacrifice|\bpray', ['AIPRAY', 'LARES', 'GODS']),
    (r'\bcoins?\b|money|valuables|bags of', ['COINS']),
    (r'\bgold\b|\brings?\b|bracelets?|jewellery|earrings', ['JEWEL']),
    (r'\blamps?\b|torch(es)?\b|candle', ['LAMPS']),
    (r'\bkeys?\b|\btools\b|belongings|possessions', ['OBJECTS']),
    (r'\bdogs?\b', ['DOG', 'CASTS']),
    (r'Seneca', ['SENECA']),
    (r'emperor|\bTitus\b|Vespasian', ['TITUS']),
    (r'two letters|\bletter\b|copied|\bwrote\b|account of', ['AIWRITE', 'SCHOLAR']),
    (r'Strabo|Tacitus|historian|philosopher|scholar|encyclopaedia|Natural History|naturalist|curiosity', ['SCHOLAR']),
    (r'\bships?\b|\bfleet\b|\bboats?\b|\bsail(ed|ing)?\b|quadrireme|warships|helmsman|\bnavy\b|Liburnian|steer', ['SHIPS', 'AISHIP', 'BAY']),
    (r'\bmother\b|\bwoman\b|\bwomen\b|\bsister\b|\bwife\b', ['AIYOUNG', 'WOMAN']),
    (r'\bnephew\b|seventeen-year-old|seventeen years old|young man|young Pliny|\byouth\b|Pliny the Younger', ['AIYOUNG', 'YOUTH']),
    (r'Pliny the Elder|\badmiral\b|\buncle\b|\bPliny\b|Plinius', ['PLINY', 'AIPLINY']),
    (r'darkness|\bdark\b|\bnight\b|blacker', ['DARKFX', 'AIDARK', 'LAMPS']),
    (r'\bfle(e|d|eing)\b|escape|crowd|streamed', ['AIFLEE']),
    (r'\bbodies\b|\bbody\b|\bdead\b|\bdied\b|\bdeath\b|victims|skeletons?|killed|\bcasts?\b|plaster|vanished', ['CASTS', 'MOURN', 'DARKFX']),
    (r'excavat|archaeolog|\bdig(ging)?\b|tunnel|uncover|excavators', ['EXCAV', 'AIEXCAV', 'RUINS']),
    (r'scrolls?|papyr|\blibrary\b|\bbooks?\b|\bread\b', ['AISCROLL', 'SCHOLAR', 'HERCART']),
    (r'Naples|metropolitan|residents|evacuation|populated', ['NAPLES', 'BAY']),
    (r'\bsea\b|\bshore(line)?\b|\bbeach\b|\bbay\b|coast|\bwaves\b|harbour|\bwater\b', ['BAY', 'AIBEACH']),
    (r'mountain|Vesuvius|volcano|summit|crater|\bslopes\b', ['VESUV', 'ERUPT']),
]
OVERRIDES = {
    'They were men, women and children.': ['AIBOAT'], 'A woman lying face down.': ['CASTS'],
    'A pair thought to be sisters': ['CASTS'], 'An adult wearing a gold bracelet': ['CASTS'],
    'Pliny got to his feet': ['AIDYING'], 'His nephew believed that the dense fumes': ['AIDYING'],
    'He was a large man': ['LAMPS', 'DARKFX'], 'Then he went to bed': ['LAMPS', 'DARKFX'],
    'Modern scientists have debated what killed him': ['AIBODY'], 'more like a man asleep than dead': ['AIBODY'],
    'a new generation of excavations has revealed whole rooms': ['FRESCO'],
    'at a place called Civita Giuliana': ['CASTS'], 'Within months, they had recovered whole columns of text': ['AISCROLL'],
    'But there was no attempt to rebuild': ['AIASH'], 'They rebuilt their lives': ['NAPLES', 'BAY'], 'Others stayed and rebuilt.': ['AIQUAKE'],
    'A prince serving in the Austrian army': ['AIEXCAV'], 'an architect named Domenico Fontana': ['AIEXCAV'],
    'Its tunnel ran straight through the buried city': ['AIEXCAV'], 'Pliny admitted that he did not cry out': ['AIMOTHER'],
    'She was old and heavy': ['AIMOTHER'], 'most of these victims died by suffocating': ['CASTS'],
    'More than eleven hundred bodies have been found': ['CASTS'], 'Studies of the skeletons suggest that the heat': ['AIBOAT'],
    'Near the water lay an overturned boat.': ['AIBOAT'], 'loaded his belongings onto boats': ['SHIPS'],
    'Charcoal does not last long on a wall': ['INSCRIPT'], 'It gives a date equivalent to the seventeenth of October.': ['INSCRIPT'],
    'The Greek geographer Strabo': ['SCHOLAR'], 'He suggested that the area might once have burned': ['VESUV'],
    'But he had no idea that the fire was only sleeping.': ['VESUV'], 'a place of adventure and of wine, not of fire': ['VESUV'],
    'The water supply had been partly cut off': ['AIFOUNTAIN'], 'It fell at a rate of perhaps fifteen centimetres': ['PUMICEFX'],
    "Mixed with it came larger rocks, torn from the walls of the volcano's throat": ['PUMICEFX'],
    'Most scholars believe it is Vesuvius, the only image': ['AIBACCHUS'], 'Roofs had collapsed across the city.': ['AIROOF'],
    'And for nearly seventeen centuries': ['AIASH'], 'In seventeen thirty-eight, the new king of Naples': ['EXCAV', 'NAPLES'],
    'Ten years later, in seventeen forty-eight': ['AIEXCAV', 'EXCAV'],
}
SHAKE = re.compile(r'earthquake|tremors?|shaking|\bshook\b|trembl|sway', re.I)
CRX = [(re.compile(p, re.I), t) for p, t in RULES]

def load_ai():
    out = []
    path = os.path.join(ROOT, 'script', 'ai_shots.json')
    if not os.path.exists(path): return out
    for i, e in enumerate(json.load(open(path))):
        f = os.path.join(AIDIR, f'ai_{i:02d}.png')
        if os.path.exists(f): out.append((e['match'], '../ai/' + os.path.basename(f)))
    if os.path.exists(os.path.join(AIDIR, 'test_bakery.png')):
        out.append(('In the bakeries of Pompeii', '../ai/test_bakery.png'))
    return out
AI = load_ai()

def for_sentence(text):
    """-> ('file', name) | ('themes', [..]) | None ; plus shake flag"""
    shake = bool(SHAKE.search(text))
    for m, f in AI:
        if m in text: return ('file', f), shake
    for m, th in OVERRIDES.items():
        if m in text: return ('themes', th), shake
    for rx, th in CRX:
        if rx.search(text): return ('themes', th), shake
    return None, shake
