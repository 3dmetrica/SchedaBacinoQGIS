# Scheda del bacino idrografico in QGIS

Script PyQGIS che, partendo da DTM, poligono del bacino e reticolo idrografico, calcola i **parametri morfometrici** del bacino e il **tempo di corrivazione** con cinque formule, poi crea in un colpo solo un **layout A3 "Scheda bacino"** con mappa, tabelle, curva ipsometrica e profilo dell'asta principale.

È lo script usato nel video di **QGIS in Azione** "Dal DTM al tempo di corrivazione: la scheda del bacino in QGIS", terzo episodio della mini serie sull'analisi di bacino, realizzata con [Gter](https://www.gter.it/formazione).

Video: https://youtu.be/VAMr4Yz_yFc

![Esempio di scheda prodotta dallo script sul bacino del Rio Maggiore](esempio_tavola_bacino.png)

## Cosa ti serve

- QGIS 3 (scritto e provato con QGIS 3.44 LTR). NumPy e GDAL per Python sono già inclusi nell'installazione di QGIS
- Il **DTM** del bacino, come **file** leggibile da GDAL (per esempio GeoTIFF): lo script legge le celle direttamente dal file, quindi non funziona con un DTM da servizio web
- Il **poligono del bacino**, come esce dal primo episodio della mini serie
- Il **reticolo idrografico a linee**, ritagliato sul bacino, come esce dal secondo episodio
- Un DTM in un **sistema di riferimento proiettato in metri** (nel video EPSG:32632). Bacino e reticolo possono essere in un altro sistema: lo script li riproietta in quello del DTM

Se il reticolo ha già i campi `strahler` e `asta_princ`, calcolati con lo script dell'episodio 2 ([OrdiniStrahler](https://github.com/3dmetrica/OrdiniStrahler)), lo script li usa. Se non li ha, li calcola da solo.

## Come si usa

1. Carica nel progetto DTM, bacino e reticolo
2. Apri `tavola_bacino.py` e adatta le **impostazioni** in cima al file:

   | Impostazione | Cosa contiene |
   |---|---|
   | `DTM`, `BACINO`, `RETICOLO` | il nome dei tre layer, o una sua parte, senza distinzione tra maiuscole e minuscole |
   | `ASTA` | il layer dell'asta principale, se ce l'hai. Facoltativo: se non lo trova, l'asta viene presa dai tratti con `asta_princ = 1` o calcolata dallo script |
   | `TOLLERANZA_SIMPLIFY` | la tolleranza in metri per semplificare il limite del bacino (nel video 1,5 m, con DTM a 1 m) |
   | `TITOLO`, `SOTTOTITOLO`, `FONTE` | i testi della scheda. Sono impostati sul Rio Maggiore: cambiali per il tuo bacino |
   | `TITOLO_LAYOUT` | il nome del layout (predefinito "Scheda bacino") |
   | `ESPORTA_PDF` | il percorso del PDF da esportare, per esempio `r'C:\lavori\scheda_bacino.pdf'`. Vuoto: nessun export |

3. Nel menu Plugins apri la **Python Console**, poi l'editor (icona *Show Editor*), apri il file e lancialo con *Run Script*
4. Nella console compaiono i parametri calcolati; poi si apre il layout, pronto da rifinire o da esportare

Come trova i layer: prima cerca un layer con il nome identico, poi uno che contenga il testo indicato, e per il bacino e il reticolo considera solo i layer del tipo giusto (poligoni e linee). Se ne trova più di uno, sceglie quello che comincia con il testo cercato e ha il nome più corto, e scrive in console quale ha scelto: controllalo. Se non ne trova nessuno, si ferma e ti elenca i nomi dei layer presenti nel progetto.

Lo script **non modifica i tuoi layer**: crea copie in memoria nel gruppo "Tavola bacino". Se lo rilanci, gruppo e layout vengono sostituiti.

## Cosa calcola

**Forma**
- Area del bacino e perimetro, sia del poligono a scalini nato dal raster sia di quello semplificato con la tolleranza impostata
- Coefficiente di Gravelius: `Kc = 0,28 · P / √A`
- Rapporto di circolarità: `Rc = 4π · A / P²`

In console trovi Kc e Rc calcolati su entrambi i perimetri; nella scheda va il valore con il perimetro semplificato.

**Quote e pendenze**
- Quota minima, massima, media e mediana, dalle celle del DTM dentro il bacino
- Pendenza media in gradi e in percentuale, calcolata con il metodo di Horn come lo strumento Slope di QGIS. La media in percentuale è fatta sulle pendenze in percentuale cella per cella, non come tangente della media in gradi: la media delle percentuali non è la percentuale della media
- Integrale ipsometrico: `HI = (Hmedia − Hmin) / (Hmax − Hmin)`
- Curva ipsometrica: percentuale di area del bacino sopra ogni quota

**Reticolo e asta principale**
- Lunghezza del reticolo, densità di drenaggio, ordine di Strahler massimo. Lo sbocco è l'estremità libera del reticolo con la quota più bassa sul DTM
- Asta principale: lunghezza, quota della sezione di chiusura e della testata lette sul DTM, pendenza media (dislivello diviso lunghezza)
- Profilo longitudinale dell'asta, campionato sul DTM ogni 10 m

**Tempo di corrivazione** (in ore, e in minuti nella scheda; A in km², L lunghezza dell'asta in km, Hm quota media e H0 quota della sezione in m, i pendenza dell'asta in m/m)

| Formula | Espressione |
|---|---|
| Giandotti | `(4 · √A + 1,5 · L) / (0,8 · √(Hm − H0))` |
| Kirpich | `0,000325 · (1000 · L)^0,77 · i^(−0,385)` |
| Ventura | `0,1272 · √(A / i)` |
| Pezzoli | `0,055 · L / √i` |
| Pasini | `0,108 · (A · L)^(1/3) / √i` |

**Scheda A3 orizzontale**
- Mappa con rilievo ombreggiato e quote, bacino, reticolo colorato per ordine di Strahler, asta principale e sezione di chiusura. La scala è la più grande scala tonda con cui il bacino entra in un riquadro di 250 × 250 mm
- Legenda, barra di scala e freccia del nord
- Tabelle dei parametri e dei tempi di corrivazione
- Curva ipsometrica e profilo dell'asta principale
- In fondo: scala, sistema di riferimento, fonte, tolleranza e data

Sul bacino del Rio Maggiore (Riomaggiore, Cinque Terre), con il DTM LiDAR del Ministero dell'Ambiente a 1 m, la scheda riporta area 2,23 km², Kc 1,56, HI 0,51, asta 2,27 km e tempi di corrivazione da 14 a 39 minuti, gli stessi valori calcolati a mano nel video.

## Limiti

- **I tempi di corrivazione sono dimostrativi.** Quale formula usare è una scelta idrologica che spetta al tecnico, e cambia la portata che calcolerai dopo. La formula di Giandotti è tarata su bacini da circa 170 a 70.000 km²: su bacini di pochi km² è fuori dal suo campo di validità
- **Il risultato dipende dal reticolo che gli dai.** Il DTM non vede tombini e sottopassi: dove il torrente passa sotto un rilevato stradale, il reticolo calcolato devia lungo la strada e l'asta si allunga. Se conosci il territorio, correggi il reticolo prima di lanciare lo script
- **Il perimetro dipende dalla semplificazione.** Il poligono nato dal raster segue i gradini dei pixel e ha un perimetro più lungo del reale; con la tolleranza cambiano perimetro e indici di forma. Adatta la tolleranza alla risoluzione del tuo DTM
- **Pendenza:** le medie possono differire di qualche decimo da quelle che ottieni con Slope e le statistiche zonali, per la gestione dei bordi del raster
- **Reticolo:** deve essere connesso e ad albero, con le estremità dei tratti coincidenti nelle confluenze (lo script le confronta arrotondate al centimetro). Tratti staccati restano senza ordine; un reticolo con anelli non viene gestito. La lunghezza del reticolo e la densità di drenaggio contano tutti i tratti del layer
- **I grafici sono file temporanei.** Curva ipsometrica, profilo e freccia del nord vengono salvati come SVG in una cartella temporanea del sistema. Se riapri il progetto quando quella cartella è stata svuotata, nel layout spariscono: esporta subito il PDF (con `ESPORTA_PDF` o dal layout) oppure rilancia lo script

## Contatti

Paolo Corradeghini, 3DMetrica
- YouTube: canale di 3DMetrica
- LinkedIn: [linkedin.com/in/paolocorradeghini](https://www.linkedin.com/in/paolocorradeghini)
- Gruppo Telegram di QGIS in Azione: [t.me/+ZKm37iQHD083MTRk](https://t.me/+ZKm37iQHD083MTRk)
