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
}
RULES = [  # (regex, themes) — first match wins, checked in order
    (r'gladiat|amphitheatre|spectators|\bbrawl\b|\bgames\b', ['AIGLAD']),
    (r'\bsiege\b|catapult|\bwar\b|veterans|rebellion|Sulla', ['AISIEGE', 'PORTRAIT']),
    (r'earthquakes?|tremors?|\btremble|collapsed|\bdamage\b|laid low|rebuil|unsafe', ['AIQUAKE', 'RUINS']),
    (r'\broofs?\b|ceilings?|roof beams', ['AIROOF', 'PUMICEFX']),
    (r'\bdoors?\b|doorways?|\bgates?\b|city walls', ['GATE', 'AIFLEE', 'STREET']),
    (r'\bstreets?\b|paving|pavements?|stepping stones|\bruts\b|\broads?\b', ['STREET', 'AISTREET', 'RUINS']),
    (r'commerce|merchants|business|basilica|\bshops?\b|bakeries|\bbars\b|workshops', ['AIBAR', 'STREET', 'FOOD']),
    (r'mosaics?|House of the Faun', ['ISSUS', 'MOSAIC']),
    (r'\btemples?\b|\bforum\b|Jupiter|Apollo|Isis', ['TEMPLE', 'RUINS']),
    (r'\bbaths?\b|bathing', ['BATHS']),
    (r'\bwine\b|vineyards?|\bvines\b|grapes|amphora|\bjars?\b|fertile|plenty', ['AMPHORA']),
    (r'fish sauce|garum|lentils|\bfood\b|\bmeal\b|\bbread\b|loaves|\bate\b|pomegranates|chestnuts|walnuts|\bdined\b|\blunch\b', ['FOOD', 'AMPHORA']),
    (r'paint(ed|ing|ings)?\b|frescoe?s?|colours|coloured|\brich\b|wealthy|grand homes|in style', ['FRESCO']),
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
    (r'\bletters?\b|copied|wrote|\bwrote\b|account of', ['AIWRITE', 'SCHOLAR']),
    (r'Strabo|Tacitus|historian|philosopher|scholar|encyclopaedia|Natural History|naturalist|curiosity', ['SCHOLAR']),
    (r'\bships?\b|\bfleet\b|\bboats?\b|\bsail(ed|ing)?\b|quadrireme|warships|helmsman|\bnavy\b|Liburnian|steer', ['SHIPS', 'AISHIP', 'BAY']),
    (r'\bmother\b|\bwoman\b|\bwomen\b|\bsister\b|\bwife\b', ['AIYOUNG', 'WOMAN']),
    (r'\bnephew\b|seventeen|young man|\byouth\b|Pliny the Younger', ['AIYOUNG', 'YOUTH']),
    (r'Pliny the Elder|\badmiral\b|\buncle\b|\bPliny\b|Plinius', ['PLINY', 'AIPLINY']),
    (r'pumice|stones were falling|\bhail\b|rattling|falling stones', ['PUMICEFX']),
    (r'\bsurges?\b|\bcurrents?\b|avalanche|scalding|\bheat\b|burning|\bflames?\b|\bfire\b|\bburned\b', ['FLOWFX', 'AIERUPT', 'ERUPT']),
    (r'\bpine\b|branches|trunk', ['PINE', 'ERUPT']),
    (r'\bcloud\b|\bcolumn\b|eruptions?|\berupt|plume|blast|stratosphere|magma', ['ERUPT', 'AIERUPT', 'ASHFX']),
    (r'\bash\b|snow|buried', ['AIASH', 'ASHFX']),
    (r'darkness|\bdark\b|\bnight\b|blacker', ['DARKFX', 'AIDARK', 'LAMPS']),
    (r'\bfle(e|d|eing)\b|escape|crowd|streamed', ['AIFLEE']),
    (r'\bbodies\b|\bbody\b|\bdead\b|\bdied\b|\bdeath\b|victims|skeletons?|killed|\bcasts?\b|plaster|vanished', ['CASTS', 'MOURN', 'DARKFX']),
    (r'excavat|archaeolog|\bdig(ging)?\b|tunnel|uncover|excavators', ['EXCAV', 'AIEXCAV', 'RUINS']),
    (r'scrolls?|papyr|\blibrary\b|\bbooks?\b|\bread\b', ['AISCROLL', 'SCHOLAR', 'HERCART']),
    (r'Naples|metropolitan|residents|evacuation|populated', ['NAPLES', 'BAY']),
    (r'\bsea\b|\bshore(line)?\b|\bbeach\b|\bbay\b|coast|\bwaves\b|harbour|\bwater\b', ['BAY', 'AIBEACH']),
    (r'mountain|Vesuvius|volcano|summit|crater|\bslopes\b', ['VESUV', 'ERUPT']),
]
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
    for rx, th in CRX:
        if rx.search(text): return ('themes', th), shake
    return None, shake
