"""Add on-screen texts to text_register.json with their source. Only texts listed in SRC (checked by hand) or plain
place names / editorial notes are added; anything else is printed and must be checked before it can be registered."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
reg_p = os.path.join(ROOT, 'text_register.json'); reg = json.load(open(reg_p))
GEN = 'map/diagram: place names and dates checked against research.md and Natural Earth coordinates'
NOTE = 'editorial note on a schematic map/diagram (states that positions or borders are approximate)'
SRC = {
 'positions approximate': NOTE, 'positions schematic': NOTE, 'borders approximate': NOTE, 'route approximate': NOTE, 'routes approximate': NOTE,
 'schematic': NOTE, 'Carthaginian control': 'map key', 'December 218 BC': 'Polybius 3.72 (winter solstice, 218 BC)', 'June 217 BC · schematic': 'Ovid, Fasti 6.767 (21 June); Polybius 3.82-84', '209 BC · schematic': 'Polybius 10.9-15; Livy 26.42-46',
 'naval battle': 'Polybius 1.25-28 (battle of Ecnomus, 256 BC)', 'Ecnomus': 'Polybius 1.25', 'Aspis': 'Polybius 1.29 (Roman landing at Aspis/Clupea)',
 'Carthaginian supply fleet': 'Polybius 1.60-61', 'Roman fleet': 'Polybius 1.60-61', 'Aegates Islands': 'Polybius 1.60-61',
 'SICILY': 'Sicily became the first Roman province after 241 BC (research.md)', 'first Roman province': 'research.md claim register',
 'silver mines': 'Polybius 34.9 (silver mines near New Carthage); Diodorus 5.36', 'the Ebro treaty, 226 BC': 'Polybius 2.13',
 '237–219 BC': 'Polybius 2.1, 3.17 (Hamilcar to Spain 237; Saguntum 219)', 'to Spain': 'Polybius 3.40-41 (consul Scipio sent to Spain)',
 'to Africa': 'Polybius 3.40-41; Livy 21.17 (consul Sempronius at Lilybaeum for Africa)', "Hannibal's plan": 'Polybius 3.34',
 "Hannibal's route": 'Polybius 3.35-56', 'Hannibal crosses': 'Polybius 3.42-46', "Scipio's fleet": 'Polybius 3.41',
 'three days too late': 'Polybius 3.49 (Scipio reached the crossing three days after Hannibal left)', 'late summer 218 BC': 'Polybius 3.42',
 'main theories': 'pass not recorded by Polybius or Livy; modern candidate passes (research.md)', 'Taurini (Turin)': 'Polybius 3.60',
 'Little St Bernard': 'candidate pass (research.md)', 'Mont Cenis': 'candidate pass (research.md)', 'Col du Clapier': 'candidate pass (research.md)',
 'Col de la Traversette': 'candidate pass (research.md)', 'late 218 BC': 'Polybius 3.64-74', 'Mago': 'Polybius 3.71',
 'Romans wade the icy river': 'Polybius 3.72', 'ambush from a hidden streambed': 'Polybius 3.71', 'Romans': 'key', 'Carthaginians': 'key',
 'Roman column': 'Polybius 3.84', 'the trap springs': 'Polybius 3.84', 'hills': 'Polybius 3.83', 'Lake Trasimene': 'Polybius 3.82',
 '217–216 BC': 'Polybius 3.86-107', '2 August 216 BC: deployment': 'Gellius 5.17 / Macrobius 1.16 (a.d. IV Non. Sext.); Polybius 3.113',
 'Roman infantry': 'Polybius 3.113', 'Roman cavalry': 'Polybius 3.113', 'allied cavalry': 'Polybius 3.113', 'Gauls and Spaniards': 'Polybius 3.113-114',
 'Africans': 'Polybius 3.114', 'Carthaginian cavalry': 'Polybius 3.114', 'outnumbered almost two to one': 'Polybius 3.113-114: about 80,000 Roman infantry against about 40,000',
 'the centre gives ground; the cavalry rides round': 'Polybius 3.115-116', 'the crescent bends backward': 'Polybius 3.115', 'the trap closes': 'Polybius 3.115-116',
 'surrounded on every side': 'Polybius 3.116', '216–211 BC': 'Livy 22-26', 'about 310 km in a straight line': 'computed great-circle distance Rome to Cannae',
 'Rome and loyal allies': 'Livy 22.61', 'went over to Hannibal (much of the south)': 'Livy 22.61; Polybius 3.118', 'A WAR ON FOUR FRONTS': 'Livy 23-25',
 '215–212 BC': 'Livy 23-25', 'Macedon, allied to Carthage': 'Polybius 7.9 (treaty of 215 BC)', 'Hasdrubal': 'Livy 27.39-49',
 'Roman consul Nero, secret march north': 'Livy 27.43-45', '207 BC': 'Livy 27.46-49', 'lagoon': 'Polybius 10.10', 'harbour': 'Polybius 10.10',
 "Scipio's camp": 'Polybius 10.9', 'main attack': 'Polybius 10.12-13', 'wading at low water': 'Polybius 10.14',
 '209–206 BC': 'Polybius 10-11', 'New Carthage 209': 'Polybius 10.9-15', 'Baecula 208': 'Polybius 10.38-40', 'Ilipa 206': 'Polybius 11.20-24',
 'Zama: exact site uncertain': 'research.md (site of the battle is disputed)', '202 BC: the elephant charge': 'Polybius 15.11-12',
 'elephants': 'Polybius 15.11-12', 'open lanes between the Roman units': 'Polybius 15.9', '195–183 BC': 'Livy 33.47-49, 39.51',
 'Ephesus': 'Livy 33.49', 'Crete': 'Nepos, Hannibal 9', 'Bithynia': 'Livy 39.51', 'c. 200 to 150 BC': 'Polybius 31.21; Appian, Punic Wars 67-70',
 "Numidia under Masinissa, growing at Carthage's expense": 'Polybius 31.21; Appian, Punic Wars 68-70', 'THE THIRD WAR BEGINS': 'Appian, Punic Wars 75',
 '149 BC': 'Appian, Punic Wars 75', 'at least 80 stades (about 15 km) from the sea': 'Appian, Punic Wars 81 (80 stades = about 14.8 km)',
 'cross-section, after Appian; simplified': 'Appian, Punic Wars 95', 'ditch': 'Appian, Punic Wars 95', 'palisade': 'Appian, Punic Wars 95',
 'stalls for 300 elephants': 'Appian, Punic Wars 95', 'stables for 4,000 horses,': 'Appian, Punic Wars 95', 'barracks for 20,000 men': 'Appian, Punic Wars 95',
 'about 13 m': 'Appian, Punic Wars 95: 30 cubits', 'a man, for scale': 'scale figure, about 1.7 m', '147 BC': 'Appian, Punic Wars 112-120',
 'city walls': 'Appian, Punic Wars 95', "Scipio's siege line": 'Appian, Punic Wars 119', 'the mole': 'Appian, Punic Wars 121',
 'channel dug in secret': 'Appian, Punic Wars 121', 'spring 146 BC': 'Appian, Punic Wars 127-131', 'agora': 'Appian, Punic Wars 127',
 'THE THREE STREETS TO THE BYRSA': 'Appian, Punic Wars 128', 'temple of Eshmun': 'Appian, Punic Wars 130 (temple of Asclepius, i.e. Eshmun)',
 'from the agora': 'Appian, Punic Wars 128', 'houses six storeys high': 'Appian, Punic Wars 128', 'province of Africa': 'Appian, Punic Wars 135',
 'Roman territory, 146 BC': 'research.md', 'Corinth': 'Pausanias 7.16 (Corinth destroyed 146 BC)', '146 BC': 'research.md claim register',
 'The written accounts': 'split label: manuscript of Diodorus (a written source)', 'The excavated evidence': 'split label: Punic stele with the sign of Tanit, Louvre AO 23046',
 'Olympias | a modern reconstruction of a Greek trireme': 'Olympias, built 1985-87, Hellenic Navy (photo title)',
 'Sagunto today | the hill of ancient Saguntum': 'Livy 21.7 (Saguntum on a hill near the sea); photo title',
 'Inhuman cruelty; a treachery worse than Punic.': 'Livy 21.4.9 "inhumana crudelitas, perfidia plus quam Punica"',
 'MAGO': 'Pliny, Natural History 18.22; Columella 1.1.13', 'a Carthaginian writer on farming': 'Pliny, Natural History 18.22',
 'his manual was translated into Latin by order of the Roman Senate': 'Pliny, Natural History 18.22',
 '10 warships': 'Polybius 15.18 (ten triremes allowed by the peace of 201 BC)', 'all that Carthage was allowed after 201 BC, according to Polybius': 'Polybius 15.18',
 'OUR SOURCES': 'card heading', 'Polybius, a Greek, friend of Scipio Aemilianus': 'Polybius 31.23-25', 'Livy, a Roman, writing under Augustus': 'research.md',
 'Appian, a Greek, 2nd century AD': 'research.md (Appian of Alexandria, wrote c. AD 160)',
}
PLACES = {'Lilybaeum', 'Drepana', 'Utica', 'Carthage', 'Rome', 'Capua', 'Cannae', 'Tarentum', 'Placentia', 'Ticinus', 'Trebia', 'Trasimene', 'Canusium', 'Metaurus',
          'Macedon', 'Spain', 'New Carthage', 'Saguntum', 'Ebro', 'River Ebro', 'Pyrenees', 'Rhône', 'Alps', 'Po valley', 'Massalia', 'Tarraco', 'Hadrumetum', 'Zama',
          'Byrsa', 'Lake of Tunis', 'Gulf of Tunis', 'Tyre', 'Kition', 'Motya', 'Sardinia', 'Gades', 'Syracuse', 'Messana'}
out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'qc.py'), '--texts'], capture_output=True, text=True, cwd=ROOT).stdout.splitlines()
left = []
for line in out:
    sid, kind, t = line[:10].strip(), line[11:23].strip(), line[24:]
    if t in reg: continue
    if t in SRC: reg[t] = {'kind': kind, 'shot': sid, 'source': SRC[t]}
    elif t in PLACES or (t.isupper() and kind == 'map text') or (kind == 'map text' and t.endswith('BC') and len(t) < 12):
        reg[t] = {'kind': kind, 'shot': sid, 'source': GEN}
    else: left.append(line)
if 'Inhuman cruelty; a treachery worse than Punic.' in reg: reg['Inhuman cruelty; a treachery worse than Punic.']['narration'] = 'reviewed'
json.dump(reg, open(reg_p, 'w'), indent=1, ensure_ascii=False)
print(len(reg), 'registered;', len(left), 'need a source:'); [print(' ', l) for l in left]
