"""Curated image library: themes (hand-picked from contact sheets, by global index in build/img/index.json)
and the mapping from each script [v:] query to themes. Writes build/img/library.json and build/img/credits.json.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build', 'img')

def R(*a):
    out = []
    for x in a:
        out += list(range(x[0], x[1] + 1)) if isinstance(x, tuple) else [x]
    return out

THEMES = {
    'ERUPT':   R(33, 51, 65),
    'VESUV':   R(38, 49, 59, 60, 67),
    'BAY':     R(56, 57, 64, 70, 72, 145, 146, 147, 148, 149, 152, 153),
    'NAPLES':  R(132, 135, 140, 141, 142, 151),
    'RUINS':   R(0, 2, 3, 4, 5, 6, 9, 11, 12, 13, 14, 22, 24),
    'EXCAV':   R(8, 15, 18, 91, 13, 22, 24),
    'CASTS':   R(1),
    'FRESCO':  R((75, 88), 163, (165, 167), 174, 209, 213, 221, 31),
    'FRAG':    R(155, 157, (190, 208), 211, 214),
    'MOSAIC':  R(89, 228, 233),
    'HERCART': R(69, (92, 103)),
    'PORTRAIT': R((266, 272), (274, 276), (278, 287), 289, (291, 295), (322, 327), 332, 333, 334, 336, 337, 338, 342, 345, 348, 350, 352, 355, 357, 358, 360, 362),
    'GODS':    R(328, 329, 331, 335, 343, 346, 361),
    'LARES':   R(364, 367, 370, 372, 373, 376, 377, 378, 379, 381, 383, 384, 386, 389, 390, 392, 396, 398, 399, 400, 401, 402, 403, 404, 405, 411, 412, 416, 417, 418, 419, 420),
    'OBJECTS': R(16, 17, 19, 20, 21, 23, 25, 28, 29, 32, 37, 40, 42, 46, 68, 90, 106, 227, (229, 232), 234, 237, 239, 243,
                 (421, 427), 429, 430, 432, 433, 434, 436, 439, 440, 441, 442, 443, 446, 447, 448, 449, 452, 453, 454, 457, 458, 459,
                 460, 461, 462, 464, 466, 467, 468, 469, 470, 471, 474, 477, 478, 480, 481, 482, 483, 486, 489, 490, 491, 494, 502),
    'JEWEL':   R(26, 48, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 522, 523, 524, 528, 529, 532, 533, 535, 536, 539, 540, 543, 547, 548, 549, 550, 553),
    'COINS':   R(476, 479, 487, 492, 499, 500, 501, 503, 504, 505, 506, 507, 508),
    'LAMPS':   R(555, 556, 557, 559, 562, 563, 564, 565, 568, 571, 582, 585, 586, 588, 589, 593),
    'AMPHORA': R(19, 608, 609, 613, 616, 617, 619, 621, 622),
    'GARDEN':  R(45, 57, 88, 221),
    'TITUS':   R(67, 159),
    'SENECA':  R(309),
    'SCHOLAR': R(310, 331, 309),
    'PANIC':   R(178),
}
WM = {'BRULLOV': 'wm_ec39e0c79c85.jpg', 'ISSUS': 'wm_ae783ce9bc77.jpg', 'VESFROMPOMPEII': 'wm_c010b2d7ffd3.jpg', 'PLINY': 'wm_496bf4dc7cf1.jpg'}
FX = {'ASHFX': ['fx:ash'] * 6, 'PUMICEFX': ['fx:pumice'] * 6, 'FLOWFX': ['fx:flow'] * 6, 'DARKFX': ['fx:dark'] * 4}

Q = {
    'Alexander Mosaic': ['ISSUS', 'MOSAIC'], 'Bay of Naples': ['BAY'], 'Brullov Last Day of Pompeii': ['BRULLOV', 'ERUPT'],
    'Charles III of Spain Naples': ['NAPLES', 'EXCAV'], 'Emperor Titus bust': ['TITUS', 'COINS'], 'Garden of the Fugitives Pompeii': ['CASTS', 'DARKFX', 'RUINS'],
    'Giuseppe Fiorelli': ['EXCAV', 'CASTS'], 'Herculaneum': ['HERCART', 'FRESCO', 'EXCAV'], 'Herculaneum papyrus scroll': ['SCHOLAR', 'HERCART', 'EXCAV'],
    'Herculaneum ruins': ['HERCART', 'EXCAV', 'RUINS'], 'Herculaneum skeletons boat sheds': ['DARKFX', 'JEWEL', 'LAMPS', 'BAY'],
    'Joseph Wright of Derby Vesuvius': ['ERUPT', 'VESUV'], 'Karl Weber Herculaneum plan': ['EXCAV'], 'Misenum Roman fleet': ['SHIPS', 'BAY'],
    'Mount St Helens eruption 1980': ['ERUPT', 'ASHFX'], 'Mount Vesuvius from Pompeii': ['VESFROMPOMPEII', 'VESUV'], 'Naples Vesuvius panorama': ['BAY', 'VESUV', 'NAPLES'],
    'Naples skyline Vesuvius night': ['BAY', 'NAPLES'], 'Pierre-Jacques Volaire': ['ERUPT'], 'Pinatubo eruption 1991 ash column': ['ERUPT', 'ASHFX'],
    'Plinian eruption column': ['ERUPT', 'ASHFX', 'PINE'], 'Pliny the Elder': ['PLINY', 'SCHOLAR', 'PORTRAIT'], 'Pliny the Younger': ['PORTRAIT', 'SCHOLAR', 'LAMPS'],
    'Pliny the Younger and his mother at Misenum': ['BAY', 'PORTRAIT', 'ASHFX'], 'Pompeii Basilica': ['RUINS'], 'Pompeii Dancing Faun statue': ['LARES', 'GODS'],
    'Pompeii House of the Faun': ['RUINS', 'MOSAIC'], 'Pompeii Large Theatre': ['RUINS'], 'Pompeii Porta Marina': ['RUINS', 'EXCAV'],
    'Pompeii Stabian Baths': ['RUINS', 'OBJECTS'], 'Pompeii Temple of Apollo': ['RUINS', 'GODS'], 'Pompeii amphitheatre': ['RUINS', 'LARES'],
    'Pompeii atrium impluvium': ['RUINS', 'FRESCO'], 'Pompeii bakery oven': ['AMPHORA', 'OBJECTS', 'RUINS'], 'Pompeii body cast': ['CASTS', 'DARKFX', 'MOURN'],
    'Pompeii carbonized food': ['OBJECTS', 'AMPHORA'], 'Pompeii cast dog': ['CASTS'], 'Pompeii earthquake relief Lararium Caecilius Iucundus': ['LARES', 'GODS', 'RUINS'],
    'Pompeii election inscription': ['INSCRIPT', 'FRAG', 'RUINS'], 'Pompeii engraving 18th century': ['EXCAV', 'RUINS'], 'Pompeii excavation 1860s': ['EXCAV', 'CASTS'],
    'Pompeii excavation 19th century photograph': ['EXCAV', 'RUINS'], 'Pompeii forum Vesuvius': ['RUINS', 'VESFROMPOMPEII'], 'Pompeii fresco': ['FRESCO'],
    'Pompeii fresco Sappho': ['FRESCO', 'PORTRAIT'], 'Pompeii fresco portrait Terentius Neo': ['FRESCO', 'PORTRAIT'], 'Pompeii graffiti': ['FRAG', 'RUINS'],
    'Pompeii inscription': ['INSCRIPT', 'FRAG', 'COINS'], 'Pompeii jewellery gold': ['JEWEL'], 'Pompeii mosaic': ['MOSAIC', 'ISSUS'], 'Pompeii mosaic fish': ['MOSAIC', 'FRAG'],
    'Pompeii peristyle garden': ['GARDEN', 'FRESCO'], 'Pompeii plaster casts victims': ['CASTS', 'DARKFX', 'MOURN'], 'Pompeii pumice lapilli': ['PUMICEFX'],
    'Pompeii ruins panorama': ['RUINS'], 'Pompeii street': ['RUINS'], 'Pompeii surgical instruments': ['OBJECTS'], 'Pompeii thermopolium': ['AMPHORA', 'OBJECTS'],
    'Pompeii walls tower': ['RUINS', 'EXCAV'], 'Pompeii watercolour': ['RUINS', 'FRESCO'], 'Pumice': ['PUMICEFX'], 'Pyroclastic flow': ['FLOWFX'],
    'Roman amphora': ['AMPHORA'], 'Roman bread carbonized Pompeii': ['OBJECTS', 'AMPHORA'], 'Roman quinquereme': ['SHIPS', 'BAY'], 'Roman trireme relief': ['SHIPS', 'COINS'],
    'Roman wine amphorae Pompeii': ['AMPHORA'], 'Seneca bust': ['SENECA', 'SCHOLAR'], 'Stabiae villa fresco': ['FRESCO', 'GARDEN'], 'Sulla bust': ['PORTRAIT', 'COINS'],
    'Tacitus': ['SCHOLAR', 'PORTRAIT'], 'Vesuvius 1631 eruption': ['ERUPT'], 'Vesuvius 1944 eruption': ['ERUPT', 'ASHFX'], 'Vesuvius aerial': ['VESUV', 'BAY'],
    'Vesuvius crater': ['VESUV', 'ERUPT'], 'Vesuvius eruption 1779 painting': ['ERUPT'], 'Vesuvius eruption painting': ['ERUPT', 'BRULLOV'],
    "Via dell'Abbondanza Pompeii": ['RUINS'], 'Villa San Marco Stabiae': ['FRESCO', 'GARDEN'], 'Villa of the Mysteries fresco': ['FRESCO'],
    'Villa of the Papyri': ['HERCART', 'SCHOLAR', 'GARDEN'], 'Volaire Vesuvius': ['ERUPT'], 'Volcanic ash cloud': ['ASHFX', 'ERUPT'],
}

def main(extra=None):
    ix = json.load(open(os.path.join(B, 'index.json')))
    themes = {k: [ix[i]['file'] for i in v if i < len(ix)] for k, v in THEMES.items()}
    if extra:
        for k, v in extra.items(): themes.setdefault(k, []).extend(ix[i]['file'] for i in v if i < len(ix))
    for k, f in WM.items(): themes[k] = [f]
    themes.update(FX)
    meta = {e['file']: {'title': e['title'], 'artist': e['artist'], 'source': e['source'], 'license': e['license'], 'page': e['page']} for e in ix}
    for f, m in json.load(open(os.path.join(B, 'wm_direct.json'))).items():
        meta[f] = {'title': m['title'], 'artist': m['credit'], 'source': 'Wikimedia Commons', 'license': 'see page', 'page': m['page']}
    missing = [t for q, ts in Q.items() for t in ts if t not in themes]
    assert not missing, missing
    json.dump({'queries': Q, 'themes': themes, 'meta': meta}, open(os.path.join(B, 'library.json'), 'w'), indent=1, ensure_ascii=False)
    print({k: len(v) for k, v in themes.items()})

if __name__ == '__main__':
    extra = json.load(open(os.path.join(B, 'extra_themes.json'))) if os.path.exists(os.path.join(B, 'extra_themes.json')) else None
    main(extra)
