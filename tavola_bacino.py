# Tavola del bacino: calcola i parametri e crea il layout in un colpo solo
# QGIS in Azione, mini serie sull'analisi di bacino, episodio 3 (QGIS 3.44 LTR)
#
# Uso: Plugins > Python Console > Show Editor, incolla lo script e lancialo.
# Servono nel progetto: il DTM, il poligono del bacino e il reticolo ritagliato
# sul bacino. Lo script non modifica i tuoi layer: crea copie in memoria nel
# gruppo "Tavola bacino" e un layout chiamato come TITOLO_LAYOUT.

# ---------------------------------------------------------------- impostazioni
DTM = 'DTM_terra'          # basta una parte del nome, maiuscole indifferenti
BACINO = 'Bacino'
RETICOLO = '2ha_bacino'
ASTA = 'asta_principale'   # se non c'e', l'asta viene presa da asta_princ = 1
                           # oppure calcolata dallo script
TOLLERANZA_SIMPLIFY = 1.5  # m, per il perimetro "vero"
TITOLO = 'Bacino del Rio Maggiore'
SOTTOTITOLO = "Sezione di chiusura all'imbocco del tratto tombinato, Riomaggiore (SP)"
FONTE = ('DTM LiDAR MASE ricampionato a 1 m. Reticolo da r.stream.extract, soglia 2 ha. '
         'QGIS in Azione, 3DMetrica e Gter')
TITOLO_LAYOUT = 'Scheda bacino'
ESPORTA_PDF = ''           # per esempio r'C:\lavori\scheda_bacino.pdf'; vuoto = nessun export
# -----------------------------------------------------------------------------

import math, os, tempfile, datetime
from collections import defaultdict
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions()
from qgis.PyQt.QtCore import QVariant, QPointF
from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.core import *
import sys
sys.setrecursionlimit(10000)

P = QgsProject.instance()
MM = Qgis.LayoutUnit.Millimeters if hasattr(Qgis, 'LayoutUnit') else QgsUnitTypes.LayoutMillimeters


def trova(parte, obbligatorio=True, tipo=None, geom=None):
    tutti = [l for l in P.mapLayers().values() if tipo is None or isinstance(l, tipo)]
    tutti = [l for l in tutti if not l.customProperty('tavola_bacino')]  # layer di una corsa precedente
    if geom is not None:
        tutti = [l for l in tutti if l.geometryType() == geom]
    trovati = ([l for l in tutti if l.name().lower() == parte.lower()]
               or [l for l in tutti if parte.lower() in l.name().lower()])
    if len(trovati) > 1:  # piu' candidati: quelli che iniziano con il nome cercato, poi il nome piu' corto
        inizio = [l for l in trovati if l.name().lower().startswith(parte.lower())] or trovati
        scelto = min(inizio, key=lambda l: ('sempl' in l.name().lower() and 'sempl' not in parte.lower(), len(l.name())))
        print("'%s': scelto '%s' tra %s" % (parte, scelto.name(), [l.name() for l in trovati]))
        return scelto
    if trovati:
        return trovati[0]
    if not obbligatorio:
        return None
    raise Exception("'%s': nessun layer trovato. Nomi nel progetto: %s"
                    % (parte, [l.name() for l in P.mapLayers().values()]))


def num(x, d=2):
    return ('{:,.%df}' % d).format(x).replace(',', ' ').replace('.', ',').replace(' ', '.')


dem = trova(DTM, tipo=QgsRasterLayer)
bac = trova(BACINO, tipo=QgsVectorLayer, geom=Qgis.GeometryType.Polygon if hasattr(Qgis, 'GeometryType') else QgsWkbTypes.PolygonGeometry)
ret = trova(RETICOLO, tipo=QgsVectorLayer, geom=Qgis.GeometryType.Line if hasattr(Qgis, 'GeometryType') else QgsWkbTypes.LineGeometry)
asta_lyr = trova(ASTA, obbligatorio=False, tipo=QgsVectorLayer, geom=Qgis.GeometryType.Line if hasattr(Qgis, 'GeometryType') else QgsWkbTypes.LineGeometry)
crs = dem.crs()
ctx = P.transformContext()


def in_crs_dem(layer):
    tr = QgsCoordinateTransform(layer.crs(), crs, ctx)
    out = []
    for f in layer.getFeatures():
        g = QgsGeometry(f.geometry())
        if layer.crs() != crs:
            g.transform(tr)
        out.append((f, g))
    return out


# ------------------------------------------------------------ bacino e forma
geom_bac = QgsGeometry.unaryUnion([g for f, g in in_crs_dem(bac)])
geom_semp = geom_bac.simplify(TOLLERANZA_SIMPLIFY)
A_km2 = geom_bac.area() / 1e6
P_km = geom_bac.length() / 1e3
Ps_km = geom_semp.length() / 1e3
Kc = 0.28 * P_km / math.sqrt(A_km2)
Kcs = 0.28 * Ps_km / math.sqrt(A_km2)
Rc = 4 * math.pi * A_km2 / P_km ** 2
Rcs = 4 * math.pi * A_km2 / Ps_km ** 2

# ------------------------------------------------- quote e pendenze (GDAL)
ds = gdal.Open(dem.dataProvider().dataSourceUri().split('|')[0])
gt = ds.GetGeoTransform()
band = ds.GetRasterBand(1)
nodata = band.GetNoDataValue()
bb = geom_bac.boundingBox()
c0 = max(int((bb.xMinimum() - gt[0]) / gt[1]) - 2, 0)
c1 = min(int((bb.xMaximum() - gt[0]) / gt[1]) + 3, ds.RasterXSize)
r0 = max(int((bb.yMaximum() - gt[3]) / gt[5]) - 2, 0)
r1 = min(int((bb.yMinimum() - gt[3]) / gt[5]) + 3, ds.RasterYSize)
z = band.ReadAsArray(c0, r0, c1 - c0, r1 - r0).astype('float64')
if nodata is not None:
    z[z == nodata] = np.nan
# maschera del bacino
mem = gdal.GetDriverByName('MEM').Create('', c1 - c0, r1 - r0, 1, gdal.GDT_Byte)
mem.SetGeoTransform((gt[0] + c0 * gt[1], gt[1], 0, gt[3] + r0 * gt[5], 0, gt[5]))
srs = osr.SpatialReference()
srs.ImportFromWkt(crs.toWkt())
mem.SetProjection(srs.ExportToWkt())
ods = ogr.GetDriverByName('Memory').CreateDataSource('m')
ol = ods.CreateLayer('b', srs, ogr.wkbMultiPolygon)
of = ogr.Feature(ol.GetLayerDefn())
of.SetGeometry(ogr.CreateGeometryFromWkt(geom_bac.asWkt()))
ol.CreateFeature(of)
gdal.RasterizeLayer(mem, [1], ol, burn_values=[1])
mask = (mem.GetRasterBand(1).ReadAsArray() == 1) & ~np.isnan(z)
zb = z[mask]
z_min, z_max, z_mean, z_med = zb.min(), zb.max(), zb.mean(), np.median(zb)
HI = (z_mean - z_min) / (z_max - z_min)
# pendenza con il metodo di Horn, come lo strumento Slope
dx, dy = abs(gt[1]), abs(gt[5])
zp = np.pad(z, 1, mode='edge')
a, b, c = zp[:-2, :-2], zp[:-2, 1:-1], zp[:-2, 2:]
d, f, g_ = zp[1:-1, :-2], zp[1:-1, 2:], zp[2:, :-2]
h, i_ = zp[2:, 1:-1], zp[2:, 2:]
gx = ((c + 2 * f + i_) - (a + 2 * d + g_)) / (8 * dx)
gy = ((g_ + 2 * h + i_) - (a + 2 * b + c)) / (8 * dy)
grad = np.hypot(gx, gy)
ok = mask & ~np.isnan(grad)
slope_deg = np.degrees(np.arctan(grad[ok])).mean()
slope_pct = (grad[ok] * 100).mean()
# curva ipsometrica: percentuale di area sopra ogni quota
zs = np.sort(zb)
quote_curva = np.linspace(z_min, z_max, 60)
area_sopra = 100 * (1 - np.searchsorted(zs, quote_curva) / zs.size)

# --------------------------------------------- reticolo e ordine di Strahler
righe = in_crs_dem(ret)
nomi = [fld.name() for fld in ret.fields()]
k = lambda p: (round(p.x(), 2), round(p.y(), 2))


def estremi(g):
    parti = g.asMultiPolyline() if g.isMultipart() else [g.asPolyline()]
    return parti[0][0], parti[-1][-1]


quota = lambda xy: dem.dataProvider().sample(QgsPointXY(*xy), 1)[0]
feat = {n: g for n, (f, g) in enumerate(righe)}
lung = {n: g.length() for n, g in feat.items()}
adj = defaultdict(list)
for n, g in feat.items():
    p1, p2 = map(k, estremi(g))
    adj[p1].append((n, p2))
    adj[p2].append((n, p1))
sbocco = min((nd for nd, v in adj.items() if len(v) == 1), key=quota)
ordine, monte = {}, {}


def visita(nodo, via):
    figli = [visita(o, s) for s, o in adj[nodo] if s != via]
    if not figli:
        s_, L = 1, 0
    else:
        oo = sorted((x[0] for x in figli), reverse=True)
        s_ = oo[0] + 1 if len(oo) > 1 and oo[0] == oo[1] else oo[0]
        L = max(x[1] for x in figli)
    if via is not None:
        L += lung[via]
        ordine[via], monte[via] = s_, L
    return s_, L


visita(sbocco, None)
if 'strahler' in nomi:  # se lo script dell'episodio 2 e' gia' stato lanciato
    ordine = {n: f['strahler'] for n, (f, g) in enumerate(righe) if f['strahler'] not in (None, NULL)}
asta_ids, nodo, via = [], sbocco, None
while True:
    figli = [(s, o) for s, o in adj[nodo] if s != via and s in monte]
    if not figli:
        break
    via, nodo = max(figli, key=lambda x: monte[x[0]])
    asta_ids.append(via)
if asta_lyr is not None:
    geom_asta = QgsGeometry.unaryUnion([g for f, g in in_crs_dem(asta_lyr)]).mergeLines()
elif 'asta_princ' in nomi:
    geom_asta = QgsGeometry.unaryUnion([g for f, g in righe if f['asta_princ'] == 1]).mergeLines()
else:
    geom_asta = QgsGeometry.unaryUnion([feat[n] for n in asta_ids]).mergeLines()
L_km = geom_asta.length() / 1e3
ret_km = sum(lung.values()) / 1e3
Dd = ret_km / A_km2
ord_max = max(ordine.values())

# profilo longitudinale dalla sezione di chiusura alla testata
linea = geom_asta.asMultiPolyline()[0] if geom_asta.isMultipart() else geom_asta.asPolyline()
if quota((linea[0].x(), linea[0].y())) > quota((linea[-1].x(), linea[-1].y())):
    linea = linea[::-1]
geom_linea = QgsGeometry.fromPolylineXY(linea)
dist = np.arange(0, geom_linea.length(), 10.0).tolist() + [geom_linea.length()]
prof = [quota((p.x(), p.y())) for p in (geom_linea.interpolate(s).asPoint() for s in dist)]
H0, H_testata = prof[0], prof[-1]
i_asta = (H_testata - H0) / (L_km * 1000)
outlet_xy = linea[0]

# -------------------------------------------------- tempi di corrivazione (h)
Hm = z_mean
tc = [
    ('Giandotti', (4 * math.sqrt(A_km2) + 1.5 * L_km) / (0.8 * math.sqrt(Hm - H0)), 'tarata su 170-70.000 km\u00b2'),
    ('Kirpich', 0.000325 * (L_km * 1000) ** 0.77 * i_asta ** -0.385, ''),
    ('Ventura', 0.1272 * math.sqrt(A_km2 / i_asta), ''),
    ('Pezzoli', 0.055 * L_km / math.sqrt(i_asta), ''),
    ('Pasini', 0.108 * (A_km2 * L_km) ** (1 / 3) / math.sqrt(i_asta), ''),
]

print('A %.3f km2  P %.2f / %.2f km  Kc %.2f / %.2f  Rc %.2f / %.2f' % (A_km2, P_km, Ps_km, Kc, Kcs, Rc, Rcs))
print('quote min %.1f max %.1f media %.1f mediana %.1f  HI %.2f' % (z_min, z_max, z_mean, z_med, HI))
print('pendenza %.1f gradi, %.1f %%' % (slope_deg, slope_pct))
print('reticolo %.2f km, Dd %.2f km/km2, ordine max %d' % (ret_km, Dd, ord_max))
print('asta %.2f km, H0 %.1f, testata %.1f, i %.3f' % (L_km, H0, H_testata, i_asta))
for n_, t, _ in tc:
    print('tc %s %.2f h (%d min)' % (n_, t, round(t * 60)))

# ------------------------------------------------------ layer per la tavola
radice = P.layerTreeRoot()
vecchio = radice.findGroup('Tavola bacino')
if vecchio:
    for l in vecchio.findLayers():
        P.removeMapLayer(l.layerId())
    radice.removeChildNode(vecchio)
gruppo = radice.insertGroup(0, 'Tavola bacino')
crs_id = crs.authid()


def aggiungi(layer, nome):
    layer.setName(nome)
    layer.setCustomProperty('tavola_bacino', True)
    P.addMapLayer(layer, False)
    gruppo.addLayer(layer)
    return layer


hs = QgsRasterLayer(dem.source(), 'Rilievo', dem.providerType())
rend = QgsHillshadeRenderer(hs.dataProvider(), 1, 315, 45)
rend.setMultiDirectional(True)
hs.setRenderer(rend)
hs.setOpacity(0.9)
aggiungi(hs, 'Rilievo (hillshade)')

ql = QgsRasterLayer(dem.source(), 'Quote', dem.providerType())
st = ql.dataProvider().bandStatistics(1, QgsRasterBandStats.All, ql.extent(), 0)
ramp = QgsColorRampShader(st.minimumValue, st.maximumValue)
ramp.setColorRampType(QgsColorRampShader.Interpolated)
cols = ['#3a7d44', '#a6c36f', '#e8d98a', '#c99a5b', '#8c5a3c', '#f2f2f2']
vals = np.linspace(st.minimumValue, st.maximumValue, len(cols))
ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(float(v), QColor(c)) for v, c in zip(vals, cols)])
sh = QgsRasterShader()
sh.setRasterShaderFunction(ramp)
ql.setRenderer(QgsSingleBandPseudoColorRenderer(ql.dataProvider(), 1, sh))
ql.setOpacity(0.45)
ql.setBlendMode(QPainter.CompositionMode_Multiply)
aggiungi(ql, 'Quote')

lb = QgsVectorLayer('MultiPolygon?crs=%s' % crs_id, 'b', 'memory')
fb = QgsFeature()
fb.setGeometry(geom_semp)
lb.dataProvider().addFeatures([fb])
lb.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
    {'color': '200,30,30,25', 'outline_color': '200,30,30,255', 'outline_width': '0.7'})))
aggiungi(lb, 'Bacino (%s km\u00b2)' % num(A_km2, 2))

lr = QgsVectorLayer('LineString?crs=%s' % crs_id, 'r', 'memory')
lr.dataProvider().addAttributes([QgsField('strahler', QVariant.Int)])
lr.updateFields()
nf = []
for n, g in feat.items():
    q = QgsFeature(lr.fields())
    q.setGeometry(g)
    q['strahler'] = ordine.get(n)
    nf.append(q)
lr.dataProvider().addFeatures(nf)
blu = ['#9ecae1', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041c40']
spess = [0.3, 0.55, 0.85, 1.2, 1.6, 2.0]
cats = []
for o in range(1, ord_max + 1):
    s = QgsLineSymbol.createSimple({'color': blu[min(o - 1, 5)], 'width': str(spess[min(o - 1, 5)]),
                                    'capstyle': 'round', 'joinstyle': 'round'})
    cats.append(QgsRendererCategory(o, s, 'Ordine %d' % o))
lr.setRenderer(QgsCategorizedSymbolRenderer('strahler', cats))
aggiungi(lr, 'Reticolo, ordine di Strahler')

la = QgsVectorLayer('LineString?crs=%s' % crs_id, 'a', 'memory')
fa = QgsFeature()
fa.setGeometry(geom_linea)
la.dataProvider().addFeatures([fa])
sa = QgsLineSymbol.createSimple({'color': '255,255,255,230', 'width': '2.6', 'capstyle': 'round'})
sa.appendSymbolLayer(QgsSimpleLineSymbolLayer(QColor('#0b2a5b'), 1.4))
la.setRenderer(QgsSingleSymbolRenderer(sa))
aggiungi(la, 'Asta principale (%s km)' % num(L_km, 2))

lo = QgsVectorLayer('Point?crs=%s' % crs_id, 'o', 'memory')
fo = QgsFeature()
fo.setGeometry(QgsGeometry.fromPointXY(outlet_xy))
lo.dataProvider().addFeatures([fo])
lo.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
    {'name': 'circle', 'color': '200,30,30', 'outline_color': 'white', 'outline_width': '0.8', 'size': '4.2'})))
aggiungi(lo, 'Sezione di chiusura (%s m)' % num(H0, 1))

# ------------------------------------------------------------- grafici SVG
cartella = tempfile.mkdtemp(prefix='tavola_bacino_')


def grafico(nome, xs, ys, xlim, ylim, xstep, ystep, xlab, ylab, nota='', xdec=0):
    W, H, l, r, t, bt = 600, 560, 96, 22, 24, 84
    X = lambda v: l + (v - xlim[0]) / (xlim[1] - xlim[0]) * (W - l - r)
    Y = lambda v: H - bt - (v - ylim[0]) / (ylim[1] - ylim[0]) * (H - t - bt)
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect x="0" y="0" width="%d" height="%d" fill="white"/>' % (W, H)]
    v = xlim[0]
    while v <= xlim[1] + 1e-9:
        s.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#dddddd" stroke-width="1.5"/>' % (X(v), t, X(v), H - bt))
        s.append('<text x="%.1f" y="%d" font-family="Arial" font-size="24" fill="#444444" text-anchor="middle">%s</text>'
                 % (X(v), H - bt + 32, num(v, xdec)))
        v += xstep
    v = ylim[0]
    while v <= ylim[1] + 1e-9:
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#dddddd" stroke-width="1.5"/>' % (l, Y(v), W - r, Y(v)))
        s.append('<text x="%d" y="%.1f" font-family="Arial" font-size="24" fill="#444444" text-anchor="end">%s</text>'
                 % (l - 10, Y(v) + 8, num(v, 0)))
        v += ystep
    pts = ' '.join('%.1f,%.1f' % (X(a_), Y(b_)) for a_, b_ in zip(xs, ys))
    s.append('<polygon points="%.1f,%.1f %s %.1f,%.1f" fill="#c6dbef" stroke="none"/>'
             % (X(xs[0]), Y(ylim[0]), pts, X(xs[-1]), Y(ylim[0])))
    s.append('<polyline points="%s" fill="none" stroke="#08519c" stroke-width="4" stroke-linejoin="round"/>' % pts)
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#444444" stroke-width="2"/>' % (l, H - bt, W - r, H - bt))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#444444" stroke-width="2"/>' % (l, t, l, H - bt))
    s.append('<text x="%.1f" y="%d" font-family="Arial" font-size="25" fill="#222222" text-anchor="middle">%s</text>'
             % ((l + W - r) / 2, H - 12, xlab))
    s.append('<text x="26" y="%.1f" font-family="Arial" font-size="25" fill="#222222" text-anchor="middle" '
             'transform="rotate(-90 26 %.1f)">%s</text>' % ((t + H - bt) / 2, (t + H - bt) / 2, ylab))
    if nota:
        s.append('<text x="%d" y="%d" font-family="Arial" font-size="27" font-weight="bold" fill="#08519c" '
                 'text-anchor="end">%s</text>' % (W - r - 10, t + 34, nota))
    s.append('</svg>')
    path = os.path.join(cartella, nome + '.svg')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(s))
    return path


ytop = math.ceil(z_max / 100) * 100
svg_ips = grafico('ipsometrica', area_sopra.tolist(), quote_curva.tolist(), (0, 100), (0, ytop), 20, 100,
                  'Area sopra la quota (%)', 'Quota (m)', nota='HI = %s' % num(HI, 2))
svg_prof = grafico('profilo', [d_ / 1000 for d_ in dist], prof, (0, math.ceil(L_km * 2) / 2),
                   (0, math.ceil(H_testata / 100) * 100), 0.5, 100,
                   'Distanza dalla sezione (km)', 'Quota (m)', nota='i = %s%%' % num(i_asta * 100, 1), xdec=1)
svg_nord = os.path.join(cartella, 'nord.svg')
with open(svg_nord, 'w', encoding='utf-8') as fh:
    fh.write('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="90" viewBox="0 0 60 90">'
             '<polygon points="30,8 46,62 30,52" fill="#222222"/><polygon points="30,8 14,62 30,52" fill="white" '
             'stroke="#222222" stroke-width="2"/><text x="30" y="86" font-family="Arial" font-size="20" '
             'font-weight="bold" text-anchor="middle" fill="#222222">N</text></svg>')

# ------------------------------------------------------------------ layout
man = P.layoutManager()
for vecchio_layout in [l for l in man.printLayouts() if l.name() == TITOLO_LAYOUT]:
    man.removeLayout(vecchio_layout)
lay = QgsPrintLayout(P)
lay.initializeDefaults()
lay.setName(TITOLO_LAYOUT)
man.addLayout(lay)
lay.pageCollection().page(0).setPageSize('A3', QgsLayoutItemPage.Landscape)


def metti(item, x, y, w, h):
    lay.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(w, h, MM))
    return item


def testo(t, x, y, w, h, size=10, bold=False, html=False, colore='#222222'):
    lab = QgsLayoutItemLabel(lay)
    if html:
        modo = getattr(QgsLayoutItemLabel, 'ModeHtml', None)
        lab.setMode(modo if modo is not None else Qgis.LayoutLabelMode.RenderHtml)
    lab.setText(t)
    fmt = QgsTextFormat()
    fnt = QFont('Arial')
    fnt.setBold(bold)
    fmt.setFont(fnt)
    fmt.setSize(size)
    fmt.setColor(QColor(colore))
    lab.setTextFormat(fmt)
    return metti(lab, x, y, w, h)


testo(TITOLO, 12, 9, 300, 12, size=24, bold=True)
testo(SOTTOTITOLO, 12, 21, 300, 7, size=11, colore='#555555')

# mappa: la scala tonda piu' grande con cui il bacino entra in 250 x 250 mm
est = geom_bac.boundingBox()
est.grow(max(est.width(), est.height()) * 0.05)
for scala in (1000, 2000, 2500, 5000, 7500, 10000, 12500, 15000, 20000, 25000, 50000, 100000):
    mw, mh = est.width() / scala * 1000, est.height() / scala * 1000
    if mw <= 250 and mh <= 250:
        break
mw, mh = max(mw, 150), max(mh, 200)
mappa = QgsLayoutItemMap(lay)
metti(mappa, 12, 32, mw, mh)
mappa.setCrs(crs)
mappa.setLayers([lo, la, lr, lb, ql, hs])
mappa.setKeepLayerSet(True)
c = est.center()
mappa.zoomToExtent(QgsRectangle(c.x() - mw * scala / 2000, c.y() - mh * scala / 2000,
                                c.x() + mw * scala / 2000, c.y() + mh * scala / 2000))
mappa.setScale(scala)
mappa.setFrameEnabled(True)
mappa.setFrameStrokeColor(QColor('#888888'))

leg = QgsLayoutItemLegend(lay)
leg.setLinkedMap(mappa)
leg.setAutoUpdateModel(False)
radice_leg = leg.model().rootGroup()
radice_leg.removeAllChildren()
for l in (lo, la, lr, lb):
    radice_leg.addLayer(l)
leg.setTitle('')
leg.setBackgroundEnabled(True)
leg.setBackgroundColor(QColor(255, 255, 255, 215))
metti(leg, 15, 35, 60, 40)
leg.adjustBoxSize()

barra = QgsLayoutItemScaleBar(lay)
barra.setStyle('Single Box')
barra.setLinkedMap(mappa)
try:
    barra.setUnits(Qgis.DistanceUnit.Kilometers)
except Exception:
    barra.setUnits(QgsUnitTypes.DistanceKilometers)
barra.setUnitLabel('km')
barra.setNumberOfSegments(2)
barra.setNumberOfSegmentsLeft(0)
barra.setUnitsPerSegment(0.25 if scala <= 15000 else 0.5)
barra.setBackgroundEnabled(True)
barra.setBackgroundColor(QColor(255, 255, 255, 215))
metti(barra, 15, 32 + mh - 15, 60, 12)
barra.update()

nord = QgsLayoutItemPicture(lay)
nord.setPicturePath(svg_nord)
metti(nord, 12 + mw - 13, 35, 10, 15)

# colonna dei parametri, a destra della mappa
X0 = 12 + mw + 10
W0 = 408 - X0
r = lambda nome, val, u='': '<tr><td>%s</td><td align="right"><b>%s</b> %s</td></tr>' % (nome, val, u)
css = ('<style>body{font-family:Arial;font-size:11pt;color:#222}h3{font-size:12pt;margin:0 0 3px 0;color:#08519c}'
       'table{width:100%;border-collapse:collapse}td{padding:1px 0;border-bottom:1px solid #e3e3e3}</style>')
geo = (css + '<h3>Geometria e forma</h3><table>'
       + r('Area', num(A_km2, 3), 'km²')
       + r('Perimetro a scalini / semplificato', '%s / %s' % (num(P_km, 2), num(Ps_km, 2)), 'km')
       + r('Gravelius Kc (semplificato)', num(Kcs, 2))
       + r('Circolarità Rc (semplificato)', num(Rcs, 2))
       + '</table><br><h3>Quote e pendenze</h3><table>'
       + r('Quota minima / massima', '%s / %s' % (num(z_min, 1), num(z_max, 1)), 'm')
       + r('Quota media / mediana', '%s / %s' % (num(z_mean, 1), num(z_med, 1)), 'm')
       + r('Pendenza media', '%s° (%s%%)' % (num(slope_deg, 1), num(slope_pct, 1)))
       + r('Integrale ipsometrico HI', num(HI, 2))
       + '</table><br><h3>Reticolo e asta principale</h3><table>'
       + r('Lunghezza reticolo', num(ret_km, 2), 'km')
       + r('Densità di drenaggio', num(Dd, 2), 'km/km²')
       + r('Ordine di Strahler massimo', str(ord_max))
       + r('Lunghezza asta principale', num(L_km, 2), 'km')
       + r('Quota testata / sezione', '%s / %s' % (num(H_testata, 1), num(H0, 1)), 'm')
       + r('Pendenza media asta', num(i_asta * 100, 1), '%')
       + '</table>')
testo(geo, X0, 31, W0, 122, html=True)
tct = (css + '<h3>Tempo di corrivazione</h3><table>'
       + ''.join(r(n_ + (' <span style="font-size:8.5pt;color:#777">(%s)</span>' % nt if nt else ''),
                   '%s h' % num(t, 2), '(%d min)' % round(t * 60)) for n_, t, nt in tc)
       + '</table>')
testo(tct, X0, 140, W0, 50, html=True)

gw = (W0 - 6) / 2
gh = min(gw * 560 / 600, 280 - 207)
for path, x, tit in ((svg_ips, X0, 'Curva ipsometrica'), (svg_prof, X0 + gw + 6, "Profilo dell'asta principale")):
    testo(tit, x, 200, gw, 6, size=10, bold=True, colore='#08519c')
    pic = QgsLayoutItemPicture(lay)
    pic.setPicturePath(path)
    metti(pic, x, 207, gw, gh)

testo('Scala 1:%s, %s. %s. Tolleranza Simplify %s m. %s'
      % (num(scala, 0), crs.authid(), FONTE, num(TOLLERANZA_SIMPLIFY, 1), datetime.date.today().strftime('%d/%m/%Y')),
      12, 288, 396, 5, size=7.5, colore='#777777')

lay.refresh()
if ESPORTA_PDF:
    QgsLayoutExporter(lay).exportToPdf(ESPORTA_PDF, QgsLayoutExporter.PdfExportSettings())
    print('PDF salvato in', ESPORTA_PDF)
try:
    iface.openLayoutDesigner(lay)
except NameError:
    pass
print("Layout '%s' creato." % TITOLO_LAYOUT)
