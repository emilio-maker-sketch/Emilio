"""Insert a visual beat before every sentence that lacked one (one-off patch of script.md)."""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, 'script.md')
B = {
 "A queen who wanted her son": ['@quote "SUSPECTS: A QUEEN, HER SON, THE PALACE STAFF" hl="A QUEEN"'],
 "A plot that used messengers": ['@quote "MESSENGERS - REBELS - MAGIC" hl="MAGIC" on=magic'],
 "This is Ancient World Files.": ['@push king'],
 "Our story begins around the year 1186": ['@map thebes as=tm'],
 "He built temples, gave enormous gifts": ['@card met549298 as=inlay w=380', '@tag inlay "FAIENCE INLAY, REIGN OF RAMESSES III"'],
 "The eastern Mediterranean world that Egypt": ['@quote "THE BRONZE AGE WORLD IS COLLAPSING" hl="COLLAPSING" on=falling'],
 "In the twenty ninth year of his reign": ['@circle tm at=deirmed on=happened', '@tag tm "DEIR EL-MEDINA: THE TOMB BUILDERS\' VILLAGE" at=deirmed'],
 "They put down their tools": ['@push strike'],
 "The great pharaoh's government could no longer": ['@circle strike on=feed'],
 "By now, Ramesses the Third was an old man.": ['@push r3'],
 "He had ruled for three decades.": ['@counter "30+" "YEARS ON THE THRONE"'],
 "The heir he eventually chose": ['@card met565104 as=sc4 w=300', '@tag sc4 "SCARAB OF RAMESSES IV"'],
 "And the question of who would succeed": ['@quote "WHO WILL BE THE NEXT KING?" hl="NEXT KING"'],
 "These were the people closest to the king": ['@card met544867 as=lyre w=360', '@tag lyre "JAR: WOMAN PLAYING A LYRE, c. 1400 BCE"'],
 "And some of them had sons.": ['@quote "SONS = RIVAL HEIRS" hl="RIVAL HEIRS" on=sons'],
 "We do not know exactly why.": ['@push tiye'],
 "Perhaps it was ambition.": ['@quote "MOTIVE? AMBITION" hl="AMBITION" on=ambition as=m1', '@string tiye m1'],
 "Perhaps it was fear, because": ['@quote "MOTIVE? FEAR OF LOSING EVERYTHING" hl="FEAR" on=fear as=m2', '@string tiye m2'],
 "The pharaoh was not just a ruler.": ['@card met549492 as=pyl w=360', '@tag pyl "STELA OF RAMESSES II"'],
 "He was the living guardian of maat": ['@circle maat on=maat'],
 "To kill the king was not simply murder.": ['@push maat'],
 "It was an attack on the order of the world": ['@quote "REGICIDE = ISFET (CHAOS)" hl="CHAOS" on=order'],
 "It lists the accused, one by one": ['@quote "\'... BROUGHT IN BECAUSE OF THE GREAT CRIMES ...\'" hl="GREAT CRIMES" on=accused'],
 "So they used messengers.": ['@circle wives on=messengers'],
 "The records name six wives": ['@counter "6" "WIVES OF THE GATEKEEPERS" on=six'],
 "It was meant to be a coup": ['@card met544921 as=sold w=520', '@tag sold "SOLDIERS (RELIEF, c. 1340 BCE)"'],
 "It was a weapon, and the court treated": ['@circle wax on=weapon'],
 "The Egyptian state itself used magic": ['@push exec'],
 "For centuries, priests had made figures": ['@card met556841 as=exec2 w=340', '@tag exec2 "FIGURINE OF A FOREIGNER, c. 1900 BCE"'],
 "Many of the names of the accused": ['@push names'],
 "The scribes changed them into insults.": ['@quote "TRUE NAMES ERASED" hl="ERASED" on=insults'],
 "Mesedsure means Ra hates him.": ['@tag mesed "MESEDSURE = \'RA HATES HIM\'"'],
 "Binemwese means evil in Thebes.": ['@tag bin "BINEMWESE = \'EVIL IN THEBES\'"'],
 "Sometime in the thirty second year": ['@map thebes as=tm2'],
 "But this is only a reasonable guess.": ['@circle tm2 at=medinet', '@tag tm2 "MEDINET HABU?" at=medinet'],
 "But we know the result.": ['@quote "THE RESULT:" hl="RESULT"'],
 "The uprising never happened.": ['@stamp letter "FAILED" on=never'],
 "The crown prince, Ramesses the Fourth, took": ['@push heir2'],
 "The papyrus is written as if the dead king": ['@card met554341 as=pal w=380', '@tag pal "SCRIBE\'S PALETTE, c. 1550-1300 BCE"'],
 "They were senior servants of the crown": ['@card met549229 as=nedjem w=360', '@tag nedjem "BLOCK STATUE OF NEDJEM, REIGN OF RAMESSES III"'],
 "The first and largest group were brought": ['@circle sections on=first'],
 "Others were allowed to die by their own hand": ['@push sections'],
 "So were the overseers, the scribes": ['@stamp overseer "CONDEMNED" on=overseers'],
 "Others, of higher rank, were allowed": ['@quote "HIGH RANK: \'TOOK THEIR OWN LIVES\'" hl="OWN LIVES"'],
 "Strangely, the records never tell us": ['@stamp tiye "UNKNOWN" on=never'],
 "Some of the judges were caught partying": ['@card met557733 as=mus w=520', '@tag mus "MUSICIANS (RELIEF, c. 1390 BCE)"'],
 "Their punishment, according to the papyrus": ['@quote "PUNISHMENT: NOSES AND EARS CUT OFF" hl="CUT OFF" on=noses'],
 "One of them took his own life rather": ['@circle judges on=own'],
 "Did the conspirators actually kill the king?": ['@circle q on=kill'],
 "The trial records are strangely silent": ['@quote "TRIAL RECORDS: NO CAUSE OF DEATH" hl="NO CAUSE" on=silent'],
 "Some scholars believed Ramesses survived": ['@quote "THEORY: HE SURVIVED AND DIED LATER" hl="SURVIVED" on=survived'],
 "In 1881, Egyptian authorities learned": ['@map thebes as=tm3', '@circle tm3 at=bahari on=secret'],
 "The museum official": ['@push db320'],
 "In just a few days, the mummies were carried": ['@tag tm3 "BY BOAT TO CAIRO" at=nile'],
 "Among them was Ramesses the Third.": ['@string db320 king'],
 "In 1886, the head of the antiquities service": ['@quote "1886: UNWRAPPED IN PUBLIC" hl="UNWRAPPED" on=unwrapped'],
 "That decision kept the king's secret": ['@counter "126" "YEARS STILL HIDDEN" on=hundred'],
 "His mummy had not been properly prepared.": ['@push unk'],
 "He had been wrapped in a goatskin": ['@quote "GOATSKIN = RITUALLY IMPURE" hl="IMPURE" on=impure'],
 "For more than a century, no one knew who": ['@circle unk on=knew'],
 "Theories piled up.": ['@quote "THEORIES:" hl="THEORIES" as=th', '@string unk th'],
 "Some suggested he had been poisoned": ['@quote "POISONED? BURIED ALIVE? A FOREIGN PRINCE?" hl="BURIED ALIVE" on=alive'],
 "In 2012, a team led by Egyptologist": ['@quote "HAWASS & SALEEM, BMJ, 2012" hl="2012"'],
 "Death would have been almost immediate.": ['@push neckd'],
 "One of the king's big toes had been cut off": ['@push footd'],
 "The plot to kill the king had succeeded.": ['@push r3b'],
 "DNA analysis showed that the young man": ['@circle dna on=DNA'],
 "His age, his dishonorable burial": ['@push unk'],
 "We cannot be completely certain.": ['@quote "IDENTIFICATION: PROBABLE, NOT PROVEN" hl="NOT PROVEN"'],
 "But it is the best match we have.": ['@push pent'],
 "The king was dead, but the conspirators never": ['@quote "KING: DEAD - CONSPIRATORS: CONDEMNED" hl="CONDEMNED"'],
 "He asked for a long life and a long reign": ['@counter "67" "YEARS - RAMESSES II\'S REIGN" on=sixty'],
 "Travelers later named it the Tomb of the Harpers": ['@card met544242 as=harp w=360', '@tag harp "BOW HARP, c. 1900 BCE"'],
 "The king himself was taken from his tomb": ['@push kv11'],
 "Under Ramesses the Ninth, officials investigated": ['@card met557208 as=coffin w=320', '@tag coffin "COFFIN, c. 1200-945 BCE"'],
 "The tombs in the Valley of the Kings would be looted": ['@string robbery cache'],
 "A king murdered by his own household.": ['@push r3b'],
 "A trial corrupted by its own judges.": ['@push judges'],
 "And a cold case solved by a scanner": ['@push neckd'],
}
lines = open(P, encoding='utf-8').read().split('\n')
out, used = [], set()
for ln in lines:
    hit = [k for k in B if ln.startswith(k)]
    if hit:
        out += B[hit[0]]; used.add(hit[0])
    out.append(ln)
miss = [k for k in B if k not in used]
assert not miss, miss
s = '\n'.join(out)
s = s.replace('@zone open\n', '@open "CASE FILE: RAMESSES III|THEBES, EGYPT - c. 1155 BCE|A KING IS MURDERED.|THE CASE WILL TAKE 3,000 YEARS TO SOLVE."\n@zone open\n', 1)
open(P, 'w', encoding='utf-8').write(s)
print('inserted beats for', len(used), 'sentences')
